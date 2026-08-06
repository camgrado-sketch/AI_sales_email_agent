"""阶段 A.4：email_generator 不再按销售阶段自动选择模板，必须显式 selected_template。"""

import pytest

from email_agent import config, email_generator


def test_generate_for_customer_requires_selected_template(make_template, write_settings):
    make_template("initial_contact")
    write_settings({"selected_template": "", "template_confirmed": True})
    customer = {"id": "c1", "name": "Test", "email": "t@example.com", "company": "Acme"}
    with pytest.raises(RuntimeError, match="未选择生效模板"):
        email_generator.generate_for_customer(customer)


def test_generate_uses_selected_template(make_template, write_settings):
    make_template("initial_contact")
    write_settings({"selected_template": "initial_contact", "template_confirmed": True})
    customer = {"id": "c2", "name": "Alice", "email": "a@example.com", "company": "Acme"}

    draft = email_generator.generate_for_customer(customer)
    assert draft["template"] == "initial_contact"
    assert draft["rendered_by"] == "local"


def test_generate_rejects_missing_selected_template(make_template, write_settings):
    make_template("initial_contact")
    write_settings({"selected_template": "does_not_exist", "template_confirmed": True})
    customer = {"id": "c3", "name": "Bob", "email": "b@example.com", "company": "Acme"}
    with pytest.raises(RuntimeError, match="生效模板 'does_not_exist' 不存在"):
        email_generator.generate_for_customer(customer)


def test_stage_no_longer_affects_template(make_template, write_settings):
    make_template("initial_contact")
    write_settings({"selected_template": "initial_contact", "template_confirmed": True})
    # Customer with follow-up history would previously select final_note
    customer = {"id": "c4", "name": "Carol", "email": "c@example.com", "company": "Acme"}
    draft = email_generator.generate_for_customer(customer)
    assert draft["template"] == config.get_selected_template()
