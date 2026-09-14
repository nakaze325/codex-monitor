import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

import config
from twitter_fetcher import Tweet


def build_email(tweet: Tweet, result: dict) -> tuple[str, str]:
    score = result["score"]
    category = "高概率重置" if score >= 80 else "疑似重置"
    subject = f"🚨 Codex重置信号：{score}%" if score >= 80 else f"⚠️ Codex疑似重置：{score}%"
    body = f"""Codex重置信号：{score}%
判断：{category}，请到 Codex 额度页面确认实际状态。
====================

时间：{tweet.time.isoformat()}
来源：{config.SOURCE}
原文链接：{tweet.url}

原文：
{tweet.text}

信号类型：{result['signal_type']}

AI分析（本地关键词规则）：
{result['analysis']}

建议：
建议立即打开 Codex 检查额度状态。
Codex小火车可能进站啦 🚂
"""
    return subject, body


def send_notification(tweet: Tweet, result: dict) -> dict:
    if result["score"] < config.SEND_THRESHOLD:
        return {"status": "skipped"}
    try:
        sender, password, receiver = config.email_credentials()
        subject, body = build_email(tweet, result)
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = sender, receiver, subject
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid()
        message.set_content(body, charset="utf-8")
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}
    smtp = None
    submitting = False
    try:
        smtp = smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT, timeout=30, context=ssl.create_default_context())
        smtp.login(sender, password)
        submitting = True
        if smtp.send_message(message, from_addr=sender, to_addrs=[receiver]):
            return {"status": "error", "error": "SMTP 拒绝收件人"}
        return {"status": "sent", "message_id": str(message["Message-ID"])}
    except smtplib.SMTPAuthenticationError:
        return {"status": "error", "error": "SMTP 登录失败，请核对授权码和 SMTP 开关"}
    except smtplib.SMTPResponseException as exc:
        return {"status": "error", "error": f"SMTP 拒绝请求，代码 {exc.smtp_code}"}
    except smtplib.SMTPRecipientsRefused:
        return {"status": "error", "error": "SMTP 拒绝收件人"}
    except (smtplib.SMTPException, OSError) as exc:
        return {"status": "unknown" if submitting else "error", "error": f"SMTP 连接异常：{type(exc).__name__}"}
    finally:
        if smtp is not None:
            # 关闭阶段的错误不会改变服务器已经接受 DATA 的事实。
            try:
                smtp.close()
            except OSError:
                pass

