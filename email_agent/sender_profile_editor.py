import os
import re

import yaml

from email_agent import config, data_store


SENDER_FIELDS = [
    ("sender_name", "发送者姓名"),
    ("sender_title", "发送者职位"),
    ("sender_company", "发送者公司"),
    ("sender_email", "发送者邮箱"),
    ("sender_phone", "发送者电话"),
    ("sender_market_region", "发送者负责区域"),
]


def _parse_sender_profile(path):
    """Parse YAML frontmatter from sender_profile.md if it exists."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return {}

    if not content.startswith("---"):
        return {}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    try:
        front = yaml.safe_load(parts[1])
        if isinstance(front, dict):
            return front
    except Exception:
        pass
    return {}


def _write_sender_profile(path, values):
    """Write sender identity back to sender_profile.md as YAML frontmatter."""
    lines = ["---"]
    for key, _label in SENDER_FIELDS:
        value = values.get(key, "")
        lines.append(f'{key}: "{value}"')
    lines.append("---")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _prompt_value(label, current_value):
    """Prompt for a single field; return new value or current value if empty."""
    prompt = f"{label}"
    if current_value:
        prompt += f" [{current_value}]"
    prompt += ": "
    value = input(prompt).strip()
    return value if value else current_value


def edit_sender_profile_interactive():
    """Interactively edit sender identity and persist to templates/sender_profile.md."""
    print("\n[编辑发送者信息]")
    print("直接按 Enter 保留当前值，输入新值覆盖。\n")

    # Start from .env defaults so the file is always complete
    defaults = {
        "sender_name": config.SENDER_NAME,
        "sender_title": config.SENDER_TITLE,
        "sender_company": getattr(config, "SENDER_COMPANY", ""),
        "sender_email": config.SENDER_EMAIL,
        "sender_phone": config.SENDER_PHONE,
        "sender_market_region": config.SENDER_MARKET_REGION,
    }

    current = _parse_sender_profile(config.SENDER_PROFILE_FILE)
    values = {}
    for key, label in SENDER_FIELDS:
        current_value = current.get(key) or defaults.get(key, "")
        values[key] = _prompt_value(label, current_value)

    _write_sender_profile(config.SENDER_PROFILE_FILE, values)

    # Reload in-memory config values
    config.SENDER_NAME = values.get("sender_name", config.SENDER_NAME)
    config.SENDER_TITLE = values.get("sender_title", config.SENDER_TITLE)
    config.SENDER_EMAIL = values.get("sender_email", config.SENDER_EMAIL)
    config.SENDER_PHONE = values.get("sender_phone", config.SENDER_PHONE)
    config.SENDER_MARKET_REGION = values.get("sender_market_region", config.SENDER_MARKET_REGION)
    if hasattr(config, "SENDER_COMPANY"):
        config.SENDER_COMPANY = values.get("sender_company", config.SENDER_COMPANY)

    print("\n✅ 发送者信息已保存到：{}".format(config.SENDER_PROFILE_FILE))
    return values


if __name__ == "__main__":
    edit_sender_profile_interactive()
