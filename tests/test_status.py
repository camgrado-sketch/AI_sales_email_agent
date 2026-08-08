"""阶段 B：status.py 状态栏、data_store 回复查看、activate_template 导入日期。"""

import pytest

from email_agent import config, data_store, status, template_importer
from email_agent.cli_controller import menu_check_replies


def test_compute_status_no_template():
    result = status.compute_status()
    assert result["template_name"] == "（未选择）"
    assert result["confirmed"] is False
    assert result["send_state"] == "未选择模板"
    assert result["unseen_replies"] == 0
    assert result["color"] == "red"


def test_compute_status_with_template(make_template, write_settings):
    make_template("initial_contact")
    write_settings({
        "selected_template": "initial_contact",
        "template_confirmed": True,
        "template_imported_at": {"initial_contact": "2026-08-01"},
    })
    result = status.compute_status()
    assert result["template_name"] == "initial_contact"
    assert result["imported_at"] == "2026-08-01"
    assert result["confirmed"] is True
    assert result["send_state"] == "未发送"
    assert result["unseen_replies"] == 0
    assert result["color"] == "green"


def test_compute_status_partial_send(make_template, write_settings):
    make_template("initial_contact")
    write_settings({
        "selected_template": "initial_contact",
        "template_confirmed": True,
    })
    drafts = [
        {"draft_id": "d1", "template": "initial_contact", "review_status": "approved"},
        {"draft_id": "d2", "template": "initial_contact", "review_status": "approved"},
    ]
    data_store.save_drafts(drafts)
    data_store.append_email_log({
        "email_id": "d1",
        "customer_id": "c1",
        "recipient": "a@example.com",
        "subject": "s1",
        "send_time": "2026-08-06 10:00:00",
        "status": "success",
        "error_msg": "",
        "message_id": "msg1",
    })

    result = status.compute_status()
    assert result["send_state"] == "部分发送（剩余 1 封）"
    assert result["color"] == "yellow"


def test_compute_status_all_sent(make_template, write_settings):
    make_template("initial_contact")
    write_settings({
        "selected_template": "initial_contact",
        "template_confirmed": True,
    })
    drafts = [{"draft_id": "d1", "template": "initial_contact", "review_status": "approved"}]
    data_store.save_drafts(drafts)
    data_store.append_email_log({
        "email_id": "d1",
        "customer_id": "c1",
        "recipient": "a@example.com",
        "subject": "s1",
        "send_time": "2026-08-06 10:00:00",
        "status": "success",
        "error_msg": "",
        "message_id": "msg1",
    })

    result = status.compute_status()
    assert result["send_state"] == "已全部发送"


def test_compute_status_counts_unviewed_replies():
    data_store.append_reply_log({
        "email_id": "d1",
        "sender": "a@example.com",
        "receive_time": "2026-08-06 10:00:00",
        "content": "hello",
        "status": "replied",
    })
    data_store.append_reply_log({
        "email_id": "d2",
        "sender": "b@example.com",
        "receive_time": "2026-08-06 10:01:00",
        "content": "hi",
        "status": "viewed",
    })

    result = status.compute_status()
    assert result["unseen_replies"] == 1


def test_print_status_bar_contains_prd_fields(make_template, write_settings, capsys):
    make_template("initial_contact")
    write_settings({
        "selected_template": "initial_contact",
        "template_confirmed": True,
        "template_imported_at": {"initial_contact": "2026-08-01"},
    })
    status.print_status_bar()
    captured = capsys.readouterr()
    assert "模板: initial_contact (2026-08-01) ✅已确认" in captured.out
    assert "发送: 未发送" in captured.out
    assert "回复: 0 封" in captured.out


def test_count_and_mark_replies_viewed():
    data_store.append_reply_log({
        "email_id": "d1",
        "sender": "a@example.com",
        "receive_time": "2026-08-06 10:00:00",
        "content": "hello",
        "status": "replied",
    })
    assert data_store.count_unviewed_replies() == 1
    data_store.mark_all_replies_viewed()
    assert data_store.count_unviewed_replies() == 0
    rows = data_store.load_reply_logs()
    assert all(r["status"] == "viewed" for r in rows)


def test_activate_template_records_imported_at(make_template, tmp_path, monkeypatch):
    """Use a real markdown file so activate_template writes import date."""
    import_path = tmp_path / "import.md"
    import_path.write_text("# Hello\n\nThis is a test template.", encoding="utf-8")

    # Patch LLM call to avoid network
    structured = {
        "subject_template": "Test subject",
        "cn_html": "<html><body>中文</body></html>",
        "en_html": "<html><body>English</body></html>",
        "variables": [],
        "images": [],
        "files": [],
    }
    monkeypatch.setattr(
        template_importer, "structure_template_with_llm",
        lambda markdown, filename="": structured,
    )

    result = template_importer.activate_template("hello_template", str(import_path), force=True)
    assert result["template_name"] == "hello_template"
    imported_at = config.get_template_imported_at("hello_template")
    assert len(imported_at) == 10  # YYYY-MM-DD
    assert imported_at.startswith("2026")


def test_menu_check_replies_marks_viewed_after_save(monkeypatch, capsys):
    data_store.append_reply_log({
        "email_id": "d1",
        "sender": "a@example.com",
        "receive_time": "2026-08-06 10:00:00",
        "content": "hello",
        "status": "replied",
    })

    # Fake IMAP check returning one reply
    monkeypatch.setattr(
        "email_agent.receiver.check_replies",
        lambda dry_run=False: [{"email_id": "d1", "sender": "a@example.com"}] if dry_run else [],
    )
    monkeypatch.setattr(
        "email_agent.preview.open_replies_preview",
        lambda replies: "/tmp/preview.html",
    )

    inputs = iter(["s", "q"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    menu_check_replies()
    assert data_store.count_unviewed_replies() == 0
