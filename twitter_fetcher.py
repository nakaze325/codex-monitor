import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

import config


class FetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class Tweet:
    id: str
    time: datetime
    text: str
    url: str


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "p", "div"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"p", "div"}:
            self.parts.append("\n")


def plain_text(value: str) -> str:
    parser = PlainText()
    parser.feed(value)
    return "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())


def tag_name(element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def child_text(element, *names) -> str:
    for name in names:
        for child in element:
            if tag_name(child) == name:
                value = "".join(child.itertext()).strip()
                if value:
                    return value
    return ""


def parse_time(value: str) -> datetime:
    try:
        date = parsedate_to_datetime(value)
    except (ValueError, TypeError):
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("推文时间缺少时区")
    return date.astimezone(timezone.utc)


def parse_feed(data: bytes) -> list[Tweet]:
    if len(data) > config.MAX_FEED_BYTES:
        raise FetchError("RSS 超过大小限制")
    # 拒绝 DTD，避免外部来源的实体声明影响 XML 解析。
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper() or b"\x00" in data:
        raise FetchError("RSS 包含不支持的 XML 声明或编码")
    try:
        root = ET.fromstring(data.lstrip())
    except ET.ParseError as exc:
        raise FetchError("返回内容不是有效 RSS/Atom XML，可能是验证页面") from exc
    if tag_name(root) not in {"rss", "feed", "RDF"}:
        raise FetchError("返回内容不是 RSS/Atom")
    tweets = {}
    for entry in root.iter():
        if tag_name(entry) not in {"item", "entry"}:
            continue
        links = [child.get("href", "") or (child.text or "") for child in entry
                 if tag_name(child) == "link" and child.get("rel", "alternate") == "alternate"]
        links.append(child_text(entry, "guid", "id"))
        match = None
        for link in links:
            path = urllib.parse.urlsplit(link.strip()).path
            candidate = re.fullmatch(r"/([A-Za-z0-9_]+)/status/(\d+)(?:/.*)?", path)
            if candidate and candidate[1].lower() == config.TARGET_USER:
                match = candidate
                break
        if match is None:
            continue
        text = plain_text(child_text(entry, "encoded", "content", "description", "summary", "title"))
        try:
            date = parse_time(child_text(entry, "pubDate", "published", "date", "updated"))
        except (ValueError, TypeError, OverflowError) as exc:
            raise FetchError("RSS 中 Tibo 动态的时间无效") from exc
        if not text or date > datetime.now(timezone.utc) + timedelta(minutes=15):
            raise FetchError("RSS 中 Tibo 动态正文为空或时间异常")
        tweet_id = match[2]
        tweets[tweet_id] = Tweet(tweet_id, date, text, f"https://x.com/{config.TARGET_USER}/status/{tweet_id}")
    if not tweets:
        raise FetchError("未读到带 Tibo 推文链接的条目：请检查 RSS 白名单、验证页、账号及来源服务")
    return sorted(tweets.values(), key=lambda tweet: (tweet.time, int(tweet.id)))


def fetch_latest_tweets(urls: list[str] | None = None) -> list[Tweet]:
    failures = []
    for index, url in enumerate(config.rss_urls() if urls is None else urls, 1):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise FetchError("RSS 地址必须是 HTTPS URL，不能包含用户名密码")
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "CodexMonitor/1.0 RSS reader", "Accept": "application/rss+xml, application/atom+xml"})
            with urllib.request.urlopen(request, timeout=config.HTTP_TIMEOUT) as response:
                if urllib.parse.urlsplit(response.url).scheme != "https":
                    raise FetchError("RSS 重定向到非 HTTPS 地址")
                tweets = parse_feed(response.read(config.MAX_FEED_BYTES + 1))
            print(f"RSS 来源 #{index}：取得 {len(tweets)} 条，最新时间 {tweets[-1].time.isoformat()}")
            return tweets
        except urllib.error.HTTPError as exc:
            failures.append(f"来源 #{index}: HTTP {exc.code}")
        except (OSError, ValueError, FetchError) as exc:
            detail = str(exc) if isinstance(exc, FetchError) else type(exc).__name__
            failures.append(f"来源 #{index}: {detail}")
    raise FetchError("全部 RSS 来源失败；" + "；".join(failures))
