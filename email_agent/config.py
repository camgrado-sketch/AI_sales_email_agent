import json
import os
import re

import yaml
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
# Legacy LLM Configuration (fallback when no MODEL_* blocks are defined)
# -----------------------------------------------------------------------------
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")  # Optional: for OpenAI-compatible endpoints
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# -----------------------------------------------------------------------------
# Sender Identity (used when templates ask for sender details)
# -----------------------------------------------------------------------------
SENDER_NAME = os.getenv("SENDER_NAME", "[Your Name]")
SENDER_TITLE = os.getenv("SENDER_TITLE", "Partnership Manager")
SENDER_COMPANY = os.getenv("SENDER_COMPANY", "GRADO CONTRACT")
SENDER_MARKET_REGION = os.getenv("SENDER_MARKET_REGION", "Global")
SENDER_PHONE = os.getenv("SENDER_PHONE", "")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", EMAIL_ACCOUNT or "")

# Optional external browser command for HTML previews (overrides platform default)
# Examples: "firefox", "google-chrome %s", "wslview %s", "cmd.exe /c start %s"
BROWSER = os.getenv("BROWSER", "").strip()

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
TEMPLATE_IMPORT_DIR = os.path.join(BASE_DIR, "templates", "import")
TEMPLATE_ARCHIVE_DIR = os.path.join(BASE_DIR, "templates", "archive")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
IMAGES_DIR = os.path.join(ASSETS_DIR, "images")
FILES_DIR = os.path.join(ASSETS_DIR, "files")

PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
SKILLS_DIR = os.path.join(BASE_DIR, "skills")

EMAIL_GENERATION_PROMPT_FILE = os.path.join(PROMPTS_DIR, "email_generation_prompt.md")
TEMPLATE_IMPORT_PROMPT_FILE = os.path.join(PROMPTS_DIR, "template_import_prompt.md")
EMAIL_WRITING_SKILL_FILE = os.path.join(SKILLS_DIR, "email_writing_skill.md")
EMAIL_WRITING_SKILL_CONCISE_FILE = os.path.join(SKILLS_DIR, "email_writing_skill_concise.md")

SENDER_PROFILE_FILE = os.path.join(BASE_DIR, "templates", "sender_profile.md")

# ------------------------------------------------------------------------------
# Settings Persistence
# ------------------------------------------------------------------------------
SETTINGS_JSON_FILE = os.path.join(DATA_DIR, "settings.json")
GENERATION_STATE_FILE = os.path.join(DATA_DIR, "generation_state.json")
SENDING_STATE_FILE = os.path.join(DATA_DIR, "sending_state.json")
TEMPLATE_IMPORT_STATE_FILE = os.path.join(DATA_DIR, "template_import_state.json")


def _load_json(path, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


_settings = _load_json(SETTINGS_JSON_FILE)
SKILL_MODE = os.getenv("SKILL_MODE", _settings.get("skill_mode", "concise"))


# -----------------------------------------------------------------------------
# Multi-model configuration
# -----------------------------------------------------------------------------

def load_available_models():
    """Parse numbered MODEL_* blocks from environment variables.

    Supported keys per model (N is 1-based index):
      MODEL_N_NAME, MODEL_N_BASE_URL, MODEL_N_API_KEY, MODEL_N_MODEL,
      MODEL_N_TEMPERATURE

    Falls back to legacy LLM_API_KEY / LLM_BASE_URL / LLM_MODEL if no blocks.
    """
    pattern = re.compile(r"^MODEL_(\d+)_(NAME|BASE_URL|API_KEY|MODEL|TEMPERATURE)$")
    raw = {}
    for key, value in os.environ.items():
        if not value:
            continue
        m = pattern.match(key)
        if not m:
            continue
        idx, field = int(m.group(1)), m.group(2).lower()
        raw.setdefault(idx, {})[field] = value

    models = []
    for idx in sorted(raw):
        cfg = raw[idx]
        if "name" not in cfg or "api_key" not in cfg or "model" not in cfg:
            continue
        try:
            temperature = float(cfg.get("temperature", "0.7"))
        except ValueError:
            temperature = 0.7
        models.append({
            "index": idx,
            "name": cfg["name"],
            "base_url": cfg.get("base_url", ""),
            "api_key": cfg["api_key"],
            "model": cfg["model"],
            "temperature": temperature,
        })

    if not models:
        models.append({
            "index": 0,
            "name": "default",
            "base_url": LLM_BASE_URL or "",
            "api_key": LLM_API_KEY or "",
            "model": LLM_MODEL,
            "temperature": 0.7,
        })

    return models


AVAILABLE_MODELS = load_available_models()


def _active_model_index():
    env_index = os.getenv("ACTIVE_MODEL_INDEX")
    if env_index is not None:
        try:
            return int(env_index)
        except ValueError:
            pass
    return _load_json(SETTINGS_JSON_FILE).get("active_model_index", 0)


def get_active_model():
    """Return the currently selected model config dict."""
    idx = _active_model_index()
    models = load_available_models()
    if not models:
        return None
    if 0 <= idx < len(models):
        return models[idx]
    return models[0]


# -----------------------------------------------------------------------------
# Sender profile (overrides .env identity variables when present)
# -----------------------------------------------------------------------------

def load_sender_profile():
    """Load sender identity from templates/sender_profile.md (YAML frontmatter).

    Falls back to .env values if the file is missing or invalid.
    """
    defaults = {
        "sender_name": SENDER_NAME,
        "sender_title": SENDER_TITLE,
        "sender_company": SENDER_COMPANY,
        "sender_market_region": SENDER_MARKET_REGION,
        "sender_phone": SENDER_PHONE,
        "sender_email": SENDER_EMAIL,
    }
    if not os.path.exists(SENDER_PROFILE_FILE):
        return defaults

    try:
        with open(SENDER_PROFILE_FILE, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return defaults

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                front = yaml.safe_load(parts[1])
                if isinstance(front, dict):
                    for key in defaults:
                        if front.get(key):
                            defaults[key] = str(front[key]).strip()
            except Exception:
                pass

    return defaults


# -----------------------------------------------------------------------------
# Template confirmation state
# -----------------------------------------------------------------------------

def is_template_confirmed():
    """Return True only when the user has confirmed the active template."""
    return bool(_load_json(SETTINGS_JSON_FILE).get("template_confirmed", False))


def get_selected_template():
    """Return the user-selected active template name, or empty string if auto."""
    return str(_load_json(SETTINGS_JSON_FILE).get("selected_template", "")).strip()


def set_selected_template(name):
    """Persist the active template name to settings.json.

    Pass an empty string or None to clear the selection.
    """
    settings = _load_json(SETTINGS_JSON_FILE)
    if name:
        settings["selected_template"] = str(name).strip()
    else:
        settings["selected_template"] = ""
    _save_json(SETTINGS_JSON_FILE, settings)


def get_template_imported_at(template_name):
    """Return the imported-at date string for a template, or '' if unknown."""
    imported_at = _load_json(SETTINGS_JSON_FILE).get("template_imported_at", {})
    return str(imported_at.get(template_name, "")).strip()


def _save_json(path, data):
    """Persist a JSON object, creating parent directories if needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
