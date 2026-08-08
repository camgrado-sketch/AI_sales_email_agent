"""双语标题语言纯净与图片渲染加固（装饰框替换 + ASCII CID）。"""

import os
import re

import yaml

from email_agent import config, email_generator, sender, template_engine
from email_agent import template_importer

CJK = re.compile("[一-鿿]")


def _make_template(name, files):
    tdir = os.path.join(config.TEMPLATES_DIR, name)
    os.makedirs(tdir, exist_ok=True)
    for fname, content in files.items():
        with open(os.path.join(tdir, fname), "w", encoding="utf-8") as f:
            f.write(content)
    return tdir


# ------------------------------------------------------------------------------
# 问题 1：双语标题 + en 语言纯净守卫
# ------------------------------------------------------------------------------

def test_render_subject_selects_language_variant():
    cfg = {
        "subject_template": "legacy",
        "subject_template_cn": "致 {{CUSTOMER_COMPANY}}",
        "subject_template_en": "Note for {{CUSTOMER_COMPANY}}",
    }
    variables = {"CUSTOMER_COMPANY": "Gensler"}
    assert email_generator._render_subject(
        cfg, variables, language="en"
    ) == "Note for Gensler"
    assert email_generator._render_subject(
        cfg, variables, language="cn"
    ) == "致 Gensler"


def test_render_subject_legacy_single_template_fallback():
    """旧模板仅有单 subject_template 时两种语言仍可渲染。"""
    cfg = {"subject_template": "Hi {{CUSTOMER_FIRST_NAME}}"}
    variables = {"CUSTOMER_FIRST_NAME": "Michael"}
    for lang in ("cn", "en"):
        assert email_generator._render_subject(
            cfg, variables, language=lang
        ) == "Hi Michael"


def test_render_subject_en_excludes_cjk_variable_values():
    """英文标题插入中文客户数据时剔除该变量并清理悬空连接词。"""
    cfg = {
        "subject_template_en": (
            "Furniture partnership inquiry for {{CUSTOMER_COMPANY}}"
            " | GRADO Contract"
        ),
    }
    variables = {"CUSTOMER_COMPANY": "字节跳动"}
    subject = email_generator._render_subject(cfg, variables, language="en")
    assert not CJK.search(subject)
    assert subject == "Furniture partnership inquiry | GRADO Contract"


def test_render_subject_en_legacy_chinese_template_falls_back():
    """信01 场景：单一中文标题模板 + en 语言 → 回退纯英文通用标题。"""
    cfg = {"subject_template": "为 {{CUSTOMER_COMPANY}} 提供公共空间家具支持"}
    variables = {"CUSTOMER_COMPANY": "字节跳动"}
    subject = email_generator._render_subject(cfg, variables, language="en")
    assert not CJK.search(subject)
    assert subject == "GRADO Contract Partnership Opportunity"
    # 中文语言不受影响
    cn = email_generator._render_subject(cfg, variables, language="cn")
    assert cn == "为 字节跳动 提供公共空间家具支持"


# ------------------------------------------------------------------------------
# 问题 2：装饰框替换 + ASCII CID
# ------------------------------------------------------------------------------

CHROME_TEMPLATE = (
    "<html><body><p>Hello</p>"
    '<div class="image-placeholder">'
    "[Image placeholder: {{IMAGE:信01_img_01}}]</div>"
    '<div style="border:1px dashed #ccc;padding:12px;text-align:center;">'
    "[图片占位符: {{IMAGE:hero}}]</div>"
    "</body></html>"
)


def _seed_image(fname):
    os.makedirs(config.IMAGES_DIR, exist_ok=True)
    path = os.path.join(config.IMAGES_DIR, fname)
    with open(path, "wb") as f:
        # JFIF header so stdlib imghdr (pre-PR#14 sender) also accepts it.
        f.write(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 16)
    return path


def test_render_strips_placeholder_chrome_and_ascii_cid(isolated_env):
    """两种装饰框形态整框替换；非 ASCII 图片名生成 ASCII cid 且与 HTML 一致。"""
    _seed_image("信01_img_01.jpg")
    _seed_image("hero.png")
    _make_template("chrome", {"template.html": CHROME_TEMPLATE})

    html, images, _ = template_engine.render("chrome", {})

    assert "image-placeholder" not in html
    assert "Image placeholder" not in html
    assert "图片占位符" not in html

    assert len(images) == 2
    cids = {
        os.path.splitext(os.path.basename(i["path"]))[0]: i["cid"]
        for i in images
    }
    cn_cid = cids["信01_img_01"]
    assert cn_cid.isascii() and re.match(r"^img_\d+", cn_cid)
    assert cids["hero"] == "hero"
    assert f'<img src="cid:{cn_cid}"' in html
    assert '<img src="cid:hero"' in html


def test_render_chrome_removed_when_asset_missing(isolated_env):
    """资产缺失时装饰框整体消失（不留破框），仅保留缺失注释。"""
    _make_template(
        "chrome_missing",
        {"template.html": (
            '<div class="image-placeholder">'
            "[Image placeholder: {{IMAGE:nope_img_01}}]</div>"
        )},
    )
    html, images, _ = template_engine.render("chrome_missing", {})
    assert images == []
    assert "image-placeholder" not in html
    assert "Missing image asset: nope_img_01" in html


def test_content_id_headers_are_ascii_end_to_end(isolated_env):
    """非 ASCII 图片名经渲染→构建邮件后，Content-ID 头部纯 ASCII。"""
    _seed_image("信01_img_01.jpg")
    _make_template(
        "cid_t",
        {"template.html": "<p>{{IMAGE:信01_img_01}}</p>"},
    )
    html, images, _ = template_engine.render("cid_t", {})
    draft = {
        "email": "to@example.com",
        "subject": "S",
        "html_body": html,
        "text_body": "t",
        "images": images,
    }
    msg, _ = sender.create_email_message(draft)
    image_parts = [
        p for p in msg.walk() if p.get_content_type().startswith("image/")
    ]
    assert image_parts
    for part in image_parts:
        assert part["Content-ID"].isascii()


def test_default_config_yaml_writes_bilingual_subjects():
    structured = {
        "subject_template": "Src",
        "subject_template_cn": "中文主题",
        "subject_template_en": "English subject",
        "variables": [],
        "images": [],
        "files": [],
    }
    cfg = yaml.safe_load(
        template_importer._default_config_yaml("t", structured, "en")
    )
    assert cfg["subject_template"] == "Src"
    assert cfg["subject_template_cn"] == "中文主题"
    assert cfg["subject_template_en"] == "English subject"
