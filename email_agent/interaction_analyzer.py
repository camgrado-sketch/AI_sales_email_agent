from email_agent import config, data_store


def _detect_language(location):
    """Determine email language from customer location.

    Explicit suffixes override everything:
      - (中文) / (Chinese)  -> cn
      - (英文) / (English)  -> en

    Without suffix:
      - Mainland China -> cn
      - Hong Kong, Taiwan, and other overseas -> en
    """
    loc = (location or "").lower()
    if "(中文)" in loc or "(chinese)" in loc:
        return "cn"
    if "(英文)" in loc or "(english)" in loc:
        return "en"
    mainland_cities = (
        "中国", "大陆", "北京", "上海", "广州", "深圳", "成都", "杭州",
        "beijing", "shanghai", "guangzhou", "shenzhen", "chengdu", "hangzhou",
        "nanjing", "wuhan", "xian", "xi'an", "chongqing", "tianjin", "suzhou",
    )
    if any(k in loc for k in mainland_cities):
        return "cn"
    if any(k in loc for k in ("香港", "台湾", "hong kong", "taiwan", "macau", "澳门")):
        return "en"
    return "en"


def _rule_based_stage(history):
    """Determine sales stage from successful email/reply history."""
    successful_sent = sum(
        1 for e in history.get("emails", []) if e.get("status") == "success"
    )
    if history["reply_count"] > 0:
        return "replied"
    if successful_sent >= 2:
        return "follow_up_no_reply"
    if successful_sent == 1:
        return "contacted_no_reply"
    return "new_lead"


def _strategy_for_stage(stage):
    """Return a rule-based strategy note for the given stage."""
    return {
        "new_lead": "Introduce GRADO and request permission to share a tailored overview.",
        "contacted_no_reply": "Add one specific reason GRADO is relevant and ask a low-friction question.",
        "follow_up_no_reply": "Provide credible proof and a very low-barrier ask; pause if still no reply.",
        "replied": "Respond to the customer's reply and propose a clear next step.",
    }.get(stage, "")


def analyze(customer):
    """
    Analyze a customer and return sales stage + template recommendation.

    This function no longer calls an LLM; it relies on deterministic rules
    based on email/reply history and customer location.

    Args:
        customer: Dict representing a customer row from customers.csv.

    Returns:
        Dict with keys: stage, template_type, strategy, reason, language.
    """
    customer_id = customer.get("id") or customer.get("customer_id")
    history = data_store.get_customer_history(customer_id)

    stage = _rule_based_stage(history)
    template_type = {
        "new_lead": "initial_contact",
        "contacted_no_reply": "follow_up",
        "follow_up_no_reply": "final_note",
        "replied": "follow_up",
    }.get(stage, "initial_contact")

    return {
        "stage": stage,
        "template_type": template_type,
        "strategy": _strategy_for_stage(stage),
        "reason": f"Rule-based: sent={history['sent_count']}, replies={history['reply_count']}",
        "language": _detect_language(customer.get("location", "")),
    }
