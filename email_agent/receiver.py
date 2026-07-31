import imaplib
import email
from email.header import decode_header
import csv
import os
from datetime import datetime

from email_agent import config
from email_agent.logger import log_reply

def decode_str(s):
    """Decode email header string."""
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
            return value.decode('utf-8')
        except Exception:
            return str(value)
    return str(value)

def get_email_body(msg):
    """Extract plain text body from email message."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    return part.get_payload(decode=True).decode()
                except Exception:
                    pass
    else:
        content_type = msg.get_content_type()
        if content_type == "text/plain":
            try:
                return msg.get_payload(decode=True).decode()
            except Exception:
                pass
    return "Could not extract text/plain content."

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
        
        # Search for all emails (in a real system, we'd search for UNSEEN or since last check date)
        status, messages = mail.search(None, "ALL")
        
        if status != "OK":
            print("No messages found or search failed.")
            return
            
        email_ids = messages[0].split()
        print(f"Found {len(email_ids)} messages in inbox. Checking for replies...")
        
        # Load sent email logs to match replies
        sent_emails = {}
        if os.path.exists(config.EMAIL_LOGS_FILE):
            with open(config.EMAIL_LOGS_FILE, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('status') == 'success':
                        # Key by recipient to do a basic match (better to use Message-ID if available)
                        sent_emails[row.get('recipient')] = row.get('email_id')
        
        for e_id in email_ids[-20:]: # Check only the last 20 emails for demo
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    subject = decode_str(msg.get("Subject"))
                    sender = decode_str(msg.get("From"))
                    date = decode_str(msg.get("Date"))
                    
                    # Basic reply detection: Sender is in our sent logs AND subject starts with Re:
                    sender_email = sender.split('<')[-1].strip('>') if '<' in sender else sender
                    
                    is_reply = False
                    matched_email_id = "UNKNOWN"
                    
                    if sender_email in sent_emails and (subject.lower().startswith("re:") or subject.lower().startswith("回复:")):
                        is_reply = True
                        matched_email_id = sent_emails[sender_email]
                    
                    if is_reply:
                        print(f"📥 Found Reply from {sender_email}: {subject}")
                        body = get_email_body(msg)
                        # Truncate body for logging
                        short_body = body[:200].replace('\n', ' ') + '...' if len(body) > 200 else body.replace('\n', ' ')
                        log_reply(matched_email_id, sender_email, date, short_body)
                        
        mail.close()
        mail.logout()
        print("✅ Reply check complete.")
        
    except Exception as e:
        print(f"❌ IMAP Error: {str(e)}")
