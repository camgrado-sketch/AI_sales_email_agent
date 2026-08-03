import json

from email_agent import config, data_store, llm_client


def _rule_based_stage(history):
    """Determine sales stage from email/reply history."""
    if history["reply_count"] > 0:
        return "replied"
    if history["sent_count"] >= 2:
        return "follow_up_no_reply"
    if history["sent_count"] == 1:
        return "contacted_no_reply"
    return "new_lead"


def _llm_strategy(customer, history):
    """
    Ask the LLM for a strategy and template recommendation.
    Falls back to a default if no API key is configured.
    """
    if not config.LLM_API_KEY:
        return None

    system_prompt = """You are a sales strategy assistant for GRADO CONTRACT, a furniture brand.
Analyze the provided customer profile and email history, then recommend the next outreach action.
Respond ONLY with a JSON object matching the schema."""

    user_prompt = f"""Customer profile:
{json.dumps(customer, ensure_ascii=False, indent=2)}

Interaction history:
{json.dumps(history, ensure_ascii=False, indent=2)}

Rules:
- If never contacted, stage is "new_lead" and template is "initial_contact".
- If contacted once with no reply, stage is "contacted_no_reply" and template is "follow_up".
- If contacted two or more times with no reply, stage is "follow_up_no_reply" and template is "final_note".
- If the customer has replied, stage is "replied" and template is "follow_up".

Return JSON with:
- "stage": one of new_lead, contacted_no_reply, follow_up_no_reply, replied
- "template_type": one of initial_contact, follow_up, final_note
- "strategy": a one-sentence strategy note for the email generator
- "reason": a one-sentence reason for the recommendation
"""

    schema = {
        "name": "stage_recommendation",
        "type": "object",
        "properties": {
            "stage": {"type": "string"},
            "template_type": {"type": "string"},
            "strategy": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["stage", "template_type", "strategy", "reason"],
        "additionalProperties": False,
    }

    try:
        raw = llm_client.complete_json(system_prompt, user_prompt, schema, temperature=0.3)
        return json.loads(raw)
    except Exception:
        return None


def analyze(customer):
    """
    Analyze a customer and return sales stage + template recommendation.

    Args:
        customer: Dict representing a customer row from customers.csv.

    Returns:
        Dict with keys: stage, template_type, strategy, reason.
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

    result = {
        "stage": stage,
        "template_type": template_type,
        "strategy": "",
        "reason": f"Rule-based: sent={history['sent_count']}, replies={history['reply_count']}",
    }

    llm_result = _llm_strategy(customer, history)
    if llm_result:
        result.update(llm_result)
    else:
        result["strategy"] = {
            "new_lead": "Introduce GRADO and request permission to share a tailored overview.",
            "contacted_no_reply": "Add one specific reason GRADO is relevant and ask a low-friction question.",
            "follow_up_no_reply": "Provide credible proof and a very low-barrier ask; pause if still no reply.",
            "replied": "Respond to the customer's reply and propose a clear next step.",
        }.get(stage, "")

    return result
