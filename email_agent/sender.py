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


def _is_skipped_customer(draft):
    """Drafts for customers whose original name started with '#' are skipped."""
    # Try to look up the customer record; fall back to parsing draft fields.
    customer_id = draft.get("customer_id", "")
    for customer in data_store.load_customers():
        cid = customer.get("id") or customer.get("customer_id")
        if cid == customer_id:
            name = (customer.get("name") or "").strip()
            return name.startswith("#")
    return False


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
        mime_image.add_header("Content-Disposition", "inline", filename=os.path.basename(path))
        msg.attach(mime_image)


def check_draft_images(drafts):
    """Return a list of image cids whose referenced files are missing on disk."""
    missing = []
    seen = set()
    for draft in drafts:
        for image in draft.get("images", []):
            path = image.get("path")
            cid = image.get("cid") or path or "unknown"
            if cid in seen:
                continue
            seen.add(cid)
            if not path or not os.path.exists(path):
                missing.append(cid)
    return missing


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
    email_id = draft.get("draft_id") or f"{datetime.now().strftime('%Y%m%d')}-{customer_id}"

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


def _save_sending_state(sent_ids, remaining_drafts):
    data_store.save_sending_state({
        "started_at": datetime.now().isoformat(),
        "sent_draft_ids": list(sent_ids),
        "remaining_draft_ids": [d.get("draft_id") for d in remaining_drafts if d.get("draft_id")],
    })


def process_queue(drafts=None):
    """Read approved drafts and send them with rate limiting.

    Supports pause/resume via Ctrl+C. State is stored in sending_state.json.
    """
    if not config.is_template_confirmed():
        print("❌ No template confirmed. Please import and confirm a template first (menu 8).")
        return

    if drafts is None:
        drafts = data_store.load_drafts()

    approved = [d for d in drafts if d.get("review_status", "").lower() in ("approved", "pass")]
    if not approved:
        print("No approved drafts found to send.")
        data_store.clear_sending_state()
        return

    state = data_store.load_sending_state()
    sent_ids = set(state.get("sent_draft_ids", []))
    remaining_ids = set(state.get("remaining_draft_ids", []))

    if remaining_ids:
        # Resume from saved state
        to_send = [d for d in approved if d.get("draft_id") in remaining_ids]
        if not to_send:
            to_send = approved
    else:
        to_send = approved

    # Skip already-sent and # customers
    already_sent = sent_ids | data_store.get_sent_draft_ids()
    to_send = [d for d in to_send if d.get("draft_id") not in already_sent and not _is_skipped_customer(d)]

    if not to_send:
        print("All approved drafts have already been sent.")
        data_store.clear_sending_state()
        return

    print(f"Found {len(to_send)} approved draft(s) to send. Press Ctrl+C to pause.")

    missing_images = check_draft_images(to_send)
    if missing_images:
        print(
            f"\033[93m⚠️  以下图片文件缺失，邮件正文可能出现空白："
            f"{', '.join(missing_images)}\033[0m"
        )
        confirm = input("图片缺失，是否仍继续发送？ (y/N): ").strip().lower()
        if confirm != "y":
            print("已取消发送。")
            return

    remaining = list(to_send)
    try:
        for i, draft in enumerate(to_send):
            draft_id = draft.get("draft_id")
            remaining = to_send[i + 1:]
            print(f"\n[Ctrl+C to pause] Sending {i + 1}/{len(to_send)}: {draft.get('email')}")
            success = send_email(draft)
            if success:
                sent_ids.add(draft_id)
            _save_sending_state(sent_ids, remaining)

            if remaining:
                deliverability.wait_before_next()

        data_store.clear_sending_state()
        print("\n✅ All approved drafts processed.")

    except KeyboardInterrupt:
        print("\n⏸️  Sending paused by user.")
        _save_sending_state(sent_ids, remaining)
        print("💡 Tip: Run option 3 again to resume from where you left off.")


# Backward-compatible alias for legacy CLI callers
process_drafts = process_queue
