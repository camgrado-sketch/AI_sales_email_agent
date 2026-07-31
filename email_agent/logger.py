import csv
import os
from datetime import datetime
from email_agent.config import EMAIL_LOGS_FILE, REPLY_LOGS_FILE

def init_log_files():
    """Initialize CSV log files with headers if they don't exist."""
    # Ensure data directory exists
    os.makedirs(os.path.dirname(EMAIL_LOGS_FILE), exist_ok=True)
    
    # Initialize email logs
    if not os.path.exists(EMAIL_LOGS_FILE):
        with open(EMAIL_LOGS_FILE, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['email_id', 'customer_id', 'recipient', 'subject', 'send_time', 'status', 'error_msg'])
            
    # Initialize reply logs
    if not os.path.exists(REPLY_LOGS_FILE):
        with open(REPLY_LOGS_FILE, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['email_id', 'sender', 'receive_time', 'content', 'status'])

def log_email_send(email_id, customer_id, recipient, subject, status, error_msg=""):
    """Log an email sending attempt."""
    send_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(EMAIL_LOGS_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([email_id, customer_id, recipient, subject, send_time, status, error_msg])

def log_reply(email_id, sender, receive_time, content, status="replied"):
    """Log a received reply."""
    with open(REPLY_LOGS_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([email_id, sender, receive_time, content, status])
