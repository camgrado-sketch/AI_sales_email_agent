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


def get_template_path(template_name, language=None):
    """Return the HTML path for a template, optionally choosing a language variant."""
    dir_path = os.path.join(config.TEMPLATES_DIR, template_name)
    if language:
        lang_path = os.path.join(dir_path, f"template_{language}.html")
        if os.path.exists(lang_path):
            return lang_path
    return os.path.join(dir_path, "template.html")


def list_template_languages(template_name):
    """List available language variants for a template."""
    dir_path = os.path.join(config.TEMPLATES_DIR, template_name)
    if not os.path.exists(dir_path):
        return []
    languages = []
    if os.path.exists(os.path.join(dir_path, "template.html")):
        languages.append("default")
    for fname in os.listdir(dir_path):
        m = re.match(r"template_([a-z]+)\.html$", fname)
        if m:
            languages.append(m.group(1))
    return languages


def _load_template_html(template_name, language=None):
    path = get_template_path(template_name, language)
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


def _find_file(file_name):
    """Search for a file by base name under assets/files."""
    if not os.path.exists(config.FILES_DIR):
        return None
    # Common file extensions; also try exact name first.
    candidates = [file_name]
    base, ext = os.path.splitext(file_name)
    if not ext:
        candidates.extend(
            [f"{file_name}{e}" for e in (".pdf", ".docx", ".doc", ".xlsx", ".xls", ".zip", ".txt")]
        )
    for candidate in candidates:
        path = os.path.join(config.FILES_DIR, candidate)
        if os.path.exists(path):
            return path
    return None


def _normalize_variables(variables):
    """Normalize variable dict keys to uppercase for consistent placeholder matching."""
    normalized = {}
    for key, value in variables.items():
        normalized[str(key).strip().upper()] = value
    return normalized


# Preview-time placeholder chrome (dashed boxes with label text) must not leak
# into outbound emails; reduce them to the bare placeholder token first.
_IMAGE_CHROME_RE = re.compile(
    r"<div[^>]*(?:class=\"[^\"]*placeholder[^\"]*\""
    r"|style=\"[^\"]*dashed[^\"]*\")[^>]*>"
    r"(?:(?!</div>).)*?\{\{IMAGE:[^}]+\}\}(?:(?!</div>).)*?</div>",
    re.DOTALL,
)

_ASCII_CID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _strip_image_placeholder_chrome(html):
    """Replace dashed placeholder boxes with the bare {{IMAGE:...}} token."""
    def unwrap(match):
        return re.search(r"\{\{IMAGE:[^}]+\}\}", match.group(0)).group(0)

    return _IMAGE_CHROME_RE.sub(unwrap, html)


def _make_cid(image_name, used_cids):
    """Return an RFC 2392-safe ASCII Content-ID for the given image name.

    Non-ASCII cids (e.g. Chinese template names) break Content-ID matching in
    mail clients, so they are replaced with a sequential ASCII token.
    """
    if image_name.isascii() and _ASCII_CID_RE.match(image_name):
        cid = image_name
    else:
        cid = f"img_{len(used_cids) + 1:02d}"
        while cid in used_cids:
            cid += "x"
    used_cids.add(cid)
    return cid


def render(template_name, variables, language=None, missing_vars=None):
    """
    Render an HTML email template.

    Args:
        template_name: Name of the template directory under templates/email.
        variables: Dict of placeholder values. Keys are normalized to uppercase.
        language: Optional language code to select template_<lang>.html.
        missing_vars: Optional list to collect names of unresolved simple variables.

    Returns:
        Tuple of (html_body, images, files) where images/files are lists of dicts
        with metadata for inline attachments or download links.
    """
    html = _load_template_html(template_name, language)
    html = _strip_image_placeholder_chrome(html)
    variables = _normalize_variables(variables)
    images = []
    files = []
    cid_by_name = {}
    used_cids = set()

    # Replace image placeholders: {{IMAGE:name}}
    def replace_image(match):
        image_name = match.group(1).strip()
        cid = cid_by_name.get(image_name)
        if cid is None:
            cid = _make_cid(image_name, used_cids)
            cid_by_name[image_name] = cid
        image_path = _find_image_file(image_name)
        if image_path:
            images.append({"cid": cid, "path": image_path})
            return (
                f'<img src="cid:{cid}" alt="{image_name}" '
                'style="width:100%;height:auto;display:block;">'
            )
        # Missing asset: leave a comment and warn
        return f"<!-- Missing image asset: {image_name} -->"

    html = re.sub(r"\{\{IMAGE:([^}]+)\}\}", replace_image, html)

    # Replace file placeholders: {{FILE:name}}
    def replace_file(match):
        file_name = match.group(1).strip()
        file_path = _find_file(file_name)
        if file_path:
            files.append({"name": file_name, "path": file_path})
            # Render as a local download link. In production the user should replace
            # the file:// URL with a publicly accessible URL or use SMTP attachments.
            abs_path = os.path.abspath(file_path)
            display_name = os.path.basename(file_path)
            return (
                f'<a href="file://{abs_path}" style="color:#0d6efd;">'
                f'📎 {display_name}'
                f'</a>'
            )
        else:
            return f"<!-- Missing file asset: {file_name} -->"

    html = re.sub(r"\{\{FILE:([^}]+)\}\}", replace_file, html)

    # Replace simple variables: {{var}}
    def replace_var(match):
        var_name = match.group(1).strip().upper()
        if var_name in variables:
            return str(variables[var_name])
        if missing_vars is not None:
            missing_vars.append(var_name)
        # Do not leak raw placeholders into outbound emails.
        return ""

    html = re.sub(r"\{\{([^{}:]+)\}\}", replace_var, html)

    return html, images, files
