"""阶段 E：邮件主题非空兜底与导入后用户编辑。"""

import os

import pytest
import yaml

from email_agent import cli_controller, config, template_engine, template_importer


# ------------------------------------------------------------------------------
# Fallback subject extraction
# ------------------------------------------------------------------------------

def test_fallback_subject_prefers_markdown_heading():
    assert template_importer._fallback_subject("# Hello World\nbody") == "Hello World"


def test_fallback_subject_prefers_first_heading_over_first_line():
    assert template_importer._fallback_subject("Some intro\n# Real Title\nbody") == "Real Title"


def test_fallback_subject_falls_back_to_first_line():
    assert template_importer._fallback_subject("First line\nSecond line") == "First line"


def test_fallback_subject_truncates_long_text():
    text = "word " * 30  # way over 60 chars
    result = template_importer._fallback_subject(text)
    assert len(result) <= 60
    # It should keep whole words when possible
    assert not result.endswith(" ")


def test_fallback_subject_empty_markdown():
    assert (
        template_importer._fallback_subject("")
        == "GRADO Contract Partnership Opportunity"
    )


# ------------------------------------------------------------------------------
# Import-side empty-subject guard
# ------------------------------------------------------------------------------

def test_activate_template_fallback_on_empty_subject(isolated_env, monkeypatch, capsys):
    import_dir = config.TEMPLATE_IMPORT_DIR
    md_path = os.path.join(import_dir, "empty_subject.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Special Offer\n\nDear partner, ...")

    def fake_structure(*args, **kwargs):
        return {
            "subject_template": "   ",
            "cn_html": "<p>中文</p>",
            "en_html": "<p>English</p>",
            "variables": [],
            "images": [],
            "files": [],
        }

    monkeypatch.setattr(template_importer, "structure_template_with_llm", fake_structure)
    monkeypatch.setattr(template_importer, "detect_language", lambda markdown, filename: "cn")

    result = template_importer.activate_template("empty_subj_tmpl", md_path, force=True)
    captured = capsys.readouterr()

    assert "subject_template 为空" in captured.out
    assert result["template_name"] == "empty_subj_tmpl"
    cfg = template_engine.get_template_config("empty_subj_tmpl")
    assert cfg["subject_template"] == "Special Offer"


# ------------------------------------------------------------------------------
# CLI import flow allows editing the subject
# ------------------------------------------------------------------------------

def test_import_flow_user_can_edit_subject(isolated_env, monkeypatch):
    import_dir = config.TEMPLATE_IMPORT_DIR
    md_path = os.path.join(import_dir, "editable.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Original\nbody")

    fake_candidate = template_importer.ImportCandidate(md_path, "checksum")

    def fake_detect_changes():
        return [fake_candidate]

    def fake_activate(template_name, candidate_path, force=False):
        tdir = os.path.join(config.TEMPLATES_DIR, template_name)
        os.makedirs(tdir, exist_ok=True)
        cfg = {
            "template_name": template_name,
            "subject_template": "Auto Subject",
            "variables": [],
            "images": [],
            "files": [],
        }
        config_path = os.path.join(tdir, "config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True)
        with open(os.path.join(tdir, "template.html"), "w", encoding="utf-8") as f:
            f.write("<html><body>Hello</body></html>")
        return {
            "template_name": template_name,
            "config_path": config_path,
            "main_path": os.path.join(tdir, "template.html"),
            "other_path": os.path.join(tdir, "template_en.html"),
            "source_language": "cn",
            "target_language": "en",
        }

    monkeypatch.setattr(template_importer, "detect_changes", fake_detect_changes)
    monkeypatch.setattr(template_importer, "activate_template", fake_activate)

    # Bypass preview.open_template_preview inside _confirm_template_flow
    monkeypatch.setattr("email_agent.preview.open_template_preview", lambda name: "/tmp/preview.html")

    inputs = iter(["1", "", "Custom Subject", "y", "n"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    cli_controller._import_template_flow()

    cfg = template_engine.get_template_config("other")
    assert cfg["subject_template"] == "Custom Subject"


def test_import_flow_keeps_subject_when_user_accepts(isolated_env, monkeypatch):
    import_dir = config.TEMPLATE_IMPORT_DIR
    md_path = os.path.join(import_dir, "acceptable.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Keep Me\nbody")

    fake_candidate = template_importer.ImportCandidate(md_path, "checksum")

    def fake_detect_changes():
        return [fake_candidate]

    def fake_activate(template_name, candidate_path, force=False):
        tdir = os.path.join(config.TEMPLATES_DIR, "my_tmpl")
        os.makedirs(tdir, exist_ok=True)
        cfg = {
            "template_name": "my_tmpl",
            "subject_template": "Auto Subject",
            "variables": [],
            "images": [],
            "files": [],
        }
        config_path = os.path.join(tdir, "config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True)
        with open(os.path.join(tdir, "template.html"), "w", encoding="utf-8") as f:
            f.write("<html><body>Hello</body></html>")
        return {
            "template_name": "my_tmpl",
            "config_path": config_path,
            "main_path": os.path.join(tdir, "template.html"),
            "other_path": os.path.join(tdir, "template_en.html"),
            "source_language": "cn",
            "target_language": "en",
        }

    monkeypatch.setattr(template_importer, "detect_changes", fake_detect_changes)
    monkeypatch.setattr(template_importer, "activate_template", fake_activate)
    monkeypatch.setattr("email_agent.preview.open_template_preview", lambda name: "/tmp/preview.html")

    inputs = iter(["1", "my_tmpl", "", "y", "n"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    cli_controller._import_template_flow()

    cfg = template_engine.get_template_config("my_tmpl")
    assert cfg["subject_template"] == "Auto Subject"


# ------------------------------------------------------------------------------
# Prompt rules coverage
# ------------------------------------------------------------------------------

def test_prompt_requires_non_empty_subject():
    prompt = config.TEMPLATE_IMPORT_PROMPT_FILE
    with open(prompt, "r", encoding="utf-8") as f:
        text = f.read()
    assert "subject_template" in text
    assert "禁止为空" in text
    assert "≤60" in text or "60 字符" in text
