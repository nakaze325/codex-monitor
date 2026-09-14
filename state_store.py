import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

import config


class StateError(RuntimeError):
    pass


class GitHubState:
    def __init__(self):
        repository = os.getenv("GITHUB_REPOSITORY", "")
        self.token = os.getenv("GITHUB_TOKEN", "")
        self.branch = os.getenv("STATE_BRANCH", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or not self.token or not self.branch:
            raise StateError("缺少 GITHUB_REPOSITORY、GITHUB_TOKEN 或 STATE_BRANCH；正式运行请使用 GitHub Actions")
        self.url = f"https://api.github.com/repos/{repository}/contents/{config.STATE_PATH}"
        self.sha = None
        self.data = {"version": 1, "initialized": False, "tweets": {}}

    def request(self, method: str, payload: dict | None = None) -> dict | None:
        url = self.url + ("?" + urllib.parse.urlencode({"ref": self.branch}) if method == "GET" else "")
        request = urllib.request.Request(
            url,
            data=None if payload is None else json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json", "Content-Type": "application/json", "User-Agent": "CodexMonitor/1.0"},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=config.HTTP_TIMEOUT) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if method == "GET" and exc.code == 404:
                return None
            raise StateError(f"GitHub 状态{method}失败：HTTP {exc.code}；检查 contents:write、分支规则或并发修改") from exc
        except (OSError, ValueError) as exc:
            raise StateError(f"GitHub 状态{method}失败：{type(exc).__name__}") from exc

    def load(self):
        response = self.request("GET")
        if response is None:
            return
        try:
            data = json.loads(base64.b64decode(response["content"]).decode("utf-8"))
            if data["version"] != 1 or type(data["initialized"]) is not bool or not isinstance(data["tweets"], dict):
                raise ValueError
            for tweet_id, status in data["tweets"].items():
                if not tweet_id.isdigit() or status not in {"ignored", "normal", "pending", "sent"}:
                    raise ValueError
            if not isinstance(response["sha"], str) or not response["sha"]:
                raise ValueError
            self.data, self.sha = data, response["sha"]
        except (KeyError, TypeError, ValueError) as exc:
            raise StateError("状态文件无效，已停止；请先修复文件，避免丢失去重记录") from exc

    def save(self):
        content = base64.b64encode(json.dumps(self.data, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")).decode("ascii")
        payload = {"message": "Update Codex monitor delivery state", "content": content, "branch": self.branch}
        if self.sha:
            payload["sha"] = self.sha
        response = self.request("PUT", payload)
        try:
            self.sha = response["content"]["sha"]
        except (KeyError, TypeError) as exc:
            raise StateError("GitHub 未返回已保存状态的 SHA，请检查仓库状态") from exc

