"""阶段 A.3：cli_controller 菜单 6 [A] 选择生效模板。"""

from email_agent import cli_controller, config


def test_menu_select_template_picks_number(make_template, monkeypatch, capsys):
    make_template("alpha")
    make_template("beta")
    monkeypatch.setattr("builtins.input", lambda _: "2")

    cli_controller.menu_select_template()
    assert config.get_selected_template() == "beta"


def test_menu_select_template_empty_keeps_current(make_template, write_settings, monkeypatch):
    make_template("alpha")
    make_template("beta")
    write_settings({"selected_template": "alpha"})
    monkeypatch.setattr("builtins.input", lambda _: "")

    cli_controller.menu_select_template()
    assert config.get_selected_template() == "alpha"


def test_menu_select_template_shows_usage_state(make_template, write_settings, monkeypatch, capsys):
    make_template("alpha")
    write_settings({"selected_template": "alpha"})
    monkeypatch.setattr("builtins.input", lambda _: "1")

    cli_controller.menu_select_template()
    captured = capsys.readouterr()
    assert "未发送" in captured.out
