import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

from email_agent import config, data_store, llm_client, template_engine


class ImportCandidate:
    def __init__(self, path, checksum):
        self.path = path
        self.checksum = checksum
        self.filename = os.path.basename(path)
        self.ext = os.path.splitext(path)[1].lower()


def _ensure_dirs():
    os.makedirs(config.TEMPLATE_IMPORT_DIR, exist_ok=True)
    os.makedirs(config.TEMPLATE_ARCHIVE_DIR, exist_ok=True)


def _file_checksum(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_template_name(name):
    """Normalize a template name from a filename or user input."""
    name = re.sub(r"[^\w\-]", "_", name).strip("_").lower()
    return name or "initial_contact"


def _template_name_from_filename(filename):
    """Try to infer template name from filename; fallback to initial_contact."""
    base = os.path.splitext(filename)[0].lower()
    for candidate in ("initial_contact", "follow_up", "final_note"):
        if candidate in base:
            return candidate
    # Strip language suffixes
    base = re.sub(r"_(cn|en|zh|eng|chinese|english)$", "", base)
    return _normalize_template_name(base)


# ------------------------------------------------------------------------------
# Scanning and change detection
# ------------------------------------------------------------------------------

def scan_import_folder():
    """Return a list of ImportCandidate for supported files in the import folder."""
    _ensure_dirs()
    candidates = []
    for root, _dirs, files in os.walk(config.TEMPLATE_IMPORT_DIR):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in (".md", ".docx", ".pdf"):
                continue
            path = os.path.join(root, fname)
            candidates.append(ImportCandidate(path, _file_checksum(path)))
    return candidates


def detect_changes():
    """Return import candidates whose checksum differs from the stored state."""
    state = data_store.load_template_import_state()
    stored = state.get("files", {})
    changed = []
    for cand in scan_import_folder():
        rel = os.path.relpath(cand.path, config.TEMPLATE_IMPORT_DIR)
        if stored.get(rel) != cand.checksum:
            changed.append(cand)
    return changed


def save_import_state():
    """Snapshot current import folder checksums."""
    state = data_store.load_template_import_state()
    state["last_scan_at"] = datetime.now().isoformat()
    state["files"] = {
        os.path.relpath(cand.path, config.TEMPLATE_IMPORT_DIR): cand.checksum
        for cand in scan_import_folder()
    }
    data_store.save_template_import_state(state)


# ------------------------------------------------------------------------------
# Content extraction -> Markdown
# ------------------------------------------------------------------------------

def extract_to_markdown(path):
    """Extract a Markdown-like text representation from md/docx/pdf."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".md":
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    if ext == ".docx":
        return _docx_to_markdown(path)
    if ext == ".pdf":
        return _pdf_to_markdown(path)
    raise ValueError(f"Unsupported template file format: {ext}")


def _docx_to_markdown(path):
    try:
        import docx
    except ImportError as e:
        raise RuntimeError(
            "python-docx is required for .docx import. Run: pip install python-docx"
        ) from e

    doc = docx.Document(path)
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "").lower()
        if "heading" in style:
            level = re.search(r"\d", style)
            prefix = "#" * (int(level.group(0)) if level else 1)
            lines.append(f"{prefix} {text}")
        else:
            lines.append(text)
    return "\n\n".join(lines)


def _pdf_to_markdown(path):
    try:
        import pdfplumber
    except ImportError as e:
        raise RuntimeError(
            "pdfplumber is required for PDF import. Run: pip install pdfplumber"
        ) from e

    paragraphs = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            # Split into paragraphs by blank lines
            for para in re.split(r"\n\s*\n", text.strip()):
                para = " ".join(line.strip() for line in para.splitlines() if line.strip())
                if para:
                    paragraphs.append(para)
    return "\n\n".join(paragraphs)


# ------------------------------------------------------------------------------
# Language detection
# ------------------------------------------------------------------------------

def detect_language(markdown, filename=""):
    """Detect whether the markdown is primarily Chinese (cn) or English (en)."""
    base = os.path.splitext(filename)[0].lower()
    if any(k in base for k in ("cn", "chinese", "zh", "中文")):
        return "cn"
    if any(k in base for k in ("en", "english", "eng", "英文")):
        return "en"

    sample = markdown[:2000]
    try:
        from langdetect import detect
        lang = detect(sample)
        if lang.startswith("zh"):
            return "cn"
        if lang == "en":
            return "en"
    except Exception:
        pass

    # Fallback: CJK ratio
    cjk = len(re.findall(r"[一-鿿]", sample))
    total = len(sample.strip())
    if total == 0:
        return "en"
    return "cn" if cjk / total > 0.1 else "en"


# ------------------------------------------------------------------------------
# Markdown -> HTML template merge
# ------------------------------------------------------------------------------

def _strip_markdown(text):
    """Convert Markdown inline syntax to plain text."""
    text = re.sub(r"#{1,6}\s+", "", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"[image: \1]", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.strip()


def _editable_text_nodes(soup):
    """Yield text nodes in the body that are safe to overwrite."""
    body = soup.body or soup
    for elem in body.find_all(string=True):
        parent = elem.parent
        if parent and parent.name in ("style", "script"):
            continue
        text = str(elem)
        if "{{" in text and "}}" in text:
            continue
        if parent and parent.name in ("img", "a"):
            continue
        if not elem.strip():
            continue
        yield elem


def merge_markdown_into_template(template_name, markdown, language=None):
    """Merge plain-text blocks from markdown into existing template.html."""
    template_path = template_engine.get_template_path(template_name)
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    nodes = list(_editable_text_nodes(soup))

    # Split markdown into paragraphs; preserve headings as strong-ish blocks
    blocks = []
    for block in re.split(r"\n\s*\n", markdown.strip()):
        block = block.strip()
        if not block:
            continue
        # Convert heading lines to bold text
        lines = []
        for line in block.splitlines():
            m = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
            if m:
                lines.append(f"**{m.group(2)}**")
            else:
                lines.append(line)
        blocks.append(_strip_markdown(" ".join(lines)))

    # Replace nodes in order
    for i, node in enumerate(nodes):
        if i >= len(blocks):
            break
        new_text = blocks[i]
        if new_text:
            node.replace_with(new_text)

    # Append remaining blocks as new paragraphs at the end of body
    if len(blocks) > len(nodes):
        body = soup.body or soup
        for block in blocks[len(nodes):]:
            p = soup.new_tag("p")
            p.string = block
            body.append(p)

    return str(soup)


# ------------------------------------------------------------------------------
# Bilingual generation
# ------------------------------------------------------------------------------

def generate_missing_language(template_name, source_lang, target_lang):
    """Translate the current template.html into the target language."""
    template_path = template_engine.get_template_path(template_name)
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Extract text nodes, translate them, then re-inject
    soup = BeautifulSoup(html, "html.parser")
    nodes = [n for n in _editable_text_nodes(soup) if n.strip()]

    texts = [str(n) for n in nodes]
    if not texts:
        translated = []
    else:
        system_prompt = (
            "You are a professional translator. Translate the following text segments "
            f"from {'Chinese' if source_lang == 'cn' else 'English'} to "
            f"{'Chinese' if target_lang == 'cn' else 'English'}. "
            "Preserve the number of segments and return them as a JSON array of strings. "
            "Do not add explanations."
        )
        user_prompt = "\n---SEGMENT---\n".join(texts)
        schema = {
            "name": "translations",
            "type": "object",
            "properties": {
                "translations": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
            "required": ["translations"],
            "additionalProperties": False,
        }
        try:
            result = llm_client.complete_json(system_prompt, user_prompt, schema)
            translated = json.loads(result["content"]).get("translations", [])
        except Exception:
            translated = []

    for i, node in enumerate(nodes):
        if i < len(translated) and translated[i]:
            node.replace_with(translated[i])

    target_path = os.path.join(
        config.TEMPLATES_DIR, template_name, f"template_{target_lang}.html"
    )
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(str(soup))
    return target_path


# ------------------------------------------------------------------------------
# Archiving and activation
# ------------------------------------------------------------------------------

def archive_current_template(template_name):
    """Copy the current active template directory to templates/archive/YYYY/MM/DD/."""
    src = os.path.join(config.TEMPLATES_DIR, template_name)
    if not os.path.exists(src):
        return None
    now = datetime.now()
    stamp = now.strftime("%H%M%S")
    dst = os.path.join(
        config.TEMPLATE_ARCHIVE_DIR,
        now.strftime("%Y"),
        now.strftime("%m"),
        now.strftime("%d"),
        f"{template_name}_{stamp}",
    )
    shutil.copytree(src, dst)
    return dst


def has_unfinished_work(template_name=None):
    """Check whether the current template still has pending or unsent work."""
    reasons = []

    if data_store.load_generation_state():
        reasons.append("generation is in progress or paused")

    pending = data_store.load_drafts(status="pending")
    if pending:
        reasons.append(f"{len(pending)} pending draft(s) waiting for review")

    approved = data_store.load_drafts(status="approved")
    if approved:
        sent_ids = data_store.get_sent_draft_ids()
        unsent = [d for d in approved if d.get("draft_id") not in sent_ids]
        if unsent:
            reasons.append(f"{len(unsent)} approved email(s) not yet sent")

    if reasons:
        return True, "; ".join(reasons)
    return False, ""


def activate_template(template_name, candidate_path, force=False):
    """
    Import a candidate file into an active template directory.

    Steps:
      1. Archive current template.
      2. Extract candidate to Markdown.
      3. Merge Markdown into template.html (source language).
      4. Generate the missing language variant if needed.
      5. Mark template as unconfirmed (user must confirm before use).
    """
    if not force:
        has_work, reason = has_unfinished_work(template_name)
        if has_work:
            raise RuntimeError(
                f"Cannot import new template: current template has unfinished work ({reason}). "
                "Pass force=True or clear drafts/generation state first."
            )

    _ensure_dirs()
    archive_path = archive_current_template(template_name)

    markdown = extract_to_markdown(candidate_path)
    source_lang = detect_language(markdown, os.path.basename(candidate_path))

    target_dir = os.path.join(config.TEMPLATES_DIR, template_name)
    os.makedirs(target_dir, exist_ok=True)

    # Ensure a config.yaml exists for new templates
    config_path = os.path.join(target_dir, "config.yaml")
    if not os.path.exists(config_path):
        _write_default_config(config_path, template_name)

    merged_html = merge_markdown_into_template(template_name, markdown, language=source_lang)
    main_path = os.path.join(target_dir, "template.html")
    with open(main_path, "w", encoding="utf-8") as f:
        f.write(merged_html)

    # Generate missing language variant
    target_lang = "en" if source_lang == "cn" else "cn"
    try:
        generate_missing_language(template_name, source_lang, target_lang)
    except Exception as e:
        print(f"⚠️ Could not generate {target_lang} variant: {e}")

    # Mark as unconfirmed so the user has to review before generation
    settings = data_store.load_settings()
    settings["template_confirmed"] = False
    settings["template_confirmed_at"] = None
    data_store.save_settings(settings)

    return {
        "template_name": template_name,
        "source_language": source_lang,
        "archive_path": archive_path,
        "main_path": main_path,
    }


def _write_default_config(path, template_name):
    default = f"""template_name: {template_name}
purpose: Auto-imported template
customer_type: all
recommended_stage: new_lead
variables:
  - customer_first_name
  - sender_name
  - sender_title
  - market_region
  - company_name
  - specific_project_or_detail
  - pain_point_solution
  - credible_proof
images: []
rules:
  - Use only facts from the customer record and confirmed template.
  - Maintain a neutral, professional tone.
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(default)


# ------------------------------------------------------------------------------
# Preview
# ------------------------------------------------------------------------------

def build_preview_html(template_name):
    """Build a self-contained preview HTML for the active template."""
    template_path = template_engine.get_template_path(template_name)
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Highlight variables and image placeholders
    html = re.sub(
        r"\{\{([^{}:]+)\}\}",
        r'<span style="background:#fff3cd;padding:0 4px;border-radius:3px;">{{\1}}</span>',
        html,
    )
    html = re.sub(
        r"\{\{IMAGE:([^}]+)\}\}",
        r'<div style="background:#f8d7da;padding:8px;margin:8px 0;text-align:center;border-radius:4px;">'
        r'📷 Image placeholder: \1</div>',
        html,
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Template Preview: {template_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 720px; margin: 40px auto; padding: 20px; line-height: 1.6; }}
        .banner {{ background: #d1ecf1; padding: 12px 16px; border-radius: 6px; margin-bottom: 24px; }}
    </style>
</head>
<body>
    <div class="banner"><strong>Preview mode</strong> — variables are highlighted. Confirm in the terminal to activate this template.</div>
    {html}
</body>
</html>
"""


# ------------------------------------------------------------------------------
# Convenience: confirm active template
# ------------------------------------------------------------------------------

def confirm_active_template():
    """Mark the active template as confirmed in settings."""
    settings = data_store.load_settings()
    settings["template_confirmed"] = True
    settings["template_confirmed_at"] = datetime.now().isoformat()
    data_store.save_settings(settings)
    return settings
