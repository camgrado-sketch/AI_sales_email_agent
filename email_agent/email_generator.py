import json
import os
from datetime import datetime

from email_agent import config, data_store, interaction_analyzer, llm_client, template_engine


def _read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_first_name(name):
    if not name:
        return ""
    return name.split()[0]


def _build_variable_schema(template_config):
    """Build a JSON schema describing the variables the LLM must return."""
    variables = template_config.get("variables", [])
    properties = {
        "subject": {"type": "string"},
        "personalization_note": {"type": "string"},
        "variables": {
            "type": "object",
            "properties": {v: {"type": "string"} for v in variables},
            "required": variables,
            "additionalProperties": False,
        },
    }
    return {
        "name": "email_variables",
        "type": "object",
        "properties": properties,
        "required": ["subject", "personalization_note", "variables"],
        "additionalProperties": False,
    }


def _build_system_prompt(template_config):
    writing_skill = _read_file(config.EMAIL_WRITING_SKILL_FILE)
    generation_prompt = _read_file(config.EMAIL_GENERATION_PROMPT_FILE)
    rules = "\n".join(f"- {r}" for r in template_config.get("rules", []))
    return f"""You are a professional business email writer representing GRADO CONTRACT.

Follow the brand writing skill below strictly:

{writing_skill}

Generation instructions:

{generation_prompt}

Template-specific rules:
{rules}

Return ONLY a JSON object matching the provided schema."""


def _build_user_prompt(customer, analysis):
    return f"""Customer information:
- ID: {customer.get('id')}
- Name: {customer.get('name')}
- Company: {customer.get('company')}
- Position: {customer.get('position')}
- Industry: {customer.get('industry')}
- Location: {customer.get('location')}
- Company type: {customer.get('company_type')}

Sales stage analysis:
- Stage: {analysis['stage']}
- Recommended template: {analysis['template_type']}
- Strategy: {analysis['strategy']}

Fill in the template variables and produce the subject line and personalization note.
Language rule: use Chinese for mainland China customers and English for international customers."""


def generate_for_customer(customer):
    """Generate a single draft for a customer."""
    customer_id = customer.get("id") or customer.get("customer_id")
    analysis = interaction_analyzer.analyze(customer)
    template_name = analysis["template_type"]

    template_config = template_engine.get_template_config(template_name)
    schema = _build_variable_schema(template_config)

    system_prompt = _build_system_prompt(template_config)
    user_prompt = _build_user_prompt(customer, analysis)

    raw = llm_client.complete_json(system_prompt, user_prompt, schema, temperature=0.7)
    result = json.loads(raw)

    variables = result.get("variables", {})
    # Inject sender defaults if not provided by LLM
    variables.setdefault("sender_name", config.SENDER_NAME)
    variables.setdefault("sender_title", config.SENDER_TITLE)
    variables.setdefault("market_region", config.SENDER_MARKET_REGION)
    variables.setdefault("customer_first_name", _extract_first_name(customer.get("name", "")))
    variables.setdefault("company_name", customer.get("company", ""))

    html_body, images = template_engine.render(template_name, variables)

    draft_id = data_store.generate_draft_id(customer_id)
    return {
        "draft_id": draft_id,
        "customer_id": customer_id,
        "email": customer.get("email", ""),
        "template": template_name,
        "stage": analysis["stage"],
        "subject": result.get("subject", ""),
        "html_body": html_body,
        "text_body": _html_to_text(html_body),
        "images": images,
        "personalization_note": result.get("personalization_note", ""),
        "review_status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _html_to_text(html_body):
    """Very basic HTML-to-text fallback for CLI preview."""
    text = html_body
    text = text.replace("\n", " ")
    text = text.replace("</p>", "\n")
    text = text.replace("</div>", "\n")
    text = text.replace("<br>", "\n")
    text = text.replace("<br/>", "\n")
    text = text.replace("<br />", "\n")
    # Strip remaining tags
    import re
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    return text.strip()


def generate_all(customers=None):
    """Generate drafts for all (or provided) customers and save to drafts.json.

    Supports pause/resume: press Ctrl+C to pause. Re-run to resume from the
    next unprocessed customer.
    """
    if customers is None:
        customers = data_store.load_customers()

    processed_ids = data_store.load_generation_state()
    if processed_ids:
        print(f"⏳ Resuming generation. {len(processed_ids)} customer(s) already processed.")

    drafts = []
    try:
        for customer in customers:
            customer_id = customer.get("id") or customer.get("customer_id")
            if not customer_id:
                continue
            if customer_id in processed_ids:
                print(f"⏭️  Skipping {customer.get('name')} ({customer_id}) — already generated.")
                continue

            print(f"Generating draft for {customer.get('name')} at {customer.get('company')}...")
            try:
                draft = generate_for_customer(customer)
                drafts.append(draft)
                processed_ids.add(customer_id)
                data_store.save_generation_state(processed_ids)
            except Exception as e:
                print(f"❌ Failed to generate draft for {customer_id}: {e}")
    except KeyboardInterrupt:
        print("\n⏸️  Generation paused by user.")

    # Merge with existing drafts to avoid overwriting approved/edited drafts
    existing = data_store.load_drafts()
    existing_ids = {d.get("draft_id") for d in existing}
    merged = [d for d in existing if d.get("draft_id") in existing_ids]
    for draft in drafts:
        if draft["draft_id"] not in existing_ids:
            merged.append(draft)

    data_store.save_drafts(merged)
    total_customers = len([c for c in customers if (c.get("id") or c.get("customer_id"))])
    print(f"✅ Saved {len(drafts)} new draft(s). Total drafts: {len(merged)}")
    if processed_ids and len(processed_ids) >= total_customers:
        data_store.clear_generation_state()
    else:
        print("💡 Tip: Run option 1 again to resume from where you left off.")
    return drafts


if __name__ == "__main__":
    generate_all()
