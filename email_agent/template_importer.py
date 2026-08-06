import hashlib
import html
import json
import os
import re
import shutil
from datetime import datetime
from typing import Optional

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
    """Map a source filename to a standard template name.

    Chinese filenames are mapped by keyword; any unmatched file falls back
    to the 'other' category so the original filename never appears as a
    terminal variable or directory name.
    """
    base = os.path.splitext(filename)[0].lower()
    if any(k in base for k in ("开发信", "首封", "initial", "first")):
        return "initial_contact"
    if any(k in base for k in ("跟进", "follow", "reminder", "second")):
        return "follow_up"
    if any(k in base for k in ("最终", "final", "last", "收尾")):
        return "final_note"
    return "other"


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
# LLM-based template structuring
# ------------------------------------------------------------------------------

def _available_variable_names():
    """Return the canonical list of variable placeholders the LLM may use."""
    return [
        "SENDER_NAME",
        "SENDER_TITLE",
        "SENDER_COMPANY",
        "SENDER_EMAIL",
        "SENDER_PHONE",
        "SENDER_MARKET_REGION",
        "CUSTOMER_FIRST_NAME",
        "CUSTOMER_NAME",
        "CUSTOMER_COMPANY",
        "CUSTOMER_POSITION",
        "CUSTOMER_LOCATION",
        "CUSTOMER_INDUSTRY",
        "CURRENT_DATE",
    ]


def _template_structure_schema():
    return {
        "name": "structured_email_template",
        "type": "object",
        "properties": {
            "subject_template": {
                "type": "string",
                "description": "Email subject line with {{VAR}} placeholders",
            },
            "cn_html": {
                "type": "string",
                "description": "Complete Chinese HTML email body with {{VAR}}, {{IMAGE:name}}, {{FILE:name}} placeholders",
            },
            "en_html": {
                "type": "string",
                "description": "Complete English HTML email body with placeholders",
            },
            "variables": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of variable names actually used in the templates",
            },
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of image placeholder names",
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file placeholder names",
            },
            "ignored_sections": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Sections that were ignored as non-core content",
            },
        },
        "required": ["subject_template", "cn_html", "en_html", "variables", "images", "files"],
        "additionalProperties": False,
    }


def structure_template_with_llm(markdown, filename=""):
    """Call the remote LLM once to turn extracted Markdown into a structured bilingual template.

    The LLM receives only text and placeholder names; no image or file binaries are uploaded.
    """
    if not config.get_active_model():
        raise RuntimeError("No active LLM model configured. Check .env or settings.")

    system_prompt = _read_file(config.TEMPLATE_IMPORT_PROMPT_FILE)
    if not system_prompt:
        raise RuntimeError(f"Template import prompt not found: {config.TEMPLATE_IMPORT_PROMPT_FILE}")

    user_prompt = f"""Source filename: {filename}

Available variables (use only these exact names):
{', '.join(_available_variable_names())}

---

Extracted content:

{markdown}
"""

    raw = llm_client.complete_json(
        system_prompt,
        user_prompt,
        _template_structure_schema(),
        temperature=0.3,
    )
    result = json.loads(raw["content"])

    # Normalize arrays to strings and strip whitespace
    for key in ("subject_template", "cn_html", "en_html"):
        if key in result:
            result[key] = str(result[key]).strip()
    for key in ("variables", "images", "files", "ignored_sections"):
        value = result.get(key)
        if not isinstance(value, list):
            result[key] = []
        else:
            result[key] = [str(v).strip() for v in value if str(v).strip()]

    return result


# ------------------------------------------------------------------------------
# Write structured template to disk
# ------------------------------------------------------------------------------

def _default_config_yaml(template_name, structured):
    """Build a default config.yaml content from the structured template."""
    variables = structured.get("variables", [])
    images = structured.get("images", [])
    files = structured.get("files", [])
    subject_template = structured.get("subject_template", "")

    lines = [
        f"template_name: {template_name}",
        "purpose: Auto-imported template",
        "customer_type: all",
        "recommended_stage: new_lead",
        f"subject_template: {subject_template!r}",
        "variables:",
    ]
    for v in variables:
        lines.append(f"  - {v}")
    lines.append("images:")
    for img in images:
        lines.append(f"  - {img}")
    lines.append("files:")
    for f in files:
        lines.append(f"  - {f}")
    lines.extend([
        "rules:",
        "  - Use only facts from the customer record and confirmed sender profile.",
        "  - Do not invent names, companies, positions, or locations.",
        "  - The email language is determined by the language parameter at render time.",
    ])
    return "\n".join(lines) + "\n"


def write_structured_template(template_name, structured, source_lang):
    """Write the bilingual template files and config.yaml to the active template directory.

    Args:
        template_name: target template directory name.
        structured: dict returned by structure_template_with_llm().
        source_lang: "cn" or "en" — determines which version becomes template.html.

    Returns:
        dict with paths: main_path, other_path, config_path, source_language, target_language.
    """
    target_lang = "en" if source_lang == "cn" else "cn"
    source_html_key = "cn_html" if source_lang == "cn" else "en_html"
    target_html_key = "en_html" if source_lang == "cn" else "cn_html"

    target_dir = os.path.join(config.TEMPLATES_DIR, template_name)
    os.makedirs(target_dir, exist_ok=True)

    main_path = os.path.join(target_dir, "template.html")
    other_path = os.path.join(target_dir, f"template_{target_lang}.html")
    config_path = os.path.join(target_dir, "config.yaml")

    with open(main_path, "w", encoding="utf-8") as f:
        f.write(structured.get(source_html_key, ""))

    with open(other_path, "w", encoding="utf-8") as f:
        f.write(structured.get(target_html_key, ""))

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(_default_config_yaml(template_name, structured))

    return {
        "main_path": main_path,
        "other_path": other_path,
        "config_path": config_path,
        "source_language": source_lang,
        "target_language": target_lang,
    }


# ------------------------------------------------------------------------------
# Archiving and activation
# ------------------------------------------------------------------------------

def archive_current_template(template_name):
    """Copy the current active template directory to templates/archive/<template_name>/YYYY/MM/DD/."""
    src = os.path.join(config.TEMPLATES_DIR, template_name)
    if not os.path.exists(src):
        return None
    now = datetime.now()
    stamp = now.strftime("%H%M%S")
    dst = os.path.join(
        config.TEMPLATE_ARCHIVE_DIR,
        template_name,
        now.strftime("%Y"),
        now.strftime("%m"),
        now.strftime("%d"),
        stamp,
    )
    shutil.copytree(src, dst)
    return dst


def list_archive_folders():
    """Return a flat list of archived template folders sorted newest first.

    Supports both the current layout:
        archive/<template_name>/YYYY/MM/DD/<stamp>/
    and the legacy layout:
        archive/YYYY/MM/DD/<template_name>_<stamp>/
    """
    archives = []
    base = config.TEMPLATE_ARCHIVE_DIR
    if not os.path.exists(base):
        return archives

    # New structure: archive/<template_name>/YYYY/MM/DD/<stamp>
    for template_name in sorted(os.listdir(base), reverse=True):
        tpath = os.path.join(base, template_name)
        if not os.path.isdir(tpath) or template_name in (".gitkeep",):
            continue
        if re.match(r"^\d{4}$", template_name):
            continue  # legacy top-level year
        for year in sorted(os.listdir(tpath), reverse=True):
            ypath = os.path.join(tpath, year)
            if not os.path.isdir(ypath) or not re.match(r"^\d{4}$", year):
                continue
            for month in sorted(os.listdir(ypath), reverse=True):
                mpath = os.path.join(ypath, month)
                if not os.path.isdir(mpath) or not re.match(r"^\d{2}$", month):
                    continue
                for day in sorted(os.listdir(mpath), reverse=True):
                    dpath = os.path.join(mpath, day)
                    if not os.path.isdir(dpath) or not re.match(r"^\d{2}$", day):
                        continue
                    for stamp in sorted(os.listdir(dpath), reverse=True):
                        epath = os.path.join(dpath, stamp)
                        if os.path.isdir(epath) and re.match(r"^\d{6}$", stamp):
                            archives.append({
                                "path": epath,
                                "date": f"{year}/{month}/{day}",
                                "name": f"{template_name}/{year}/{month}/{day}/{stamp}",
                                "template_name": template_name,
                                "stamp": stamp,
                            })

    # Old structure: archive/YYYY/MM/DD/<name>_<stamp>
    for year in sorted(os.listdir(base), reverse=True):
        ypath = os.path.join(base, year)
        if not os.path.isdir(ypath) or not re.match(r"^\d{4}$", year):
            continue
        for month in sorted(os.listdir(ypath), reverse=True):
            mpath = os.path.join(ypath, month)
            if not os.path.isdir(mpath) or not re.match(r"^\d{2}$", month):
                continue
            for day in sorted(os.listdir(mpath), reverse=True):
                dpath = os.path.join(mpath, day)
                if not os.path.isdir(dpath) or not re.match(r"^\d{2}$", day):
                    continue
                for name in sorted(os.listdir(dpath), reverse=True):
                    epath = os.path.join(dpath, name)
                    if not os.path.isdir(epath):
                        continue
                    template_name, stamp = name, ""
                    if "_" in name:
                        parts = name.rsplit("_", 1)
                        if parts[1].isdigit() and len(parts[1]) == 6:
                            template_name, stamp = parts[0], parts[1]
                    archives.append({
                        "path": epath,
                        "date": f"{year}/{month}/{day}",
                        "name": name,
                        "template_name": template_name,
                        "stamp": stamp,
                    })

    archives.sort(key=lambda x: (x["date"].replace("/", ""), x["stamp"]), reverse=True)
    return archives


def get_active_template_path(template_name):
    """Return the active template directory path if it exists."""
    path = os.path.join(config.TEMPLATES_DIR, template_name)
    return path if os.path.exists(path) else None


def get_latest_archive(template_name):
    """Return the newest archive path for a template, or None."""
    matches = [a for a in list_archive_folders() if a["template_name"] == template_name]
    return matches[0]["path"] if matches else None


def list_archives_by_day(template_name):
    """Return [(date, [archive_dict, ...]), ...] sorted by date descending."""
    matches = [a for a in list_archive_folders() if a["template_name"] == template_name]
    days = {}
    for a in matches:
        days.setdefault(a["date"], []).append(a)
    return sorted(days.items(), key=lambda x: x[0].replace("/", ""), reverse=True)


def list_template_names_in_archive():
    """Return sorted list of template names that have archives."""
    return sorted({a["template_name"] for a in list_archive_folders()})


def is_import_state_stale():
    """Return True when templates/email/ is empty but templates/import/ still
    contains files already recorded in template_import_state.json."""
    if template_engine.list_templates():
        return False
    candidates = scan_import_folder()
    if not candidates:
        return False
    state = data_store.load_template_import_state()
    return bool(state.get("files"))


def reset_import_state():
    """Clear the checksum state so existing import files appear as new."""
    data_store.save_template_import_state({
        "last_reset_at": datetime.now().isoformat(),
        "files": {},
    })


def delete_archive_entry(path):
    """Remove an archived template folder tree."""
    if os.path.exists(path):
        shutil.rmtree(path)
        return True
    return False


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


def activate_template(template_name, candidate_path, source_template_path=None, force=False):
    """Import a candidate file into an active template directory.

    Steps:
      1. Archive current template.
      2. Extract candidate to Markdown and detect source language.
      3. Call the LLM once to obtain a structured bilingual template.
      4. Write template.html (source language), template_<other>.html, and config.yaml.
      5. Mark template as unconfirmed (user must confirm before use).

    Note:
      source_template_path is accepted for CLI compatibility but is no longer used to
      merge HTML content; the new template is generated entirely from the LLM output.
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

    # The source_template_path argument is kept for CLI compatibility but ignored;
    # the new template is produced entirely by the LLM structured output.
    _ = source_template_path

    structured = structure_template_with_llm(markdown, os.path.basename(candidate_path))
    written = write_structured_template(template_name, structured, source_lang)

    # Mark as unconfirmed so the user has to review before generation
    settings = data_store.load_settings()
    settings["template_confirmed"] = False
    settings["template_confirmed_at"] = None
    data_store.save_settings(settings)

    return {
        "template_name": template_name,
        "source_language": source_lang,
        "archive_path": archive_path,
        "main_path": written["main_path"],
        "other_path": written["other_path"],
        "config_path": written["config_path"],
    }


# ------------------------------------------------------------------------------
# Preview
# ------------------------------------------------------------------------------

def _read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build_preview_html(template_name):
    """Build a self-contained preview HTML for the active template."""
    template_path = template_engine.get_template_path(template_name)
    if not os.path.exists(template_path):
        html = f"<p><em>Template HTML not found for '{template_name}'.</em></p>"
    else:
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()

    # Highlight variables and image/file placeholders
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
    html = re.sub(
        r"\{\{FILE:([^}]+)\}\}",
        r'<div style="background:#d1ecf1;padding:8px;margin:8px 0;text-align:center;border-radius:4px;">'
        r'📎 File placeholder: \1</div>',
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
