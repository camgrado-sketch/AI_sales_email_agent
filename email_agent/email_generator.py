import os
import re
from datetime import datetime

from email_agent import config, data_store, interaction_analyzer, template_engine


def _extract_first_name(name):
    if not name:
        return ""
    return name.split()[0]


def _current_date(language="cn"):
    """Return a human-readable date string in the requested language."""
    now = datetime.now()
    if language == "cn":
        return now.strftime("%Y年%m月%d日")
    return now.strftime("%B %d, %Y")


def _build_variables(customer, template_config, language="cn"):
    """Build a variables dict from sender profile and customer record.

    All keys are uppercase so they match the {{VAR}} placeholders in templates.
    Missing values fall back to empty strings; the template engine will warn
    about unresolved placeholders.
    """
    sender = config.load_sender_profile()

    variables = {
        # Sender identity
        "SENDER_NAME": sender.get("sender_name", config.SENDER_NAME),
        "SENDER_TITLE": sender.get("sender_title", config.SENDER_TITLE),
        "SENDER_COMPANY": sender.get("sender_company", getattr(config, "SENDER_COMPANY", "")),
        "SENDER_EMAIL": sender.get("sender_email", config.SENDER_EMAIL),
        "SENDER_PHONE": sender.get("sender_phone", config.SENDER_PHONE),
        "SENDER_MARKET_REGION": sender.get("sender_market_region", config.SENDER_MARKET_REGION),
        # Customer identity
        "CUSTOMER_FIRST_NAME": _extract_first_name(customer.get("name", "")),
        "CUSTOMER_NAME": customer.get("name", ""),
        "CUSTOMER_COMPANY": customer.get("company", ""),
        "CUSTOMER_POSITION": customer.get("position", ""),
        "CUSTOMER_LOCATION": customer.get("location", ""),
        "CUSTOMER_INDUSTRY": customer.get("industry", ""),
        # Derived/static
        "CURRENT_DATE": _current_date(language=language),
    }

    # Include any variables declared in config.yaml that have a direct customer key
    declared = template_config.get("variables", [])
    for var in declared:
        key = str(var).strip().upper()
        if key not in variables:
            # Try to map some legacy/customer keys automatically
            customer_key = key.lower().replace("customer_", "")
            if customer_key in customer:
                variables[key] = customer[customer_key]
            else:
                variables[key] = ""

    # Alias mapping: common user-facing placeholder names -> canonical system names.
    # This lets templates imported from external sources use {{company_name}},
    # {{market_region}}, etc., and still resolve correctly.
    aliases = {
        "NAME": "CUSTOMER_NAME",
        "FIRST_NAME": "CUSTOMER_FIRST_NAME",
        "COMPANY": "CUSTOMER_COMPANY",
        "COMPANY_NAME": "CUSTOMER_COMPANY",
        "POSITION": "CUSTOMER_POSITION",
        "LOCATION": "CUSTOMER_LOCATION",
        "INDUSTRY": "CUSTOMER_INDUSTRY",
        "SENDER_COMPANY_NAME": "SENDER_COMPANY",
        "MARKET_REGION": "SENDER_MARKET_REGION",
    }
    for alias, canonical in aliases.items():
        if alias not in variables and canonical in variables:
            variables[alias] = variables[canonical]

    return variables


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


def generate_for_customer(customer, language=None):
    """Generate a single draft for a customer using local template variable replacement."""
    if not config.is_template_confirmed():
        raise RuntimeError("No template confirmed. Please import and confirm a template first (menu 6).")

    customer_id = customer.get("id") or customer.get("customer_id")
    analysis = interaction_analyzer.analyze(customer)

    # User-selected template overrides automatic stage-based selection
    selected = config.get_selected_template()
    available_templates = template_engine.list_templates()
    if selected and selected in available_templates:
        template_name = selected
    else:
        template_name = analysis["template_type"]

    chosen_language = language or analysis.get("language", "cn")
    if template_name not in available_templates:
        if available_templates:
            fallback = available_templates[0]
            print(f"⚠️ 推荐模板 '{template_name}' 未激活，回退使用 '{fallback}'")
            template_name = fallback
        else:
            raise RuntimeError("没有可用的激活模板，请先到菜单 6 导入/确认模板。")

    template_config = template_engine.get_template_config(template_name)
    variables = _build_variables(customer, template_config, language=chosen_language)

    html_body, images, files = template_engine.render(
        template_name, variables, language=chosen_language
    )

    # Build subject from template config if it contains a declared subject_template,
    # otherwise use the template's subject_template. The template importer writes a
    # subject line into config.yaml as the first rule for reference; we render it here.
    subject = _render_subject(template_config, variables)

    draft_id = data_store.generate_draft_id(customer_id)
    draft = {
        "draft_id": draft_id,
        "customer_id": customer_id,
        "email": customer.get("email", ""),
        "template": template_name,
        "stage": analysis["stage"],
        "language": chosen_language,
        "subject": subject,
        "html_body": html_body,
        "text_body": _html_to_text(html_body),
        "images": images,
        "files": files,
        "personalization_note": "",
        "review_status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rendered_by": "local",
    }

    data_store.append_draft(draft)
    return draft


def _render_subject(template_config, variables):
    """Render the subject line template with variables.

    If config.yaml contains a 'subject_template' key, use it; otherwise fall back
    to a generic subject so drafts are never sent with an empty subject.
    """
    subject_template = template_config.get("subject_template", "").strip()
    if not subject_template:
        company = variables.get("CUSTOMER_COMPANY", "")
        return f"Furniture partnership opportunity for {company} | GRADO Contract" if company else "GRADO Contract Partnership Opportunity"

    def replace_var(match):
        var_name = match.group(1).strip().upper()
        return str(variables.get(var_name, match.group(0)))

    return re.sub(r"\{\{([^{}:]+)\}\}", replace_var, subject_template)


def generate_all(customers=None):
    """Generate drafts for all (or provided) customers and save to drafts.json.

    Supports pause/resume: press Ctrl+C to pause. Re-run to resume from the
    next unprocessed customer.
    """
    if not config.is_template_confirmed():
        print("❌ 没有已确认的模板。请先到菜单 6 导入/确认模板。")
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
