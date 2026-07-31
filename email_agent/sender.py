import smtplib
import csv
import time
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import make_msgid
from datetime import datetime

from email_agent import config
from email_agent.logger import log_email_send

def create_email_message(recipient, subject, body):
    """Create a MIME email message."""
    msg = MIMEMultipart()
    msg['From'] = config.EMAIL_ACCOUNT
    msg['To'] = recipient
    msg['Subject'] = Header(subject, 'utf-8')
    
    # Generate a unique Message-ID for reply tracking
    msg_id = make_msgid(domain=config.EMAIL_ACCOUNT.split('@')[1] if '@' in config.EMAIL_ACCOUNT else 'local')
    msg['Message-ID'] = msg_id
    
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    return msg, msg_id

def send_email(recipient, subject, body, customer_id):
    """Send a single email and log the result."""
    # Safety check for Demo mode
    if config.DEMO_MODE and recipient not in config.ALLOWED_TEST_EMAILS:
        print(f"⚠️ BLOCKED: {recipient} is not in ALLOWED_TEST_EMAILS (Demo Mode is ON)")
        log_email_send(f"BLOCKED-{datetime.now().strftime('%Y%m%d%H%M%S')}", customer_id, recipient, subject, "failed", "Blocked by Demo Mode")
        return False
        
    if not config.EMAIL_ACCOUNT or not config.EMAIL_PASSWORD:
        print("❌ Error: EMAIL_ACCOUNT or EMAIL_PASSWORD not set in .env")
        return False

    msg, msg_id = create_email_message(recipient, subject, body)
    
    # Generate a simple email_id for our logs (date-time based)
    email_id = f"{datetime.now().strftime('%Y%m%d')}-{customer_id}"
    
    try:
        print(f"Connecting to {config.SMTP_SERVER}...")
        # Use SMTP_SSL for port 465
        server = smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT)
        server.login(config.EMAIL_ACCOUNT, config.EMAIL_PASSWORD)
        
        print(f"Sending email to {recipient}...")
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Success: Email sent to {recipient}")
        # Log success (saving the actual Message-ID in error_msg field temporarily for reference, or we could add a dedicated column)
        log_email_send(email_id, customer_id, recipient, subject, "success", f"MsgID:{msg_id}")
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Failed: Could not send to {recipient}. Error: {error_msg}")
        log_email_send(email_id, customer_id, recipient, subject, "failed", error_msg)
        return False

def process_drafts():
    """Read drafts.csv and send approved emails."""
    try:
        with open(config.DRAFTS_FILE, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            drafts = list(reader)
    except FileNotFoundError:
        print(f"❌ Error: Drafts file not found at {config.DRAFTS_FILE}")
        return
        
    to_send = [d for d in drafts if d.get('review_status', '').lower() == 'pass']
    
    if not to_send:
        print("No approved drafts (review_status='pass') found to send.")
        return
        
    print(f"Found {len(to_send)} approved drafts to send.")
    
    for i, draft in enumerate(to_send):
        customer_id = draft.get('customer_id', f'UNKNOWN-{i}')
        recipient = draft.get('email', '') # Ensure drafts.csv has the email column, or join with customers.csv
        subject = draft.get('subject', '')
        body = draft.get('body', '')
        
        if not recipient:
            print(f"⚠️ Skipping {customer_id}: No email address provided in draft.")
            continue
            
        success = send_email(recipient, subject, body, customer_id)
        
        # Random interval between sends (Policy: 30s to 10m, using shorter interval for testing)
        if i < len(to_send) - 1 and success:
            delay = random.uniform(30, 120) # 30s to 2 mins for demo
            print(f"Waiting {delay:.1f} seconds before next email to avoid spam filters...")
            time.sleep(delay)
