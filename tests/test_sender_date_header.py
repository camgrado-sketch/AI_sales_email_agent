# -*- coding: utf-8 -*-
"""Issue #27 回归：Date 邮件头 + MIME/UTF-8 序列化往返防护。

根因：`create_email_message()` 只设置 From/To/Subject/Message-ID，
smtplib 也不会补 Date，导致发出的邮件缺失 RFC 5322 必需的 Date 头
（用户副本缺 Date、退信显示 1970 与此一致）。

MIME 编码差异排查记录：用当前 develop 代码走真实构建 → smtplib 等价
序列化（Compat32 + BytesGenerator）→ 重新解析路径，Content-Type/charset/
Content-Transfer-Encoding 完整，中文、弯引号、长破折号与主题往返无损，
**未复现**"副本缺 MIME 头及乱码"。本文件的往返断言作为编码回归防护；
若用户副本再次出现该现象，应核查运行版本与退信附件导出/重建路径，
而非修改构建代码。

全部使用合成数据，不连接真实 SMTP。
"""

import io
import re
import struct
import zlib
from datetime import datetime, timedelta, timezone
from email.generator import BytesGenerator
from email.parser import BytesParser
from email.policy import default as default_policy
from email.utils import parsedate_to_datetime

import pytest

from email_agent import config, data_store, deliverability, sender

SUBJECT = "合作邀约 — GRADO Contract “开发信” 测试"
TEXT_BODY = "您好：测试邮件，含中文、弯引号 “double” ‘single’ 和长破折号 —— end."
HTML_BODY = "<p>您好：<b>测试</b>，弯引号 “double” 和长破折号 —— end.</p>"


def _make_draft(**overrides):
    draft = {
        "email": "synthetic-recipient@example.org",
        "subject": SUBJECT,
        "text_body": TEXT_BODY,
        "html_body": HTML_BODY,
        "images": [],
    }
    draft.update(overrides)
    return draft


def _png_bytes():
    def chunk(typ, data):
        return (
            struct.pack(">I", len(data)) + typ + data
            + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        )
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    )


def _serialize_like_smtplib(msg):
    """复刻 smtplib.send_message 的线上字节（Compat32 + BytesGenerator）。"""
    buf = io.BytesIO()
    BytesGenerator(buf, mangle_from_=False, maxheaderlen=0).flatten(msg)
    return buf.getvalue()


def _roundtrip(msg):
    """构建 → 序列化 → 重新解析。"""
    return BytesParser(policy=default_policy).parsebytes(_serialize_like_smtplib(msg))


def _count_date_headers(wire):
    return len(re.findall(rb"(?im)^Date:", wire))


@pytest.fixture(autouse=True)
def _synthetic_account(monkeypatch):
    monkeypatch.setattr(config, "EMAIL_ACCOUNT", "synthetic-sender@example.com")


# ---------------------------------------------------------------- Date 头


def test_date_header_present_once_in_wire():
    """根因回归：线上字节必须含且仅含一个 Date 头（此前完全缺失）。"""
    msg, _ = sender.create_email_message(_make_draft())
    wire = _serialize_like_smtplib(msg)
    assert _count_date_headers(wire) == 1


def test_date_header_parseable_tz_aware_and_recent():
    """Date 可解析、带明确时区、接近消息构建时间。"""
    before = datetime.now(timezone.utc)
    msg, _ = sender.create_email_message(_make_draft())
    after = datetime.now(timezone.utc)

    reparsed = _roundtrip(msg)
    date_value = reparsed["Date"]
    assert date_value, "重新解析后 Date 头缺失"

    dt = parsedate_to_datetime(date_value)
    assert dt.tzinfo is not None, "Date 必须带明确时区"
    assert before - timedelta(seconds=5) <= dt <= after + timedelta(seconds=5)


def test_message_id_remains_valid_and_unique():
    """修复不得影响 Message-ID 的有效性与唯一性。"""
    msg1, mid1 = sender.create_email_message(_make_draft())
    msg2, mid2 = sender.create_email_message(_make_draft())
    assert msg1["Message-ID"] == mid1
    assert mid1 != mid2
    assert re.fullmatch(r"<[^>]+@[^>]+>", mid1)


# ------------------------------------------------- MIME/UTF-8 往返防护（未复现记录）


def test_mime_headers_survive_serialization():
    """副本缺 MIME 头未在构建路径复现：顶层与文本 part 头必须完整。"""
    msg, _ = sender.create_email_message(_make_draft())
    reparsed = _roundtrip(msg)

    assert reparsed["MIME-Version"] == "1.0"
    assert reparsed.get_content_type() == "multipart/related"

    text_parts = [
        p for p in reparsed.walk() if p.get_content_type() == "text/plain"
    ]
    html_parts = [
        p for p in reparsed.walk() if p.get_content_type() == "text/html"
    ]
    assert text_parts and html_parts
    for part in text_parts + html_parts:
        assert part.get_content_charset() == "utf-8"
        assert part["Content-Transfer-Encoding"] in ("base64", "quoted-printable")


def test_utf8_subject_and_bodies_roundtrip_identically():
    """中文、弯引号、长破折号与主题经线上路径往返必须逐字一致。"""
    msg, _ = sender.create_email_message(_make_draft())
    reparsed = _roundtrip(msg)

    assert str(reparsed["Subject"]) == SUBJECT

    contents = {
        p.get_content_type(): p.get_content()
        for p in reparsed.walk() if not p.is_multipart()
    }
    assert contents["text/plain"].rstrip("\n") == TEXT_BODY
    assert contents["text/html"].rstrip("\n") == HTML_BODY


def test_plain_text_draft_roundtrip():
    """纯文本草稿（html_body 为空）场景不回归。"""
    draft = _make_draft(html_body="")
    msg, _ = sender.create_email_message(draft)
    reparsed = _roundtrip(msg)

    text_parts = [
        p for p in reparsed.walk() if p.get_content_type() == "text/plain"
    ]
    assert text_parts[0].get_content_charset() == "utf-8"
    assert text_parts[0].get_content().rstrip("\n") == TEXT_BODY


def test_cid_image_roundtrip_intact(tmp_path):
    """CID 内嵌图片经序列化往返后内容与引用完好。"""
    img_path = tmp_path / "hero.png"
    img_data = _png_bytes()
    img_path.write_bytes(img_data)

    draft = _make_draft(
        html_body="<p>x</p><img src='cid:hero'>",
        images=[{"cid": "hero", "path": str(img_path)}],
    )
    msg, _ = sender.create_email_message(draft)
    reparsed = _roundtrip(msg)

    image_parts = [
        p for p in reparsed.walk() if p.get_content_type() == "image/png"
    ]
    assert len(image_parts) == 1
    assert image_parts[0]["Content-ID"] == "<hero>"
    assert image_parts[0].get_payload(decode=True) == img_data


# ------------------------------------------------------- mock SMTP 端到端


class _FakeSMTPSSL:
    """记录 send_message 线上字节的假 SMTP_SSL，不建立任何网络连接。"""

    captured_wire = None

    def __init__(self, host, port):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        # 与 smtplib.send_message(非 SMTPUTF8)等价：msg.as_bytes()
        _FakeSMTPSSL.captured_wire = msg.as_bytes()

    def quit(self):
        pass


def test_send_email_via_mock_smtp_has_single_date_and_logs(monkeypatch):
    """端到端：mock SMTP 提交成功、Date 恰好一个、日志关联 Message-ID。"""
    monkeypatch.setattr(sender.smtplib, "SMTP_SSL", _FakeSMTPSSL)
    monkeypatch.setattr(
        deliverability, "can_send", lambda draft, history: (True, "")
    )
    _FakeSMTPSSL.captured_wire = None

    draft = _make_draft(draft_id="d-issue27", customer_id="synthetic-001")
    assert sender.send_email(draft) is True

    wire = _FakeSMTPSSL.captured_wire
    assert wire is not None
    assert _count_date_headers(wire) == 1

    reparsed = BytesParser(policy=default_policy).parsebytes(wire)
    dt = parsedate_to_datetime(reparsed["Date"])
    assert dt.tzinfo is not None

    logs = data_store.load_email_logs()
    assert logs and logs[-1]["status"] == "success"
    # 日志中的 Message-ID 与线上字节一致，保持关联
    assert logs[-1]["message_id"] == reparsed["Message-ID"]
