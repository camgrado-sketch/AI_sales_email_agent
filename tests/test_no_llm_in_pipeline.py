"""架构护栏：邮件生成/发送/回复链路禁止调用 LLM。

PRD v2.0 核心原则——全系统唯一 LLM 调用点是
template_importer.structure_template_with_llm()。
本测试静态扫描生成/发送/接收模块源码，确保不引入 llm_client 依赖。
"""

import os
import re

import pytest

from email_agent import config

FORBIDDEN_PATTERN = re.compile(r"\bllm_client\b")

PIPELINE_MODULES = [
    "email_generator.py",
    "sender.py",
    "receiver.py",
    "interaction_analyzer.py",
    "status.py",
]


@pytest.mark.parametrize("module_file", PIPELINE_MODULES)
def test_pipeline_module_does_not_import_llm_client(module_file):
    path = os.path.join(config.BASE_DIR, "email_agent", module_file)
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    assert not FORBIDDEN_PATTERN.search(source), (
        f"{module_file} 引用了 llm_client——违反 LLM 调用点唯一化原则"
    )
