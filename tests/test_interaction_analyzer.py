"""阶段 A.1 / D.3：interaction_analyzer 仅返回 stage/language/reason 且支持拼音城市。"""

import pytest

from email_agent import interaction_analyzer


def test_analyze_returns_only_stage_language_reason():
    customer = {"id": "c1", "name": "Test", "location": "Shanghai"}
    result = interaction_analyzer.analyze(customer)
    assert set(result.keys()) == {"stage", "language", "reason"}
    assert result["language"] == "cn"


@pytest.mark.parametrize("loc,expected", [
    ("Shanghai", "cn"),
    ("Beijing", "cn"),
    ("Guangzhou", "cn"),
    ("Shenzhen", "cn"),
    ("Chengdu", "cn"),
    ("Hangzhou", "cn"),
    ("Hong Kong", "en"),
    ("Taiwan", "en"),
    ("New York", "en"),
    ("中国", "cn"),
    ("上海", "cn"),
    ("(中文)", "cn"),
    ("London (English)", "en"),
])
def test_detect_language(loc, expected):
    assert interaction_analyzer._detect_language(loc) == expected
