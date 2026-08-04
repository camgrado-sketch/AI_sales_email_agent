import os

from email_agent import config, data_store, template_engine, template_importer


def _has_pending_or_approved_drafts():
    return bool(data_store.load_drafts(status="pending") or data_store.load_drafts(status="approved"))


def _has_unsent_approved():
    approved = data_store.load_drafts(status="approved")
    if not approved:
        return False
    sent_ids = data_store.get_sent_draft_ids()
    return any(d.get("draft_id") not in sent_ids for d in approved)


def compute_status():
    """Compute the top-of-screen status indicator.

    Returns:
        {"color": "red" | "yellow" | "green", "label": str, "messages": list[str]}
    """
    messages = []

    # Red conditions
    if not config.EMAIL_ACCOUNT or not config.EMAIL_PASSWORD:
        messages.append("Missing email account or password (.env)")
    if not config.get_active_model():
        messages.append("No LLM model configured (.env)")
    customers = data_store.load_customers()
    if not customers:
        messages.append("No customers found (data/customers.csv)")
    templates = template_engine.list_templates()
    if not templates:
        messages.append("No email templates found (templates/email/)")
    if not config.is_template_confirmed():
        messages.append("Template not confirmed (menu 8)")

    if messages:
        return {
            "color": "red",
            "label": "BLOCKED",
            "messages": messages,
        }

    # Yellow conditions
    yellow_reasons = []
    try:
        if template_importer.detect_changes():
            yellow_reasons.append("New template files in templates/import/ waiting to be processed")
    except Exception:
        pass

    if data_store.load_generation_state():
        yellow_reasons.append("Generation paused or in progress")
    if data_store.load_sending_state().get("remaining_draft_ids"):
        yellow_reasons.append("Sending paused or in progress")
    if _has_pending_or_approved_drafts():
        yellow_reasons.append("Pending or approved drafts need review/sending")
    if _has_unsent_approved():
        yellow_reasons.append("Approved drafts waiting to be sent")

    if yellow_reasons:
        return {
            "color": "yellow",
            "label": "READY",
            "messages": yellow_reasons,
        }

    # Green
    return {
        "color": "green",
        "label": "ALL CLEAR",
        "messages": ["Template confirmed and all work up to date"],
    }


def _color_code(color):
    return {
        "red": "\033[91m",
        "yellow": "\033[93m",
        "green": "\033[92m",
    }.get(color, "")


def print_status_bar():
    """Print a colored status bar suitable for the terminal."""
    status = compute_status()
    code = _color_code(status["color"])
    reset = "\033[0m"
    print("-" * 60)
    print(f"{code}[{status['label']}] {', '.join(status['messages'])}{reset}")
    print("-" * 60)
