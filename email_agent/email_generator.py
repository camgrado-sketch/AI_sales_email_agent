import json
import os
import re
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
    """Build the system prompt, selecting full or concise skill based on config."""
    skill_file = (
        config.EMAIL_WRITING_SKILL_FILE
        if config.SKILL_MODE == "full"
        else config.EMAIL_WRITING_SKILL_CONCISE_FILE
    )
    writing_skill = _read_file(skill_file)
    generation_prompt = _read_file(config.EMAIL_GENERATION_PROMPT_FILE)
    rules = "\n".join(f"- {r}" for r in template_config.get("rules", []))
    sender = config.load_sender_profile()
    return f"""You are a professional business email writer representing GRADO CONTRACT.

Sender identity (MUST use exactly, do not invent):
- sender_name: {sender.get('sender_name', '')}
- sender_title: {sender.get('sender_title', '')}
- market_region: {sender.get('sender_market_region', '')}

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
- Language: {analysis.get('language', 'cn')}

Fill in the template variables and produce the subject line and personalization note.
Language rule: the email body must be written entirely in the language specified above. Do not mix Chinese and English in the same paragraph."""


def generate_for_customer(customer, language=None):
    """Generate a single draft for a customer and persist it immediately."""
    if not config.is_template_confirmed():
        raise RuntimeError("No template confirmed. Please import and confirm a template first (menu 8).")

    customer_id = customer.get("id") or customer.get("customer_id")
    analysis = interaction_analyzer.analyze(customer)
    template_name = analysis["template_type"]
    chosen_language = language or analysis.get("language", "cn")

    template_config = template_engine.get_template_config(template_name)
    schema = _build_variable_schema(template_config)

    system_prompt = _build_system_prompt(template_config)
    user_prompt = _build_user_prompt(customer, analysis)

    start_time = datetime.now()
    raw = llm_client.complete_json(system_prompt, user_prompt, schema, temperature=0.7)
    result = json.loads(raw["content"])

    variables = result.get("variables", {})
    sender = config.load_sender_profile()
    # Override sender identity strictly from sender_profile/.env
    variables["sender_name"] = sender.get("sender_name", config.SENDER_NAME)
    variables["sender_title"] = sender.get("sender_title", config.SENDER_TITLE)
    variables["market_region"] = sender.get("sender_market_region", config.SENDER_MARKET_REGION)
    variables["customer_first_name"] = _extract_first_name(customer.get("name", ""))
    variables["company_name"] = customer.get("company", "")

    html_body, images = template_engine.render(template_name, variables, language=chosen_language)

    active_model = config.get_active_model()
    draft_id = data_store.generate_draft_id(customer_id)
    draft = {
        "draft_id": draft_id,
        "customer_id": customer_id,
        "email": customer.get("email", ""),
        "template": template_name,
        "stage": analysis["stage"],
        "language": chosen_language,
        "subject": result.get("subject", ""),
        "html_body": html_body,
        "text_body": _html_to_text(html_body),
        "images": images,
        "personalization_note": result.get("personalization_note", ""),
        "review_status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model_used": active_model.get("name", active_model.get("model", "")) if active_model else "",
        "generation_meta": {
            "generation_time": start_time.isoformat(),
            "prompt_tokens": raw["usage"]["prompt_tokens"],
            "completion_tokens": raw["usage"]["completion_tokens"],
            "total_tokens": raw["usage"]["total_tokens"],
        },
    }

    data_store.append_draft(draft)
    return draft


def _html_to_text(html_body):
    """Strip HTML tags and decode entities for a clean text preview."""
    import html

    text = html_body
    # Remove style/script blocks
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", text, flags=re.IGNORECASE)
    # Convert common block tags to newlines
    text = text.replace("\n", " ")
    text = text.replace("</p>", "\n")
    text = text.replace("</div>", "\n")
    text = text.replace("<br>", "\n")
    text = text.replace("<br/>", "\n")
    text = text.replace("<br />", "\n")
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n\s*\n", "\n", text)
    return text.strip()


def _is_skipped_customer(customer):
    """Customers whose name starts with '#' are skipped for generation/sending."""
    name = (customer.get("name") or "").strip()
    return name.startswith("#")


def generate_all(customers=None):
    """Generate drafts for all (or provided) customers and save to drafts.json.

    Supports pause/resume: press Ctrl+C to pause. Re-run to resume from the
    next unprocessed customer.
    """
    if not config.is_template_confirmed():
        print("❌ No template confirmed. Please import and confirm a template first (menu 8).")
        return []

    if customers is None:
        customers = data_store.load_customers()

    processed_ids = data_store.load_generation_state()
    if processed_ids:
        print(f"⏳ Resuming generation. {len(processed_ids)} customer(s) already processed.")

    new_count = 0
    try:
        for customer in customers:
            customer_id = customer.get("id") or customer.get("customer_id")
            if not customer_id:
                continue
            if customer_id in processed_ids:
                print(f"⏭️  Skipping {customer.get('name')} ({customer_id}) — already generated.")
                continue
            if _is_skipped_customer(customer):
                print(f"🚫 Skipping {customer.get('name')} ({customer_id}) — marked with #.")
                processed_ids.add(customer_id)
                data_store.save_generation_state(processed_ids)
                continue

            print(f"Generating draft for {customer.get('name')} at {customer.get('company')}...")
            try:
                generate_for_customer(customer)
                processed_ids.add(customer_id)
                data_store.save_generation_state(processed_ids)
                new_count += 1
            except Exception as e:
                print(f"❌ Failed to generate draft for {customer_id}: {e}")
    except KeyboardInterrupt:
        print("\n⏸️  Generation paused by user.")

    total_customers = len([c for c in customers if (c.get("id") or c.get("customer_id"))])
    all_drafts = data_store.load_drafts()
    print(f"✅ Saved {new_count} new draft(s). Total drafts: {len(all_drafts)}")
    if processed_ids and len(processed_ids) >= total_customers:
        data_store.clear_generation_state()
    else:
        print("💡 Tip: Run option 1 again to resume from where you left off.")
    return all_drafts


if __name__ == "__main__":
    generate_all()
