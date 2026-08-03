import json
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
# Sender Identity (used when templates ask for sender details)
# -----------------------------------------------------------------------------
SENDER_NAME = os.getenv("SENDER_NAME", "[Your Name]")
SENDER_TITLE = os.getenv("SENDER_TITLE", "Partnership Manager")
SENDER_MARKET_REGION = os.getenv("SENDER_MARKET_REGION", "Global")

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
EMAIL_WRITING_SKILL_CONCISE_FILE = os.path.join(SKILLS_DIR, "email_writing_skill_concise.md")

# ------------------------------------------------------------------------------
# Settings Persistence
# ------------------------------------------------------------------------------
SETTINGS_JSON_FILE = os.path.join(DATA_DIR, "settings.json")


def _load_settings():
    if os.path.exists(SETTINGS_JSON_FILE):
        try:
            with open(SETTINGS_JSON_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


_settings = _load_settings()
SKILL_MODE = os.getenv("SKILL_MODE", _settings.get("skill_mode", "concise"))

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
