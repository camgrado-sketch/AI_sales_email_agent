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
    # English date without leading zero: "August 6, 2026"
    return f"{now.strftime('%B')} {now.day}, {now.year}"


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
        "DATE": "CURRENT_DATE",
    }
    for alias, canonical in aliases.items():
        if canonical in variables:
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


def generate_for_customer(customer, language=None, missing_vars=None):
    """Generate a single draft for a customer using local template variable replacement."""
    if not config.is_template_confirmed():
        raise RuntimeError("No template confirmed. Please import and confirm a template first (menu 6).")

    customer_id = customer.get("id") or customer.get("customer_id")
    analysis = interaction_analyzer.analyze(customer)

    selected = config.get_selected_template()
    available_templates = template_engine.list_templates()
    if not selected:
        raise RuntimeError(
            "未选择生效模板。请先到菜单 6 [A] 选择要使用的模板。"
        )
    if selected not in available_templates:
        raise RuntimeError(
            f"生效模板 '{selected}' 不存在或已被删除。请先到菜单 6 [A] 重新选择。"
        )
    template_name = selected

    chosen_language = language or analysis.get("language", "cn")

    template_config = template_engine.get_template_config(template_name)
    variables = _build_variables(customer, template_config, language=chosen_language)

    local_missing = []
    html_body, images, files = template_engine.render(
        template_name, variables, language=chosen_language, missing_vars=local_missing
    )

    # Build subject from template config if it contains a declared subject_template,
    # otherwise use the template's subject_template. The template importer writes a
    # subject line into config.yaml as the first rule for reference; we render it here.
    subject = _render_subject(template_config, variables, missing_vars=local_missing)

    if missing_vars is not None:
        missing_vars.extend(local_missing)

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


def _render_subject(template_config, variables, missing_vars=None):
    """Render the subject line template with variables.

    If config.yaml contains a 'subject_template' key, use it; otherwise fall back
    to a generic subject so drafts are never sent with an empty subject.
    Unknown variables are replaced with an empty string and collected for warning.
    """
    subject_template = template_config.get("subject_template", "").strip()
    if not subject_template:
        company = variables.get("CUSTOMER_COMPANY", "")
        return f"Furniture partnership opportunity for {company} | GRADO Contract" if company else "GRADO Contract Partnership Opportunity"

    def replace_var(match):
        var_name = match.group(1).strip().upper()
        if var_name in variables:
            return str(variables[var_name])
        if missing_vars is not None:
            missing_vars.append(var_name)
        return ""

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
    all_missing = set()
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
                local_missing = []
                generate_for_customer(customer, missing_vars=local_missing)
                all_missing.update(local_missing)
                processed_ids.add(customer_id)
                data_store.save_generation_state(processed_ids)
                new_count += 1
            except Exception as e:
                print(f"❌ Failed to generate draft for {customer_id}: {e}")
    except KeyboardInterrupt:
        print("\n⏸️  Generation paused by user.")

    if all_missing:
        print(
            f"\033[93m⚠️  以下变量未能匹配，已替换为空字符串："
            f"{', '.join(sorted(all_missing))}\033[0m"
        )

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
