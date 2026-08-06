"""阶段 D：变量映射、日期格式、语言判定、模板导入语言纯净规则。"""

import json

import pytest

from email_agent import config, email_generator, interaction_analyzer, template_importer


def _make_var_template(make_template):
    return make_template(
        name="var_test",
        subject_template="Hi {{CUSTOMER_FIRST_NAME}} — {{DATE}}",
        html="<p>Dear {{CUSTOMER_FIRST_NAME}}, today is {{DATE}}. Note: {{TYPO_VAR}}</p>",
        variables=["CUSTOMER_FIRST_NAME", "DATE"],
    )


def test_date_alias_resolves_to_current_date(make_template, write_settings):
    _make_var_template(make_template)
    write_settings({"selected_template": "var_test", "template_confirmed": True})
    customer = {"id": "c1", "name": "Alice", "location": "Shanghai", "company": "Acme"}
    draft = email_generator.generate_for_customer(customer)
    assert "{{DATE}}" not in draft["html_body"]
    assert "2026年" in draft["html_body"]
    assert "{{UNKNOWN_VAR}}" not in draft["html_body"]


def test_missing_variables_are_collected_and_replaced(make_template, write_settings):
    _make_var_template(make_template)
    write_settings({"selected_template": "var_test", "template_confirmed": True})
    customer = {"id": "c2", "name": "Bob", "location": "Shanghai", "company": "Acme"}
    missing = []
    email_generator.generate_for_customer(customer, missing_vars=missing)
    assert "TYPO_VAR" in missing


def test_generate_all_prints_missing_variable_warning(make_template, write_settings, capsys):
    _make_var_template(make_template)
    write_settings({"selected_template": "var_test", "template_confirmed": True})
    customers = [
        {"id": "c3", "name": "Carol", "location": "Shanghai", "company": "Acme"},
    ]
    email_generator.generate_all(customers)
    captured = capsys.readouterr()
    assert "TYPO_VAR" in captured.out
    assert "已替换为空字符串" in captured.out


def test_english_date_has_no_leading_zero(make_template, write_settings):
    _make_var_template(make_template)
    write_settings({"selected_template": "var_test", "template_confirmed": True})
    customer = {"id": "c4", "name": "Dan", "location": "New York", "company": "Acme"}
    draft = email_generator.generate_for_customer(customer)
    assert "August 6, 2026" in draft["html_body"]
    assert "August 06, 2026" not in draft["html_body"]


@pytest.mark.parametrize("loc,expected", [
    ("asian cuisine", "en"),        # xian must not match inside other words
    ("beijinghotel", "en"),         # city names require word boundaries
    ("Shanghai (English)", "en"),   # explicit suffix overrides city
    ("Xi'an", "cn"),
    ("Xian", "cn"),
    ("New York", "en"),
])
def test_detect_language_word_boundaries(loc, expected):
    assert interaction_analyzer._detect_language(loc) == expected


def test_render_replaces_unknown_variables(make_template, write_settings):
    make_template(
        name="render_test",
        subject_template="Hi",
        html="<p>{{KNOWN}} and {{UNKNOWN}}</p>",
        variables=["KNOWN", "UNKNOWN"],
    )
    write_settings({"selected_template": "render_test", "template_confirmed": True})
    customer = {"id": "c1", "name": "X", "location": "Shanghai", "company": "Acme"}
    draft = email_generator.generate_for_customer(customer)
    assert "KNOWN" not in draft["html_body"]
    assert "UNKNOWN" not in draft["html_body"]
    assert " and " in draft["html_body"]


def test_prompt_contains_language_purity_rules():
    prompt = config.TEMPLATE_IMPORT_PROMPT_FILE
    with open(prompt, "r", encoding="utf-8") as f:
        text = f.read()
    assert "en_html" in text
    assert "不允许出现任何汉字" in text
    assert "GRADO Contract" in text
    assert "格度商业家具" in text


def test_structure_template_warns_on_chinese_in_en_html(monkeypatch, capsys):
    structured = {
        "subject_template": "Test subject",
        "cn_html": "<html><body>中文内容</body></html>",
        "en_html": "<html><body>English 混合中文</body></html>",
        "variables": [],
        "images": [],
        "files": [],
    }
    monkeypatch.setattr(
        "email_agent.llm_client.complete_json",
        lambda system, user, schema, temperature=None: {
            "content": json.dumps(structured),
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        },
    )
    monkeypatch.setattr(
        "email_agent.config.get_active_model",
        lambda: {"name": "test", "model": "test", "api_key": "x", "base_url": ""},
    )

    result = template_importer.structure_template_with_llm("# Hello", filename="test.md")
    captured = capsys.readouterr()
    assert "en_html 中检测到汉字" in captured.out
    assert result["en_html"] == structured["en_html"]
