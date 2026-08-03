import os
import re

import yaml

from email_agent import config


def list_templates():
    """Return a list of available template names under templates/email."""
    if not os.path.exists(config.TEMPLATES_DIR):
        return []
    return [
        name
        for name in os.listdir(config.TEMPLATES_DIR)
        if os.path.isdir(os.path.join(config.TEMPLATES_DIR, name))
    ]


def get_template_config(template_name):
    """Load the YAML config for a template."""
    path = os.path.join(config.TEMPLATES_DIR, template_name, "config.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Template config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_template_html(template_name):
    path = os.path.join(config.TEMPLATES_DIR, template_name, "template.html")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Template HTML not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _find_image_file(image_name):
    """Search for an image file by base name under assets/images."""
    if not os.path.exists(config.IMAGES_DIR):
        return None
    for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        candidate = os.path.join(config.IMAGES_DIR, f"{image_name}{ext}")
        if os.path.exists(candidate):
            return candidate
    return None


def render(template_name, variables):
    """
    Render an HTML email template.

    Args:
        template_name: Name of the template directory under templates/email.
        variables: Dict of placeholder values.

    Returns:
        Tuple of (html_body, images) where images is a list of dicts with
        'cid' and 'path' keys for inline image attachments.
    """
    html = _load_template_html(template_name)
    images = []

    # Replace image placeholders: {{IMAGE:name}}
    def replace_image(match):
        image_name = match.group(1).strip()
        image_path = _find_image_file(image_name)
        if image_path:
            images.append({"cid": image_name, "path": image_path})
            return f'<img src="cid:{image_name}" alt="{image_name}" style="width:100%;height:auto;display:block;">'
        else:
            # Missing asset: leave a comment and warn
            return f"<!-- Missing image asset: {image_name} -->"

    html = re.sub(r"\{\{IMAGE:([^}]+)\}\}", replace_image, html)

    # Replace simple variables: {{var}}
    def replace_var(match):
        var_name = match.group(1).strip()
        if var_name in variables:
            return str(variables[var_name])
        return match.group(0)

    html = re.sub(r"\{\{([^{}:]+)\}\}", replace_var, html)

    return html, images


def template_for_stage(stage):
    """
    Pick a default template name for a given sales stage.

    Args:
        stage: Sales stage string.

    Returns:
        Template name string.
    """
    mapping = {
        "new_lead": "initial_contact",
        "contacted_no_reply": "follow_up",
        "follow_up_no_reply": "final_note",
        "replied": "follow_up",
    }
    return mapping.get(stage, "initial_contact")
