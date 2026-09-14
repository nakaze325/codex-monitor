import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

import config
from analyzer import analyze
from email_sender import build_email, send_notification
from state_store import GitHubState, StateError
from twitter_fetcher import FetchError, Tweet, fetch_latest_tweets


def process_tweets(tweets: list[Tweet], store, now: datetime) -> bool:
    states = store.data["tweets"]
    first_run = not store.data["initialized"]
    ready = []
    changed = first_run
    for tweet in tweets:
        if tweet.id in states:
            continue
        result = analyze(tweet.text)
        if first_run and tweet.time < now - timedelta(hours=24):
            states[tweet.id] = "ignored"
            changed = True
        elif result["score"] < config.SEND_THRESHOLD:
            states[tweet.id] = "normal"
            changed = True
        else:
            ready.append((tweet, result))
    if changed:
        store.data["initialized"] = True
        store.save()
    failed = False
    for tweet, result in ready:
        # SMTP 与仓库无法组成事务；先持久化占位，异常中断后由人工确认投递状态。
        states[tweet.id] = "pending"
        store.save()
        delivery = send_notification(tweet, result)
        print(json.dumps({"tweet_id": tweet.id, "score": result["score"], **delivery}, ensure_ascii=False))
        if delivery["status"] == "sent":
            states[tweet.id] = "sent"
            store.save()
        elif delivery["status"] == "error":
            del states[tweet.id]
            store.save()
            failed = True
        else:
            failed = True
    pending = [tweet_id for tweet_id, status in states.items() if status == "pending"]
    if pending:
        print("存在待确认投递，已暂停这些 ID 的自动重发：" + ", ".join(pending))
    print(f"处理结束：本轮候选 {len(ready)} 条，累计记录 {len(states)} 条。")
    return not (failed or pending)


def main() -> int:
    parser = argparse.ArgumentParser(description="GitHub Actions Codex RSS 邮件监控")
    parser.add_argument("--mode", choices=("monitor", "preview", "test-email"), default="monitor")
    args = parser.parse_args()
    try:
        if args.mode == "test-email":
            tweet = Tweet("0", datetime.now(timezone.utc), "【测试邮件】Codex usage limits restored", "https://x.com/thsottiaux")
            result = send_notification(tweet, analyze(tweet.text))
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["status"] == "sent" else 1
        if args.mode == "preview":
            for tweet in fetch_latest_tweets():
                result = analyze(tweet.text)
                print(json.dumps({"tweet_id": tweet.id, "time": tweet.time.isoformat(), "url": tweet.url, **result}, ensure_ascii=False))
                if result["score"] >= config.SEND_THRESHOLD:
                    print(build_email(tweet, result)[1])
            return 0
        config.email_credentials()
        store = GitHubState()
        store.load()
        tweets = fetch_latest_tweets()
        return 0 if process_tweets(tweets, store, datetime.now(timezone.utc)) else 1
    except (ValueError, FetchError, StateError) as exc:
        print(f"运行失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())

