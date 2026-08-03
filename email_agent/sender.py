import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.header import Header
from email.utils import make_msgid
from datetime import datetime

import os

from email_agent import config, data_store, deliverability
from email_agent.logger import log_email_send


def _attach_images(msg, images):
    """Attach inline images with Content-ID headers."""
    for image in images:
        path = image.get("path")
        cid = image.get("cid")
        if not path or not cid or not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            img_data = f.read()
        mime_image = MIMEImage(img_data)
        mime_image.add_header("Content-ID", f"<{cid}>")
        mime_image.add_header("Content-Disposition", "inline", filename=config.os.path.basename(path))
        msg.attach(mime_image)


def create_email_message(draft):
    """Create a MIME email message from a draft dict."""
    recipient = draft.get("email", "")
    subject = draft.get("subject", "")
    html_body = draft.get("html_body", "")
    text_body = draft.get("text_body", "")
    images = draft.get("images", [])

    msg = MIMEMultipart("related")
    msg["From"] = config.EMAIL_ACCOUNT
    msg["To"] = recipient
    msg["Subject"] = Header(subject, "utf-8")

    domain = config.EMAIL_ACCOUNT.split("@")[1] if "@" in config.EMAIL_ACCOUNT else "local"
    msg_id = make_msgid(domain=domain)
    msg["Message-ID"] = msg_id

    # Alternative plain text part for clients that don't support HTML
    alternative = MIMEMultipart("alternative")
    if text_body:
        alternative.attach(MIMEText(text_body, "plain", "utf-8"))
    alternative.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alternative)

    _attach_images(msg, images)
    return msg, msg_id


def send_email(draft):
    """Send a single email and log the result."""
    customer_id = draft.get("customer_id", "UNKNOWN")
    recipient = draft.get("email", "")
    subject = draft.get("subject", "")

    send_history = data_store.load_email_logs()
    allowed, reason = deliverability.can_send(draft, send_history)
    if not allowed:
        print(f"⚠️ BLOCKED: {reason}")
        log_email_send(
            email_id=f"BLOCKED-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            customer_id=customer_id,
            recipient=recipient,
            subject=subject,
            status="failed",
            error_msg=reason,
            message_id="",
        )
        return False

    msg, msg_id = create_email_message(draft)
    email_id = f"{datetime.now().strftime('%Y%m%d')}-{customer_id}"

    try:
        print(f"Connecting to {config.SMTP_SERVER}...")
        server = smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT)
        server.login(config.EMAIL_ACCOUNT, config.EMAIL_PASSWORD)

        print(f"Sending email to {recipient}...")
        server.send_message(msg)
        server.quit()

        print(f"✅ Success: Email sent to {recipient}")
        log_email_send(
            email_id=email_id,
            customer_id=customer_id,
            recipient=recipient,
            subject=subject,
            status="success",
            error_msg="",
            message_id=msg_id,
        )
        return True

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Failed: Could not send to {recipient}. Error: {error_msg}")
        log_email_send(
            email_id=email_id,
            customer_id=customer_id,
            recipient=recipient,
            subject=subject,
            status="failed",
            error_msg=error_msg,
            message_id="",
        )
        return False


def process_queue(drafts=None):
    """Read approved drafts and send them with rate limiting."""
    if drafts is None:
        drafts = data_store.load_drafts(status="approved")

    to_send = [d for d in drafts if d.get("review_status", "").lower() == "approved"]

    if not to_send:
        print("No approved drafts found to send.")
        return

    print(f"Found {len(to_send)} approved draft(s) to send.")

    for i, draft in enumerate(to_send):
        success = send_email(draft)
        if i < len(to_send) - 1 and success:
            deliverability.wait_before_next()


# Backward-compatible alias for legacy CLI callers
process_drafts = process_queue
