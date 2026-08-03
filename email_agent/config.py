import os
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env file
load_dotenv(find_dotenv())

# -----------------------------------------------------------------------------
# SMTP / IMAP Configuration (Tencent Enterprise Email)
# -----------------------------------------------------------------------------
SMTP_SERVER = "smtp.exmail.qq.com"
SMTP_PORT = 465
IMAP_SERVER = "imap.exmail.qq.com"
IMAP_PORT = 993

EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Must be the client authorization code

# -----------------------------------------------------------------------------
# LLM Configuration
# -----------------------------------------------------------------------------
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")  # Optional: for OpenAI-compatible endpoints
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5-mini")

# -----------------------------------------------------------------------------
# Safety Settings for Demo Phase
# -----------------------------------------------------------------------------
DEMO_MODE = True
ALLOWED_TEST_EMAILS = [
    "camgrado@gmail.com",
    "camgrado@outlook.com",
    "cam@gradodesign.hk",
]

# -----------------------------------------------------------------------------
# Deliverability / Rate Limiting
# -----------------------------------------------------------------------------
MAX_DAILY_SENDS = 50
MIN_DELAY_SECONDS = 30
MAX_DELAY_SECONDS = 120  # Demo interval; production can be raised to 600 (10 min)
SIMILARITY_THRESHOLD = 0.90

# -----------------------------------------------------------------------------
# File / Directory Paths
# -----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DRAFTS_DIR = os.path.join(DATA_DIR, "drafts")
DRAFTS_FILE = os.path.join(DRAFTS_DIR, "drafts.csv")
DRAFTS_JSON_FILE = os.path.join(DATA_DIR, "drafts.json")
EMAIL_LOGS_FILE = os.path.join(DATA_DIR, "email_logs.csv")
REPLY_LOGS_FILE = os.path.join(DATA_DIR, "reply_logs.csv")

TEMPLATES_DIR = os.path.join(BASE_DIR, "templates", "email")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
IMAGES_DIR = os.path.join(ASSETS_DIR, "images")

PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
SKILLS_DIR = os.path.join(BASE_DIR, "skills")

EMAIL_GENERATION_PROMPT_FILE = os.path.join(PROMPTS_DIR, "email_generation_prompt.md")
EMAIL_WRITING_SKILL_FILE = os.path.join(SKILLS_DIR, "email_writing_skill.md")

# -----------------------------------------------------------------------------
# Logging Headers
# -----------------------------------------------------------------------------
EMAIL_LOG_HEADERS = [
    "email_id",
    "customer_id",
    "recipient",
    "subject",
    "send_time",
    "status",
    "error_msg",
    "message_id",
]

REPLY_LOG_HEADERS = [
    "email_id",
    "sender",
    "receive_time",
    "content",
    "status",
]
