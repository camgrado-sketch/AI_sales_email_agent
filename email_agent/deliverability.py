import difflib
import random
import time
from datetime import datetime, timedelta

import dns.resolver

from email_agent import config


def _today_send_count(send_history):
    today = datetime.now().strftime("%Y-%m-%d")
    return sum(
        1
        for row in send_history
        if row.get("send_time", "").startswith(today) and row.get("status") == "success"
    )


def check_spf(domain):
    """Check if the domain has an SPF record. Returns True if found."""
    try:
        answers = dns.resolver.resolve(domain, "TXT")
        for rdata in answers:
            txt = rdata.to_text()
            if "v=spf1" in txt:
                return True
        return False
    except Exception:
        return False


def is_similar_to_recent(draft, recent_emails, threshold=None):
    """
    Compare draft body to recently sent emails.

    Args:
        draft: Draft dict with 'html_body' or 'text_body'.
        recent_emails: List of sent email log dicts with 'subject' and 'error_msg'.
        threshold: Similarity threshold (defaults to config.SIMILARITY_THRESHOLD).

    Returns:
        True if any recent email is too similar.
    """
    threshold = threshold if threshold is not None else config.SIMILARITY_THRESHOLD
    draft_text = draft.get("text_body") or draft.get("html_body") or ""
    for row in recent_emails:
        recent_text = " ".join(filter(None, [row.get("subject", ""), row.get("error_msg", "")]))
        if not recent_text:
            continue
        ratio = difflib.SequenceMatcher(None, draft_text, recent_text).ratio()
        if ratio >= threshold:
            return True
    return False


def can_send(draft, send_history):
    """
    Determine whether a draft can be sent right now.

    Returns:
        (allowed: bool, reason: str)
    """
    recipient = draft.get("email", "")

    # Demo whitelist
    if config.DEMO_MODE and recipient not in config.ALLOWED_TEST_EMAILS:
        return False, f"Blocked by Demo Mode: {recipient} not in ALLOWED_TEST_EMAILS"

    # Email credentials
    if not config.EMAIL_ACCOUNT or not config.EMAIL_PASSWORD:
        return False, "EMAIL_ACCOUNT or EMAIL_PASSWORD not set"

    # Daily send limit
    if _today_send_count(send_history) >= config.MAX_DAILY_SENDS:
        return False, f"Daily send limit reached ({config.MAX_DAILY_SENDS})"

    # Similarity check against last 24h successful sends
    cutoff = datetime.now() - timedelta(hours=24)
    recent = [
        row
        for row in send_history
        if row.get("status") == "success"
        and _parse_time(row.get("send_time")) >= cutoff
    ]
    if is_similar_to_recent(draft, recent):
        return False, "Draft is too similar to a recently sent email"

    # SPF check (warning only)
    if "@" in config.EMAIL_ACCOUNT:
        domain = config.EMAIL_ACCOUNT.split("@")[1]
        if not check_spf(domain):
            print(f"⚠️ Warning: SPF record not found for {domain}. Deliverability may suffer.")

    return True, "OK"


def _parse_time(time_str):
    """Parse send_time string into datetime; returns epoch on failure."""
    try:
        return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime(1970, 1, 1)


def wait_before_next():
    """Sleep for a random interval between sends."""
    delay = random.uniform(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)
    print(f"⏳ Waiting {delay:.1f} seconds before next email...")
    time.sleep(delay)
    return delay
