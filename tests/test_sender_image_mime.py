"""图片附件 MIME 探测加固：ICC 配置 JPEG 等 imghdr 盲区不得导致发送崩溃。"""

import os
import struct
import zlib

import pytest

from email_agent import config, data_store, deliverability, sender


def _icc_jpeg_bytes():
    """Minimal JPEG starting with an APP2 ICC_PROFILE marker (bug repro)."""
    payload = b"ICC_PROFILE\x00\x01\x01" + b"\x00" * 16
    app2 = b"\xff\xe2" + struct.pack(">H", len(payload) + 2) + payload
    return b"\xff\xd8\xff" + app2[1:] + b"\xff\xd9"


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


def _write_image(fname, data):
    path = os.path.join(config.IMAGES_DIR, fname)
    os.makedirs(config.IMAGES_DIR, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


def test_guess_subtype_icc_profile_jpeg():
    """根因回归：带 ICC 色彩配置的 JPEG（APP2 开头）必须识别为 jpeg。"""
    data = _icc_jpeg_bytes()
    assert data[:3] == b"\xff\xd8\xff" and data[3:4] == b"\xe2"
    assert sender.guess_image_subtype(data, "assets/images/x.jpg") == "jpeg"


@pytest.mark.parametrize("data,expected", [
    (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00", "jpeg"),
    (_png_bytes(), "png"),
    (b"GIF89a\x01\x00\x01\x00\x00\x00\x00;", "gif"),
    (b"GIF87a\x01\x00\x01\x00\x00\x00\x00;", "gif"),
    (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "webp"),
    (b"BM\x00\x00\x00\x00", "bmp"),
    (b"II\x2a\x00\x08\x00\x00\x00", "tiff"),
    (b"MM\x00\x2a\x00\x00\x00\x08", "tiff"),
    (b"<?xml version='1.0'?><svg></svg>", "svg+xml"),
])
def test_guess_subtype_common_formats(data, expected):
    assert (
        sender.guess_image_subtype(data, "assets/images/ignored.xyz")
        == expected
    )


def test_guess_subtype_falls_back_to_extension():
    """魔数未命中时按扩展名兜底（如未来新增格式先落盘后识别）。"""
    assert sender.guess_image_subtype(b"\x00\x99\x88", "a/hero.png") == "png"


def test_guess_subtype_unknown_raises_chinese_error():
    """无法识别时抛出指明具体文件的中文错误，而不是天书 TypeError。"""
    with pytest.raises(ValueError) as excinfo:
        sender.guess_image_subtype(
            b"not an image at all", "assets/images/bad.bin"
        )
    assert "无法识别图片格式" in str(excinfo.value)
    assert "bad.bin" in str(excinfo.value)


def test_create_email_message_attaches_icc_jpeg_with_cid():
    """端到端：真实缺陷场景（ICC JPEG 草稿）可构建邮件且 CID 引用保留。"""
    path = _write_image("icc_img_01.jpg", _icc_jpeg_bytes())
    draft = {
        "email": "to@example.com",
        "subject": "Test",
        "html_body": "<html><body><img src='cid:hero'></body></html>",
        "text_body": "text body",
        "images": [{"cid": "hero", "path": path}],
    }
    msg, _ = sender.create_email_message(draft)

    image_parts = [
        p for p in msg.walk() if p.get_content_type().startswith("image/")
    ]
    assert len(image_parts) == 1
    part = image_parts[0]
    assert part.get_content_type() == "image/jpeg"
    assert part["Content-ID"] == "<hero>"
    assert part.get_content_disposition() == "inline"


def test_send_email_logs_failure_on_unrecognizable_image(monkeypatch):
    """发送隔离：无法识别的图片使该封邮件记 failed 并跳过，不抛出、不杀队列。"""
    monkeypatch.setattr(
        deliverability, "can_send", lambda draft, history: (True, "")
    )
    path = _write_image("broken.bin", b"this is not an image")
    draft = {
        "draft_id": "d-broken-img",
        "customer_id": "001",
        "email": "camgrado@gmail.com",
        "subject": "S",
        "html_body": "<img src='cid:x'>",
        "text_body": "t",
        "images": [{"cid": "x", "path": path}],
    }

    assert sender.send_email(draft) is False

    logs = data_store.load_email_logs()
    assert logs and logs[-1]["status"] == "failed"
    assert "邮件构建失败" in logs[-1]["error_msg"]
    assert "无法识别图片格式" in logs[-1]["error_msg"]
