"""Notifications: email (primary) and ntfy phone pings (optional).

If email fails for any reason, results are written to logs/notifications.log so
nothing is ever lost silently.
"""

from __future__ import annotations

import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

import requests


def _posting_line(p: dict) -> str:
    bits = [f"[{p.get('posting_type','').upper()}] {p.get('title','')}"]
    if p.get("organization"):
        bits.append(f"  {p['organization']}")
    loc = " ".join(x for x in [p.get("location", ""), p.get("country", "")] if x).strip()
    if loc:
        bits.append(f"  {loc}")
    if p.get("relevance_score") is not None:
        bits.append(f"  relevance {p['relevance_score']}/10")
    if p.get("relevance_reason"):
        bits.append(f"  why: {p['relevance_reason']}")
    if p.get("deadline"):
        flag = "  URGENT" if p.get("urgent") else ""
        bits.append(f"  deadline: {p['deadline']}{flag}")
    if p.get("salary"):
        bits.append(f"  funding/salary: {p['salary']}")
    if p.get("tags"):
        bits.append(f"  tags: {', '.join(p['tags'])}")
    if p.get("url"):
        bits.append(f"  {p['url']}")
    return "\n".join(bits)


def build_digest(postings: list, header: str) -> str:
    if not postings:
        return f"{header}\n\nNothing new this time."
    # Most urgent and most relevant first.
    postings = sorted(
        postings,
        key=lambda p: (not p.get("urgent", False), -(p.get("relevance_score") or 0)),
    )
    blocks = [_posting_line(p) for p in postings]
    return f"{header}\n\n" + ("\n\n".join(blocks))


def send_email(email_cfg: dict, subject: str, body: str) -> bool:
    host = email_cfg.get("smtp_host", "smtp.gmail.com")
    port = int(email_cfg.get("smtp_port", 587))
    user = email_cfg.get("username", "")
    pwd = email_cfg.get("password", "")
    to_addr = email_cfg.get("to", "")
    from_addr = email_cfg.get("from") or user
    if not (user and pwd and to_addr):
        return False
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    try:
        with smtplib.SMTP(host, port, timeout=40) as server:
            server.starttls()
            server.login(user, pwd)
            server.sendmail(from_addr, [to_addr], msg.as_string())
        return True
    except Exception:
        return False


def send_ntfy(ntfy_cfg: dict, title: str, message: str) -> bool:
    if not ntfy_cfg.get("enabled"):
        return False
    topic = ntfy_cfg.get("topic", "")
    server = ntfy_cfg.get("server", "https://ntfy.sh").rstrip("/")
    if not topic:
        return False
    try:
        requests.post(
            f"{server}/{topic}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": "default"},
            timeout=30,
        )
        return True
    except Exception:
        return False


def log_fallback(body: str):
    Path("logs").mkdir(exist_ok=True)
    with open("logs/notifications.log", "a", encoding="utf-8") as f:
        f.write(f"\n===== {datetime.utcnow().isoformat()} =====\n{body}\n")


def notify(notif_cfg: dict, subject: str, body: str):
    """Send by every enabled channel; always log a fallback copy on email failure."""
    email_cfg = notif_cfg.get("email", {})
    sent_email = False
    if email_cfg.get("enabled", True):
        sent_email = send_email(email_cfg, subject, body)
    send_ntfy(notif_cfg.get("ntfy", {}), subject, body)
    if not sent_email:
        log_fallback(f"{subject}\n\n{body}")
    return sent_email
