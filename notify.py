"""
Alerts for the developer when a user sends a report.

Set these on Render (Environment tab). Each channel is optional; a channel with missing settings is skipped.

Telegram:
  TELEGRAM_BOT_TOKEN   token from @BotFather
  TELEGRAM_CHAT_ID     your chat id

Email (for example Gmail with an App Password):
  ALERT_EMAIL_TO       where the alert is sent
  SMTP_USER            the sending address (for Gmail, the same Gmail address)
  SMTP_PASS            the App Password
  SMTP_HOST            default smtp.gmail.com
  SMTP_PORT            default 587

The alert never includes the user's email. A failed alert is only logged: the user's report is already saved.
"""
import logging
import os
import smtplib
from email.message import EmailMessage

import requests


def build_text(info):
    """info: dict with kind, allergen, note, scan_id, scan_type, flagged (list of names), input_text."""
    lines = [
        f"SmartScan: new report ({info.get('scan_type') or 'allergy'} scan)",
        f"Type: {info.get('kind') or '-'}",
        f"Allergen: {info.get('allergen') or '-'}",
        f"Scan ID: {info.get('scan_id')}",
        f"AI flagged: {', '.join(info.get('flagged') or []) or 'nothing'}",
    ]
    note = (info.get("note") or "").strip()
    if note:
        lines.append(f"User note: {note[:300]}")
    text = (info.get("input_text") or "").strip()
    if text:
        lines.append(f"Typed ingredients: {text[:200]}")
    lines.append("Open Supabase > Table Editor > reports to see the full report.")
    return "\n".join(lines)


def _telegram(text):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat, "text": text},
        timeout=10,
    )
    r.raise_for_status()
    return True


def _email(text):
    to = os.getenv("ALERT_EMAIL_TO")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    if not to or not user or not password:
        return False
    msg = EmailMessage()
    msg["Subject"] = "SmartScan: new user report"
    msg["From"] = user
    msg["To"] = to
    msg.set_content(text)
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=15) as s:
        s.starttls()
        s.login(user, password)
        s.send_message(msg)
    return True


def notify_report(info):
    text = build_text(info)
    logging.warning("Report received (scan %s): trying to send alert", info.get("scan_id"))
    sent_any = False
    for name, fn in (("telegram", _telegram), ("email", _email)):
        try:
            if fn(text):
                sent_any = True
                logging.warning("Report alert sent by %s", name)
        except Exception:
            logging.exception("Report alert by %s failed", name)
    if not sent_any:
        have_token = bool(os.getenv("TELEGRAM_BOT_TOKEN"))
        have_chat = bool(os.getenv("TELEGRAM_CHAT_ID"))
        logging.warning(
            "No alert was sent. TELEGRAM_BOT_TOKEN found: %s. TELEGRAM_CHAT_ID found: %s. "
            "Check the names in Render > Environment, then redeploy.",
            have_token, have_chat,
        )


if __name__ == "__main__":
    # Test from your laptop:  python notify.py   (set the TELEGRAM_* / email variables first)
    import sys

    sample = {"kind": "test", "allergen": "Soy", "note": "This is a test alert", "scan_id": 0,
              "flagged": ["peanut"], "input_text": None}
    text = build_text(sample)
    any_ok = False
    for name, fn in (("Telegram", _telegram), ("Email", _email)):
        try:
            ok = fn(text)
            if ok:
                print(f"{name}: sent")
                any_ok = True
            else:
                print(f"{name}: skipped (settings not set)")
        except Exception as e:
            reason = str(e)
            resp = getattr(e, "response", None)
            if resp is not None:
                try:
                    reason = f"{e} | {resp.text[:200]}"
                except Exception:
                    pass
            print(f"{name}: FAILED - {reason}")
    if not any_ok:
        print("No alert was sent. Check the messages above.")
        sys.exit(1)