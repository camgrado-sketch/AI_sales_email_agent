"""阶段 G：体验优化与图片提取加固（G.1 终端 UI 与文案净化）。"""

import sys
import types

import pytest

from email_agent import preview


@pytest.mark.parametrize("headless,expected_hint", [
    (True, "playwright install chromium"),
    (False, "未检测到本地浏览器环境"),
])
def test_playwright_failure_prints_friendly_chinese(monkeypatch, capsys, headless, expected_hint):
    """G.1：Playwright 启动失败时不得打印大段英文异常栈，只输出简短中文提示。"""
    fake_pkg = types.ModuleType("playwright")
    fake_sync = types.ModuleType("playwright.sync_api")

    def _boom(*args, **kwargs):
        raise RuntimeError(
            "Executable doesn't exist at /root/.cache/ms-playwright/chromium-1148/chrome-linux/headless_shell\n"
            "Looks like Playwright Test or Playwright is not installed.\n"
            "Please run the following command to download the browser:\n"
            "  npx playwright install chromium"
        )

    fake_sync.sync_playwright = _boom
    monkeypatch.setitem(sys.modules, "playwright", fake_pkg)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_sync)

    result = preview._open_with_playwright("/tmp/nonexistent_preview.html", headless=headless)
    out = capsys.readouterr().out

    assert result is False
    # 英文异常细节不得泄漏到终端
    assert "Executable doesn't exist" not in out
    assert "Looks like Playwright" not in out
    # 必须包含简短中文提示
    assert expected_hint in out
