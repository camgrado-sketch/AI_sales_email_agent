import re

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

    # Chinese-character keywords (exact substring)
    mainland_chinese = (
        "中国", "大陆", "北京", "上海", "广州", "深圳", "成都", "杭州",
        "南京", "武汉", "西安", "重庆", "天津", "苏州",
    )
    if any(k in loc for k in mainland_chinese):
        return "cn"

    # ASCII city names require word boundaries to avoid false positives like "xian" in "asian"
    mainland_cities = (
        "beijing", "shanghai", "guangzhou", "shenzhen", "chengdu", "hangzhou",
        "nanjing", "wuhan", "xian", "chongqing", "tianjin", "suzhou",
    )
    for city in mainland_cities:
        pattern = r"\bxi['’]?an\b" if city == "xian" else rf"\b{re.escape(city)}\b"
        if re.search(pattern, loc):
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


def analyze(customer):
    """
    Analyze a customer and return sales stage + language.

    This function no longer calls an LLM and does not recommend a template type;
    template selection is the user's responsibility via settings.json.

    Args:
        customer: Dict representing a customer row from customers.csv.

    Returns:
        Dict with keys: stage, language, reason.
    """
    customer_id = customer.get("id") or customer.get("customer_id")
    history = data_store.get_customer_history(customer_id)

    stage = _rule_based_stage(history)

    return {
        "stage": stage,
        "reason": f"Rule-based: sent={history['sent_count']}, replies={history['reply_count']}",
        "language": _detect_language(customer.get("location", "")),
    }
