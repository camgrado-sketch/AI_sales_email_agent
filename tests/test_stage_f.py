"""阶段 F：Playwright 预览环境检测与无 GUI 截图路径提示。"""

from email_agent import preview


# ------------------------------------------------------------------------------
# _has_gui() environment detection
# ------------------------------------------------------------------------------

def test_has_gui_true_on_mac_and_windows(monkeypatch):
    monkeypatch.setattr(preview, "_is_wsl", lambda: False)
    for plat in ("darwin", "win32", "win64"):
        monkeypatch.setattr(preview.sys, "platform", plat)
        assert preview._has_gui() is True


def test_has_gui_true_on_linux_with_display(monkeypatch):
    monkeypatch.setattr(preview.sys, "platform", "linux")
    monkeypatch.setattr(preview, "_is_wsl", lambda: False)
    monkeypatch.setenv("DISPLAY", ":0")
    assert preview._has_gui() is True


def test_has_gui_false_on_wsl_even_with_display(monkeypatch):
    monkeypatch.setattr(preview.sys, "platform", "linux")
    monkeypatch.setattr(preview, "_is_wsl", lambda: True)
    monkeypatch.setenv("DISPLAY", ":0")
    assert preview._has_gui() is False


def test_has_gui_false_on_linux_without_display(monkeypatch):
    monkeypatch.setattr(preview.sys, "platform", "linux")
    monkeypatch.setattr(preview, "_is_wsl", lambda: False)
    monkeypatch.delenv("DISPLAY", raising=False)
    assert preview._has_gui() is False


# ------------------------------------------------------------------------------
# _open_html() chooses the right Playwright mode
# ------------------------------------------------------------------------------

def test_open_html_with_gui_tries_headed_first(monkeypatch):
    calls = []

    def fake_open(path, headless):
        calls.append(headless)
        return True

    monkeypatch.setattr(preview, "_open_with_playwright", fake_open)
    monkeypatch.setattr(preview, "_has_gui", lambda: True)
    monkeypatch.setattr(preview, "_open_with_system_browser", lambda p: False)

    preview._open_html("<html><body>Hello</body></html>")
    assert calls == [False]


def test_open_html_without_gui_uses_headless_only(monkeypatch):
    calls = []

    def fake_open(path, headless):
        calls.append(headless)
        return True

    monkeypatch.setattr(preview, "_open_with_playwright", fake_open)
    monkeypatch.setattr(preview, "_has_gui", lambda: False)
    monkeypatch.setattr(preview, "_open_with_system_browser", lambda p: False)

    preview._open_html("<html><body>Hello</body></html>")
    assert calls == [True]


def test_open_html_gui_headed_failure_falls_back_to_headless(monkeypatch):
    calls = []

    def fake_open(path, headless):
        calls.append(headless)
        return headless  # headed fails, headless succeeds

    monkeypatch.setattr(preview, "_open_with_playwright", fake_open)
    monkeypatch.setattr(preview, "_has_gui", lambda: True)
    monkeypatch.setattr(preview, "_open_with_system_browser", lambda p: False)

    preview._open_html("<html><body>Hello</body></html>")
    assert calls == [False, True]


# ------------------------------------------------------------------------------
# Screenshot path highlighting
# ------------------------------------------------------------------------------

def test_headless_screenshot_path_is_highlighted(monkeypatch, capsys):
    def fake_open(path, headless):
        if headless:
            print(f"\033[1m\033[93m📸 已生成 PNG 预览：/tmp/latest_preview.png\033[0m")
        return True

    monkeypatch.setattr(preview, "_has_gui", lambda: False)
    monkeypatch.setattr(preview, "_open_with_playwright", fake_open)
    monkeypatch.setattr(preview, "_open_with_system_browser", lambda p: False)

    preview._open_html("<html><body>Hello</body></html>")

    captured = capsys.readouterr()
    assert "\033[1m\033[93m📸 已生成 PNG 预览" in captured.out
    assert "latest_preview.png" in captured.out
