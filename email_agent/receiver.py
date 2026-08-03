import email
import imaplib
from email.header import decode_header
from email.utils import parseaddr

from email_agent import config, data_store
from email_agent.logger import log_reply


def decode_str(s):
    """Decode an email header string."""
    if not s:
        return ""
    value, charset = decode_header(s)[0]
    if charset:
        try:
            return value.decode(charset)
        except Exception:
            return str(value)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except Exception:
            return str(value)
    return str(value)


def _extract_text_part(msg, content_type):
    """Extract the first text/* body part from a message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == content_type:
                try:
                    return part.get_payload(decode=True).decode("utf-8", errors="replace")
                except Exception:
                    pass
    elif msg.get_content_type() == content_type:
        try:
            return msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except Exception:
            pass
    return ""


def get_email_body(msg):
    """Extract a readable body from email message (plain text preferred)."""
    body = _extract_text_part(msg, "text/plain")
    if body:
        return body
    body = _extract_text_part(msg, "text/html")
    return body or "Could not extract readable content."


def _get_in_reply_to(msg):
    """Extract Message-ID from In-Reply-To header."""
    in_reply_to = msg.get("In-Reply-To", "")
    if in_reply_to:
        return in_reply_to.strip().strip("<>")
    return ""


def check_replies():
    """Connect to IMAP and check for replies."""
    if not config.EMAIL_ACCOUNT or not config.EMAIL_PASSWORD:
        print("❌ Error: EMAIL_ACCOUNT or EMAIL_PASSWORD not set in .env")
        return

    try:
        print(f"Connecting to IMAP server {config.IMAP_SERVER}...")
        mail = imaplib.IMAP4_SSL(config.IMAP_SERVER, config.IMAP_PORT)
        mail.login(config.EMAIL_ACCOUNT, config.EMAIL_PASSWORD)
        mail.select("inbox")

        status, messages = mail.search(None, "ALL")
        if status != "OK":
            print("No messages found or search failed.")
            return

        email_ids = messages[0].split()
        print(f"Found {len(email_ids)} messages in inbox. Checking for replies...")

        # Build lookup tables from sent logs
        sent_by_message_id = {}
        sent_by_recipient = {}
        for row in data_store.load_email_logs():
            if row.get("status") == "success":
                msg_id = row.get("message_id", "").strip().strip("<>")
                if msg_id:
                    sent_by_message_id[msg_id] = row.get("email_id")
                recipient = row.get("recipient", "").lower()
                if recipient:
                    sent_by_recipient[recipient] = row.get("email_id")

        for e_id in email_ids[-20:]:
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if not isinstance(response_part, tuple):
                    continue
                msg = email.message_from_bytes(response_part[1])

                subject = decode_str(msg.get("Subject"))
                from_header = decode_str(msg.get("From"))
                date = decode_str(msg.get("Date"))
                sender_email = parseaddr(from_header)[1].lower()

                subject_lower = subject.lower()
                is_reply_subject = subject_lower.startswith("re:") or subject_lower.startswith("回复:")

                matched_email_id = None
                in_reply_to = _get_in_reply_to(msg)
                if in_reply_to and in_reply_to in sent_by_message_id:
                    matched_email_id = sent_by_message_id[in_reply_to]
                elif sender_email in sent_by_recipient and is_reply_subject:
                    matched_email_id = sent_by_recipient[sender_email]

                if matched_email_id:
                    print(f"📥 Found Reply from {sender_email}: {subject}")
                    body = get_email_body(msg)
                    short_body = body[:200].replace("\n", " ") + "..." if len(body) > 200 else body.replace("\n", " ")
                    log_reply(matched_email_id, sender_email, date, short_body)

        mail.close()
        mail.logout()
        print("✅ Reply check complete.")

    except Exception as e:
        print(f"❌ IMAP Error: {e}")
