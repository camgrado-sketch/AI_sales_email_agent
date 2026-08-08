"""阶段 A.2：config.py selected_template 写入与导入时间读取。"""

from email_agent import config, data_store


def test_set_and_get_selected_template():
    assert config.get_selected_template() == ""
    config.set_selected_template("initial_contact")
    assert config.get_selected_template() == "initial_contact"
    config.set_selected_template("")
    assert config.get_selected_template() == ""


def test_get_template_imported_at():
    settings = data_store.load_settings()
    settings["template_imported_at"] = {"foo": "2026-08-01", "bar": "2026-08-02"}
    data_store.save_settings(settings)

    assert config.get_template_imported_at("foo") == "2026-08-01"
    assert config.get_template_imported_at("missing") == ""


def test_set_selected_template_persists():
    config.set_selected_template("follow_up")
    # read back via data_store to ensure persistence
    settings = data_store.load_settings()
    assert settings.get("selected_template") == "follow_up"
