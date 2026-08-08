"""pytest 公共夹具：把所有数据/模板/资产路径重定向到临时目录。

所有模块均通过 `config.X` 属性在运行时取路径，因此 monkeypatch
config 模块常量即可让测试完全不碰真实 data/ 与 templates/。
"""

import os

import pytest

from email_agent import config


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Redirect every config path constant into tmp_path (per-test isolation)."""
    data_dir = tmp_path / "data"
    templates_dir = tmp_path / "templates" / "email"
    import_dir = tmp_path / "templates" / "import"
    archive_dir = tmp_path / "templates" / "archive"
    assets_dir = tmp_path / "assets"
    images_dir = assets_dir / "images"
    files_dir = assets_dir / "files"

    for d in (data_dir, templates_dir, import_dir, archive_dir, images_dir, files_dir):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(config, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(config, "DRAFTS_DIR", str(data_dir / "drafts"))
    monkeypatch.setattr(config, "DRAFTS_FILE", str(data_dir / "drafts" / "drafts.csv"))
    monkeypatch.setattr(config, "DRAFTS_JSON_FILE", str(data_dir / "drafts.json"))
    monkeypatch.setattr(config, "EMAIL_LOGS_FILE", str(data_dir / "email_logs.csv"))
    monkeypatch.setattr(config, "REPLY_LOGS_FILE", str(data_dir / "reply_logs.csv"))
    monkeypatch.setattr(config, "SETTINGS_JSON_FILE", str(data_dir / "settings.json"))
    monkeypatch.setattr(config, "GENERATION_STATE_FILE", str(data_dir / "generation_state.json"))
    monkeypatch.setattr(config, "SENDING_STATE_FILE", str(data_dir / "sending_state.json"))
    monkeypatch.setattr(config, "TEMPLATE_IMPORT_STATE_FILE", str(data_dir / "template_import_state.json"))
    monkeypatch.setattr(config, "TEMPLATES_DIR", str(templates_dir))
    monkeypatch.setattr(config, "TEMPLATE_IMPORT_DIR", str(import_dir))
    monkeypatch.setattr(config, "TEMPLATE_ARCHIVE_DIR", str(archive_dir))
    monkeypatch.setattr(config, "ASSETS_DIR", str(assets_dir))
    monkeypatch.setattr(config, "IMAGES_DIR", str(images_dir))
    monkeypatch.setattr(config, "FILES_DIR", str(files_dir))

    sender_profile = tmp_path / "templates" / "sender_profile.md"
    sender_profile.write_text(
        "---\n"
        'sender_name: "Test Sender"\n'
        'sender_title: "Partnership Manager"\n'
        'sender_company: "GRADO Contract"\n'
        'sender_email: "sender@example.com"\n'
        'sender_phone: "+86 138 0000 0000"\n'
        'sender_market_region: "大中华区"\n'
        "---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "SENDER_PROFILE_FILE", str(sender_profile))

    return tmp_path


@pytest.fixture
def write_settings(isolated_env):
    """Helper to write data/settings.json inside the isolated env."""
    import json

    def _write(settings: dict):
        path = os.path.join(config.DATA_DIR, "settings.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

    return _write


@pytest.fixture
def make_template(isolated_env):
    """Create a minimal active template (config.yaml + template.html) for tests."""
    import yaml

    def _make(name="test_template", variables=None, subject_template="Hi {{CUSTOMER_FIRST_NAME}",
              html="<html><body>Hello {{CUSTOMER_FIRST_NAME}} from {{CUSTOMER_COMPANY}}</body></html>"):
        tdir = os.path.join(config.TEMPLATES_DIR, name)
        os.makedirs(tdir, exist_ok=True)
        cfg = {
            "template_name": name,
            "subject_template": subject_template,
            "variables": variables or ["CUSTOMER_FIRST_NAME", "CUSTOMER_COMPANY"],
            "images": [],
            "files": [],
            "rules": [],
        }
        with open(os.path.join(tdir, "config.yaml"), "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True)
        with open(os.path.join(tdir, "template.html"), "w", encoding="utf-8") as f:
            f.write(html)
        return name

    return _make
