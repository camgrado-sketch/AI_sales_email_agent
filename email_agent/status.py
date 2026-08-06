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
        messages.append("缺少邮箱账号或密码（请检查 .env）")
    if not config.get_active_model():
        messages.append("未配置 LLM 模型（请检查 .env）")
    customers = data_store.load_customers()
    if not customers:
        messages.append("未找到客户（data/customers.csv）")
    templates = template_engine.list_templates()
    if not templates:
        messages.append("未找到邮件模板（templates/email/）")
    if not config.is_template_confirmed():
        messages.append("模板未确认（请使用菜单 8）")

    if messages:
        return {
            "color": "red",
            "label": "阻塞",
            "messages": messages,
        }

    # Yellow conditions
    yellow_reasons = []
    try:
        if template_importer.detect_changes():
            yellow_reasons.append("templates/import/ 中有新模板文件待处理")
    except Exception:
        pass

    if data_store.load_generation_state():
        yellow_reasons.append("生成任务已暂停或进行中")
    if data_store.load_sending_state().get("remaining_draft_ids"):
        yellow_reasons.append("发送任务已暂停或进行中")
    if _has_pending_or_approved_drafts():
        yellow_reasons.append("有待审核或待发送的草稿")
    if _has_unsent_approved():
        yellow_reasons.append("有已审核通过的草稿等待发送")

    if yellow_reasons:
        return {
            "color": "yellow",
            "label": "就绪",
            "messages": yellow_reasons,
        }

    # Green
    return {
        "color": "green",
        "label": "全部就绪",
        "messages": ["模板已确认，所有任务已就绪"],
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
