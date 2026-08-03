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
    return _read_csv(os.path.join(config.DATA_DIR, "customers.csv"))


def load_email_logs():
    """Load sent email logs."""
    return _read_csv(config.EMAIL_LOGS_FILE)


def load_reply_logs():
    """Load received reply logs."""
    return _read_csv(config.REPLY_LOGS_FILE)


def load_drafts(status=None):
    """Load drafts from drafts.json. Optionally filter by review_status."""
    if not os.path.exists(config.DRAFTS_JSON_FILE):
        return []
    with open(config.DRAFTS_JSON_FILE, "r", encoding="utf-8") as f:
        drafts = json.load(f)
    if status is not None:
        drafts = [d for d in drafts if d.get("review_status") == status]
    return drafts


def save_drafts(drafts):
    """Persist the full drafts list to drafts.json."""
    _ensure_dir(config.DRAFTS_JSON_FILE)
    with open(config.DRAFTS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(drafts, f, ensure_ascii=False, indent=2)


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
