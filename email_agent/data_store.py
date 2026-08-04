import csv
import json
import os
from datetime import datetime

from email_agent import config


def _ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, mode="r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path, rows, fieldnames):
    _ensure_dir(path)
    with open(path, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def load_customers():
    """Load customer master data from customers.csv."""
    rows = _read_csv(os.path.join(config.DATA_DIR, "customers.csv"))
    return [r for r in rows if (r.get("id") or "").strip() or (r.get("name") or "").strip()]


def load_email_logs():
    """Load sent email logs."""
    return _read_csv(config.EMAIL_LOGS_FILE)


def get_sent_draft_ids():
    """Return draft_ids already logged as successfully sent."""
    return {
        row.get("email_id", "")
        for row in load_email_logs()
        if row.get("status") == "success" and row.get("email_id")
    }


def load_reply_logs():
    """Load received reply logs."""
    return _read_csv(config.REPLY_LOGS_FILE)


def load_drafts(status=None):
    """Load drafts from drafts.json. Optionally filter by review_status."""
    if not os.path.exists(config.DRAFTS_JSON_FILE) or os.path.getsize(config.DRAFTS_JSON_FILE) == 0:
        return []
    try:
        with open(config.DRAFTS_JSON_FILE, "r", encoding="utf-8") as f:
            drafts = json.load(f)
    except json.JSONDecodeError:
        return []
    if status is not None:
        drafts = [d for d in drafts if d.get("review_status") == status]
    return drafts


def save_drafts(drafts):
    """Persist the full drafts list to drafts.json."""
    _ensure_dir(config.DRAFTS_JSON_FILE)
    with open(config.DRAFTS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(drafts, f, ensure_ascii=False, indent=2)


def append_draft(draft):
    """Append a single draft to drafts.json immediately after generation."""
    drafts = load_drafts()
    drafts.append(draft)
    save_drafts(drafts)


def update_draft_status(draft_id, status):
    """Update the review_status of a single draft by draft_id."""
    drafts = load_drafts()
    for draft in drafts:
        if draft.get("draft_id") == draft_id:
            draft["review_status"] = status
            break
    save_drafts(drafts)


def get_customer_history(customer_id):
    """Aggregate email and reply history for a customer."""
    emails = [r for r in load_email_logs() if r.get("customer_id") == customer_id]
    replies = [r for r in load_reply_logs() if r.get("email_id") in {e.get("email_id") for e in emails}]
    return {
        "customer_id": customer_id,
        "emails": emails,
        "replies": replies,
        "sent_count": len(emails),
        "reply_count": len(replies),
        "last_sent": emails[-1].get("send_time") if emails else None,
        "last_reply": replies[-1].get("receive_time") if replies else None,
    }


def append_email_log(row):
    """Append a single row to email_logs.csv."""
    _ensure_dir(config.EMAIL_LOGS_FILE)
    if not os.path.exists(config.EMAIL_LOGS_FILE):
        _write_csv(config.EMAIL_LOGS_FILE, [], config.EMAIL_LOG_HEADERS)
    with open(config.EMAIL_LOGS_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=config.EMAIL_LOG_HEADERS)
        writer.writerow({k: row.get(k, "") for k in config.EMAIL_LOG_HEADERS})


def append_reply_log(row):
    """Append a single row to reply_logs.csv."""
    _ensure_dir(config.REPLY_LOGS_FILE)
    if not os.path.exists(config.REPLY_LOGS_FILE):
        _write_csv(config.REPLY_LOGS_FILE, [], config.REPLY_LOG_HEADERS)
    with open(config.REPLY_LOGS_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=config.REPLY_LOG_HEADERS)
        writer.writerow({k: row.get(k, "") for k in config.REPLY_LOG_HEADERS})


def generate_draft_id(customer_id):
    """Generate a unique draft_id based on date and customer_id."""
    return f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{customer_id}"


# ------------------------------------------------------------------------------
# Generation pause/resume state
# ------------------------------------------------------------------------------
_GENERATION_STATE_FILE = os.path.join(config.DATA_DIR, "generation_state.json")


def load_generation_state():
    """Load the set of already-processed customer_ids from generation_state.json."""
    if not os.path.exists(_GENERATION_STATE_FILE) or os.path.getsize(_GENERATION_STATE_FILE) == 0:
        return set()
    try:
        with open(_GENERATION_STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except json.JSONDecodeError:
        return set()


def save_generation_state(processed_ids):
    """Persist the set of processed customer_ids to generation_state.json."""
    _ensure_dir(_GENERATION_STATE_FILE)
    with open(_GENERATION_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(processed_ids), f, ensure_ascii=False, indent=2)


def clear_generation_state():
    """Remove generation_state.json when all customers are done."""
    if os.path.exists(_GENERATION_STATE_FILE):
        os.remove(_GENERATION_STATE_FILE)


# ------------------------------------------------------------------------------
# Sending pause/resume state
# ------------------------------------------------------------------------------
_SENDING_STATE_FILE = config.SENDING_STATE_FILE


def load_sending_state():
    """Load sending state dict; return empty defaults if missing/corrupt."""
    if not os.path.exists(_SENDING_STATE_FILE) or os.path.getsize(_SENDING_STATE_FILE) == 0:
        return {"started_at": "", "sent_draft_ids": [], "remaining_draft_ids": []}
    try:
        with open(_SENDING_STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            if not isinstance(state, dict):
                return {"started_at": "", "sent_draft_ids": [], "remaining_draft_ids": []}
            return {
                "started_at": state.get("started_at", ""),
                "sent_draft_ids": list(state.get("sent_draft_ids", [])),
                "remaining_draft_ids": list(state.get("remaining_draft_ids", [])),
            }
    except json.JSONDecodeError:
        return {"started_at": "", "sent_draft_ids": [], "remaining_draft_ids": []}


def save_sending_state(state):
    """Persist sending state dict to sending_state.json."""
    _ensure_dir(_SENDING_STATE_FILE)
    with open(_SENDING_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def clear_sending_state():
    """Remove sending_state.json when the queue is exhausted."""
    if os.path.exists(_SENDING_STATE_FILE):
        os.remove(_SENDING_STATE_FILE)


# ------------------------------------------------------------------------------
# Template import state (checksums)
# ------------------------------------------------------------------------------
_TEMPLATE_IMPORT_STATE_FILE = config.TEMPLATE_IMPORT_STATE_FILE


def load_template_import_state():
    """Load template import checksum state."""
    if not os.path.exists(_TEMPLATE_IMPORT_STATE_FILE) or os.path.getsize(_TEMPLATE_IMPORT_STATE_FILE) == 0:
        return {}
    try:
        with open(_TEMPLATE_IMPORT_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def save_template_import_state(state):
    """Persist template import checksum state."""
    _ensure_dir(_TEMPLATE_IMPORT_STATE_FILE)
    with open(_TEMPLATE_IMPORT_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------------------
# Settings persistence
# ------------------------------------------------------------------------------

def load_settings():
    """Load user settings from settings.json."""
    if not os.path.exists(config.SETTINGS_JSON_FILE) or os.path.getsize(config.SETTINGS_JSON_FILE) == 0:
        return {}
    try:
        with open(config.SETTINGS_JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_settings(settings):
    """Persist user settings to settings.json."""
    _ensure_dir(config.SETTINGS_JSON_FILE)
    with open(config.SETTINGS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------------------
# Draft deletion helpers
# ------------------------------------------------------------------------------

def delete_draft(draft_id):
    """Remove a single draft by draft_id from drafts.json and from generation state."""
    drafts = load_drafts()
    target = next((d for d in drafts if d.get("draft_id") == draft_id), None)
    drafts = [d for d in drafts if d.get("draft_id") != draft_id]
    save_drafts(drafts)
    if target:
        customer_id = target.get("customer_id")
        if customer_id:
            processed_ids = load_generation_state()
            processed_ids.discard(customer_id)
            save_generation_state(processed_ids)


def clear_drafts():
    """Remove all drafts and reset generation state so generation can start fresh."""
    save_drafts([])
    clear_generation_state()
