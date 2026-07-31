import os
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env file
load_dotenv(find_dotenv())

# SMTP Configuration (Tencent Enterprise Email)
SMTP_SERVER = "smtp.exmail.qq.com"
SMTP_PORT = 465

# IMAP Configuration (Tencent Enterprise Email)
IMAP_SERVER = "imap.exmail.qq.com"
IMAP_PORT = 993

# Credentials
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") # Must be the client authorization code, not login password

# Safety Settings for Demo Phase
# Set to True to only allow sending to domains/emails listed in ALLOWED_TEST_EMAILS
DEMO_MODE = True 
ALLOWED_TEST_EMAILS = [
    # Add your test emails here, e.g., "test1@example.com"
]

# File Paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DRAFTS_FILE = os.path.join(DATA_DIR, "drafts", "drafts.csv")
EMAIL_LOGS_FILE = os.path.join(DATA_DIR, "email_logs.csv")
REPLY_LOGS_FILE = os.path.join(DATA_DIR, "reply_logs.csv")
