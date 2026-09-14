import os
from email.headerregistry import Address

SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
TARGET_USER = "thsottiaux"
SOURCE = "Tibo (@thsottiaux)"
SEND_THRESHOLD = 60
HTTP_TIMEOUT = 25
MAX_FEED_BYTES = 2_000_000
STATE_PATH = "state/processed_tweets.json"
DEFAULT_RSS_URLS = [
    "https://nitter.privacyredirect.com/thsottiaux/rss",
    "https://nitter.kareem.one/thsottiaux/rss",
]


def rss_urls() -> list[str]:
    value = os.getenv("TWITTER_RSS_URLS", "").strip()
    if not value:
        return DEFAULT_RSS_URLS.copy()
    urls = [line.strip() for line in value.splitlines() if line.strip()]
    if len(urls) > 5:
        raise ValueError("TWITTER_RSS_URLS 最多配置 5 个地址")
    return urls


def email_credentials() -> tuple[str, str, str]:
    names = ("QQ_EMAIL", "QQ_AUTH_CODE", "RECEIVER_EMAIL")
    values = tuple(os.getenv(name, "").strip() for name in names)
    for name, value in zip(names, values):
        if not value:
            raise ValueError(f"缺少 GitHub Secret：{name}")
    sender, password, receiver = values
    if not password.isascii() or any(c.isspace() for c in password):
        raise ValueError("QQ_AUTH_CODE 必须是不含空白的 ASCII 授权码")
    for name, value in (("QQ_EMAIL", sender), ("RECEIVER_EMAIL", receiver)):
        try:
            value.encode("ascii")
            address = Address(addr_spec=value)
            if not address.username or not address.domain or any(c.isspace() for c in value):
                raise ValueError
        except ValueError as exc:
            raise ValueError(f"{name} 必须是单个有效的 ASCII 邮箱地址") from exc
    return sender, password, receiver
