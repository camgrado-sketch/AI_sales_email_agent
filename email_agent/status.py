from email_agent import config, data_store


def _send_state(template_name):
    """Return a human-readable send-state label for the selected template."""
    if not template_name or template_name == "（未选择）":
        return "未选择模板"

    approved = [
        d for d in data_store.load_drafts(status="approved")
        if d.get("template") == template_name
    ]
    if not approved:
        return "未发送"

    sent_ids = data_store.get_sent_draft_ids()
    remaining = [d for d in approved if d.get("draft_id") not in sent_ids]
    if not remaining:
        return "已全部发送"
    return f"部分发送（剩余 {len(remaining)} 封）"


def compute_status():
    """Compute the top-of-screen status indicator.

    Returns a dict matching the PRD v2.0 status bar schema:
        {
            "template_name": str,
            "imported_at": str,
            "confirmed": bool,
            "send_state": str,
            "unseen_replies": int,
            "color": "red" | "yellow" | "green",
            "label": str,
        }
    """
    template_name = config.get_selected_template() or "（未选择）"
    imported_at = (
        config.get_template_imported_at(template_name)
        if template_name != "（未选择）" else ""
    )
    confirmed = config.is_template_confirmed() and template_name != "（未选择）"
    send_state = _send_state(template_name)
    unseen_replies = data_store.count_unviewed_replies()

    if not confirmed:
        color, label = "red", "阻塞"
    elif unseen_replies > 0 or send_state.startswith("部分发送"):
        color, label = "yellow", "就绪"
    else:
        color, label = "green", "全部就绪"

    return {
        "template_name": template_name,
        "imported_at": imported_at,
        "confirmed": confirmed,
        "send_state": send_state,
        "unseen_replies": unseen_replies,
        "color": color,
        "label": label,
    }


def _color_code(color):
    return {
        "red": "\033[91m",
        "yellow": "\033[93m",
        "green": "\033[92m",
    }.get(color, "")


def print_status_bar():
    """Print the two-line PRD v2.0 status bar."""
    status = compute_status()
    code = _color_code(status["color"])
    reset = "\033[0m"

    name_line = f"模板: {status['template_name']}"
    if status["imported_at"]:
        name_line += f" ({status['imported_at']})"
    name_line += " ✅已确认" if status["confirmed"] else " ⚠️未确认（需到菜单6确认后才能生成）"

    reply_text = f"{status['unseen_replies']} 封"
    state_line = f"发送: {status['send_state']}  |  回复: {reply_text}"

    print("-" * 60)
    print(f"{code}{name_line}{reset}")
    print(f"{code}{state_line}{reset}")
    print("-" * 60)
