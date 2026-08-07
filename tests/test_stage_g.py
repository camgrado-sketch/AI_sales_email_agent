"""阶段 G：体验优化与图片提取加固（G.1 终端 UI 与文案净化；G.2 双语分离预览）。"""

import json
import os
import sys
import types

import pytest

from email_agent import config, preview, template_importer


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


# ------------------------------------------------------------------------------
# G.2 双语模板分离预览
# ------------------------------------------------------------------------------

def _make_template(name, files):
    """Create templates/email/<name>/ with the given {filename: content} files."""
    tdir = os.path.join(config.TEMPLATES_DIR, name)
    os.makedirs(tdir, exist_ok=True)
    for fname, content in files.items():
        with open(os.path.join(tdir, fname), "w", encoding="utf-8") as f:
            f.write(content)
    return tdir


def test_resolve_preview_files_standard_layout(isolated_env):
    """标准布局（template.html 为英文源 + template_cn.html）：中英各一，中文在前。"""
    tdir = _make_template("t1", {
        "template.html": "<p>English source</p>",
        "template_cn.html": "<p>中文内容</p>",
    })
    variants = template_importer.resolve_template_preview_files("t1")
    assert [v["language"] for v in variants] == ["cn", "en"]
    assert variants[0]["path"] == os.path.join(tdir, "template_cn.html")
    assert variants[0]["fallback"] is False
    # 英文版回退到 template.html（它就是英文源）
    assert variants[1]["path"] == os.path.join(tdir, "template.html")
    assert variants[1]["fallback"] is True


def test_resolve_preview_files_missing_variant_prints_hint(isolated_env, capsys):
    """缺少语言变体文件时给出明确中文提示（复现素材：开发信测试 缺 template_en.html）。"""
    _make_template("t2", {
        "template.html": "<p>English source</p>",
        "template_cn.html": "<p>中文内容</p>",
    })
    variants = template_importer.resolve_template_preview_files("t2")
    out = capsys.readouterr().out
    assert len(variants) == 2
    assert "缺少 template_en.html" in out


def test_resolve_preview_files_empty_variant_falls_back(isolated_env, capsys):
    """语言变体文件存在但内容为空（LLM 生成缺失）→ 警告并回退 template.html。"""
    tdir = _make_template("t3", {
        "template.html": "<p>English source</p>",
        "template_cn.html": "   \n",
    })
    variants = template_importer.resolve_template_preview_files("t3")
    out = capsys.readouterr().out
    assert "内容为空" in out
    # 中英都解析到同一个 template.html，只预览一次
    assert len(variants) == 1
    assert variants[0]["path"] == os.path.join(tdir, "template.html")


def test_resolve_preview_files_no_files(isolated_env, capsys):
    """完全没有模板文件 → 返回空列表并打印警告。"""
    os.makedirs(os.path.join(config.TEMPLATES_DIR, "t4"), exist_ok=True)
    variants = template_importer.resolve_template_preview_files("t4")
    out = capsys.readouterr().out
    assert variants == []
    assert "跳过该语言预览" in out


def test_build_preview_html_language_label(isolated_env):
    """build_preview_html 支持 language 参数并在页面中标注语言。"""
    _make_template("t5", {
        "template.html": "<p>English</p>",
        "template_cn.html": "<p>中文正文</p>",
    })
    html = template_importer.build_preview_html("t5", language="cn")
    assert "中文版" in html
    assert "中文正文" in html

    html_default = template_importer.build_preview_html("t5")
    assert "English" in html_default


def test_open_template_preview_opens_both_languages(isolated_env, monkeypatch, capsys):
    """open_template_preview 必须依次打开中、英两个预览窗口。"""
    _make_template("t6", {
        "template.html": "<p>English source</p>",
        "template_cn.html": "<p>中文内容</p>",
    })
    opened = []

    def fake_open_html(html, suffix=".html"):
        opened.append(suffix)
        return f"/tmp/preview{suffix}"

    monkeypatch.setattr(preview, "_open_html", fake_open_html)
    paths = preview.open_template_preview("t6")
    out = capsys.readouterr().out

    assert len(paths) == 2
    assert opened == ["_template_cn.html", "_template_en.html"]
    assert "正在打开中文版模板预览（1/2）" in out
    assert "正在打开英文版模板预览（2/2）" in out


def test_open_template_preview_no_files(isolated_env, monkeypatch, capsys):
    """没有可用模板文件时返回空列表并给出提示，而不是抛异常。"""
    opened = []
    monkeypatch.setattr(preview, "_open_html", lambda html, suffix=".html": opened.append(suffix))
    paths = preview.open_template_preview("not_exist")
    out = capsys.readouterr().out
    assert paths == []
    assert opened == []
    assert "无法打开预览" in out


# ------------------------------------------------------------------------------
# G.2 language 生成失败容错
# ------------------------------------------------------------------------------

def _patch_llm(monkeypatch, raw_result):
    """Patch the LLM layer so structure_template_with_llm runs offline."""
    monkeypatch.setattr(
        "email_agent.config.get_active_model",
        lambda: {"name": "test", "model": "test", "api_key": "x", "base_url": ""},
    )
    monkeypatch.setattr(template_importer, "_read_file", lambda path: "SYSTEM PROMPT")
    monkeypatch.setattr(
        "email_agent.llm_client.complete_json",
        lambda system, user, schema, temperature=None: raw_result,
    )


def test_structure_llm_invalid_json_raises_chinese_message(isolated_env, monkeypatch):
    """LLM 返回非 JSON 时抛出可理解的中文错误，而不是 'Expecting value...'。"""
    _patch_llm(monkeypatch, {"content": "not a json"})
    with pytest.raises(RuntimeError, match="无法解析为 JSON"):
        template_importer.structure_template_with_llm("# Hello", filename="t.md")


def test_structure_llm_missing_content_field(isolated_env, monkeypatch):
    _patch_llm(monkeypatch, {})
    with pytest.raises(RuntimeError, match="缺少 content 字段"):
        template_importer.structure_template_with_llm("# Hello", filename="t.md")


def test_structure_llm_normalizes_alias_field_names(isolated_env, monkeypatch, capsys):
    """LLM 字段命名不符（chinese_html）时归一化为 cn_html。"""
    _patch_llm(monkeypatch, {"content": json.dumps({
        "subject_template": "S",
        "chinese_html": "<p>中文</p>",
        "en_html": "<p>English</p>",
        "variables": [],
        "images": [],
        "files": [],
    })})
    result = template_importer.structure_template_with_llm("# Hello", filename="t.md")
    out = capsys.readouterr().out
    assert result["cn_html"] == "<p>中文</p>"
    assert "已归一化为 'cn_html'" in out


def test_structure_llm_warns_on_missing_language_html(isolated_env, monkeypatch, capsys):
    """缺少某语言 HTML 时打印明确警告，供写盘阶段容错处理。"""
    _patch_llm(monkeypatch, {"content": json.dumps({
        "subject_template": "S",
        "cn_html": "",
        "en_html": "<p>English</p>",
        "variables": [],
        "images": [],
        "files": [],
    })})
    template_importer.structure_template_with_llm("# Hello", filename="t.md")
    out = capsys.readouterr().out
    assert "缺少中文模板内容" in out
    assert "'cn_html' 为空" in out


def test_write_structured_template_empty_source_raises(isolated_env):
    """源语言 HTML 缺失 → 明确报错，禁止写出空 template.html。"""
    structured = {"subject_template": "S", "en_html": "", "cn_html": ""}
    with pytest.raises(ValueError, match="模板导入失败"):
        template_importer.write_structured_template("bad", structured, "en")


def test_write_structured_template_empty_target_skips_file(isolated_env, capsys):
    """目标语言 HTML 缺失 → 不写空文件，other_path 为 None 并打印警告。"""
    structured = {"subject_template": "S", "en_html": "<p>English</p>", "cn_html": ""}
    result = template_importer.write_structured_template("t7", structured, "en")
    out = capsys.readouterr().out

    assert os.path.exists(result["main_path"])
    assert result["other_path"] is None
    assert not os.path.exists(
        os.path.join(config.TEMPLATES_DIR, "t7", "template_cn.html")
    )
    assert "cn 版模板未写入" in out

    # config.yaml 持久化源语言，供后续预览/诊断使用
    import yaml
    with open(result["config_path"], "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    assert cfg["source_language"] == "en"
