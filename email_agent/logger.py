import os
from datetime import datetime

from email_agent import config, data_store


def init_log_files():
    """Initialize CSV log files with headers if they don't exist."""
    os.makedirs(os.path.dirname(config.EMAIL_LOGS_FILE), exist_ok=True)

    if not os.path.exists(config.EMAIL_LOGS_FILE):
        data_store._write_csv(config.EMAIL_LOGS_FILE, [], config.EMAIL_LOG_HEADERS)

    if not os.path.exists(config.REPLY_LOGS_FILE):
        data_store._write_csv(config.REPLY_LOGS_FILE, [], config.REPLY_LOG_HEADERS)


def log_email_send(email_id, customer_id, recipient, subject, status, error_msg="", message_id=""):
    """Log an email sending attempt."""
    send_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data_store.append_email_log({
        "email_id": email_id,
        "customer_id": customer_id,
        "recipient": recipient,
        "subject": subject,
        "send_time": send_time,
        "status": status,
        "error_msg": error_msg,
        "message_id": message_id,
    })


def log_reply(email_id, sender, receive_time, content, status="replied"):
    """Log a received reply."""
    data_store.append_reply_log({
        "email_id": email_id,
        "sender": sender,
        "receive_time": receive_time,
        "content": content,
        "status": status,
    })
