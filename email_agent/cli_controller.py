import os
import re
import sys

from email_agent import config, data_store, sender_profile_editor, status, template_engine, template_importer


def _clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def _print_header():
    print("=" * 60)
    print("     🤖 AI 销售邮件智能助手 - 交互式控制台")
    print("=" * 60)
    status.print_status_bar()


def _print_menu():
    print("\n主菜单：")
    print("  [1] 生成草稿")
    print("  [2] 审核草稿")
    print("  [3] 发送已审核邮件")
    print("  [4] 检查回复")
    print("  [5] 查看日志")
    print("  [6] 导入 / 确认模板")
    print("  [S] 设置")
    print("  [D] 删除草稿")
    print("  [0] 退出")
    print()


def _print_settings_menu():
    print("\n设置菜单：")
    print("  [1] 发送者信息")
    print("  [2] 切换当前模型")
    print("  [3] 切换 skill 模式")
    print("  [4] 配置检查")
    print("  [0] 返回主菜单")
    print()


def _wait_for_enter():
    print("\n[Enter] 返回主菜单")
    input("按 Enter 返回主菜单...")


def _active_templates_exist():
    return bool(template_engine.list_templates())


def _prompt_with_hint(prompt, hint=""):
    """Print a hint line immediately above an input prompt."""
    if hint:
        print(f"\n{hint}")
    return input(prompt).strip()


def _require_confirmed_template():
    confirmed = config.is_template_confirmed()
    if confirmed and not _active_templates_exist():
        print("⚠️ 模板确认标志已设置，但未找到激活模板。正在重置确认状态。")
        settings = data_store.load_settings()
        settings["template_confirmed"] = False
        settings["template_confirmed_at"] = None
        data_store.save_settings(settings)
        confirmed = False
    if not confirmed:
        print("❌ 没有已确认的模板。请先到菜单 6 导入/确认模板。")
        return False
    return True


def menu_generate():
    print("\n[生成草稿]")
    if not _require_confirmed_template():
        return
    print("将根据已确认模板生成本地变量替换的邮件草稿。")
    confirm = _prompt_with_hint(
        "是否继续？ (Y/n): ",
        "[Y] 开始生成  [n] 取消"
    ).strip().lower()
    if confirm and confirm not in ("y", "yes"):
        print("已取消。")
        return

    try:
        from email_agent.email_generator import generate_all
        drafts = generate_all()
        print(f"✅ 已生成/加载 {len(drafts)} 封草稿。保存至 {config.DRAFTS_JSON_FILE}")
    except Exception as e:
        print(f"❌ 生成草稿时出错：{e}")


def menu_review():
    print("\n[审核草稿]")
    drafts = data_store.load_drafts(status="pending")
    if not drafts:
        print("没有待审核的草稿。")
        return

    print(f"找到 {len(drafts)} 封待审核草稿。逐封审核...\n")
    from email_agent.preview import open_draft_preview

    for draft in drafts:
        print("-" * 60)
        print(f"客户: {draft.get('customer_id')} <{draft.get('email')}>")
        print(f"模板: {draft.get('template')} | 阶段: {draft.get('stage')} | 语言: {draft.get('language', 'default')}")
        print(f"主题: {draft.get('subject')}")
        print(f"渲染方式: {draft.get('rendered_by', 'unknown')}")

        try:
            preview_path = open_draft_preview(draft)
            print(f"🌐 已打开预览：{preview_path}")
        except Exception as e:
            print(f"⚠️ 无法打开预览：{e}")

        while True:
            choice = _prompt_with_hint(
                "请选择：",
                "[Y] 通过  [N] 拒绝  [S] 跳过  [E] 编辑  [Q] 退出审核"
            ).strip().lower()
            if choice in ("y", "yes"):
                data_store.update_draft_status(draft.get("draft_id"), "approved")
                print("已通过。")
                break
            elif choice in ("n", "no"):
                data_store.update_draft_status(draft.get("draft_id"), "rejected")
                print("已拒绝。")
                break
            elif choice in ("s", "skip"):
                print("已跳过。")
                break
            elif choice in ("e", "edit"):
                new_body = _prompt_with_hint(
                    "输入更新后的正文：",
                    "[Enter] 保留当前正文"
                ).strip()
                if new_body:
                    draft["text_body"] = new_body
                    all_drafts = data_store.load_drafts()
                    for i, d in enumerate(all_drafts):
                        if d.get("draft_id") == draft.get("draft_id"):
                            all_drafts[i] = draft
                            break
                    data_store.save_drafts(all_drafts)
                    print("正文已更新。")
                data_store.update_draft_status(draft.get("draft_id"), "approved")
                print("编辑后已通过。")
                break
            elif choice in ("q", "quit"):
                print("退出审核。")
                return
            else:
                print("无效选择，请重试。")


def menu_send():
    print("\n[发送已审核邮件]")
    if not _require_confirmed_template():
        return
    from email_agent.sender import process_queue
    process_queue()


def menu_check_replies():
    print("\n[检查回复]")
    from email_agent.receiver import check_replies
    from email_agent.preview import open_replies_preview

    replies = check_replies(dry_run=True)
    if replies:
        try:
            preview_path = open_replies_preview(replies)
            print(f"🌐 已打开回复预览：{preview_path}")
        except Exception as e:
            print(f"⚠️ 无法打开回复预览：{e}")

        while True:
            choice = _prompt_with_hint(
                "请选择：",
                "[S] 保存回复到日志  [R] 刷新  [Q] 退出"
            ).strip().lower()
            if choice in ("s", "save"):
                check_replies(dry_run=False)
                print("✅ 回复已保存到 reply_logs.csv。")
                break
            elif choice in ("r", "refresh"):
                replies = check_replies(dry_run=True)
                if replies:
                    try:
                        open_replies_preview(replies)
                    except Exception as e:
                        print(f"⚠️ 无法刷新预览：{e}")
                else:
                    print("未找到回复。")
            elif choice in ("q", "quit"):
                print("已取消，未保存。")
                break
            else:
                print("无效选择。")
    else:
        print("未找到回复。")


def menu_logs():
    print("\n[查看日志]")
    email_logs = data_store.load_email_logs()
    reply_logs = data_store.load_reply_logs()
    print(f"发送日志：{len(email_logs)} 条记录")
    if email_logs:
        for row in email_logs[-5:]:
            print(f"  - {row.get('send_time')} | {row.get('recipient')} | {row.get('status')}")
    print(f"回复日志：{len(reply_logs)} 条记录")
    if reply_logs:
        for row in reply_logs[-5:]:
            print(f"  - {row.get('receive_time')} | {row.get('sender')} | {row.get('status')}")


def menu_config():
    print("\n[配置检查]")
    active = config.get_active_model()
    sender = config.load_sender_profile()
    print(f"邮箱账号：        {config.EMAIL_ACCOUNT or '未设置'}")
    print(f"邮箱密码：        {'已设置' if config.EMAIL_PASSWORD else '未设置'}")
    print(f"当前模型：        {active.get('name') if active else '未设置'} ({active.get('model') if active else ''})")
    print(f"模型地址：        {active.get('base_url') or 'default' if active else ''}")
    print(f"寄件人配置：      {config.SENDER_PROFILE_FILE}")
    print(f"  姓名：          {sender.get('sender_name')}")
    print(f"  职位：          {sender.get('sender_title')}")
    print(f"  公司：          {sender.get('sender_company')}")
    print(f"  邮箱：          {sender.get('sender_email')}")
    print(f"  电话：          {sender.get('sender_phone')}")
    print(f"  区域：          {sender.get('sender_market_region')}")
    print(f"Skill 模式：      {config.SKILL_MODE}")
    print(f"模板已确认：      {config.is_template_confirmed()}")
    print(f"Demo 模式：       {config.DEMO_MODE}")
    print(f"允许邮箱：        {config.ALLOWED_TEST_EMAILS}")
    print(f"日发送上限：      {config.MAX_DAILY_SENDS}")
    print(f"延迟范围：        {config.MIN_DELAY_SECONDS}s - {config.MAX_DELAY_SECONDS}s")
    print(f"草稿文件：        {config.DRAFTS_JSON_FILE}")
    print(f"模板目录：        {config.TEMPLATES_DIR}")
    print(f"图片目录：        {config.IMAGES_DIR}")
    print(f"文件目录：        {config.FILES_DIR}")


def menu_switch_model():
    print("\n[切换当前模型]")
    models = config.load_available_models()
    if not models:
        print("❌ 未配置模型，请检查 .env")
        return

    print("可用模型：")
    for i, m in enumerate(models):
        marker = " *" if i == config._active_model_index() else "  "
        print(f"{marker}[{i}] {m.get('name')} ({m.get('model')})")

    choice = _prompt_with_hint(
        f"请选择模型（0-{len(models)-1}）或按 Enter 保持当前：",
        "输入模型编号或按 Enter 保持当前模型"
    )
    if not choice:
        print("无变化。")
        return
    try:
        idx = int(choice)
        if idx < 0 or idx >= len(models):
            print("无效选择。")
            return
    except ValueError:
        print("无效输入。")
        return

    settings = data_store.load_settings()
    settings["active_model_index"] = idx
    data_store.save_settings(settings)
    print(f"✅ 已切换到模型 [{idx}] {models[idx].get('name')}。")


def menu_toggle_skill():
    print("\n[切换 skill 模式]")
    print(f"当前模式：{config.SKILL_MODE}")
    print("  full    - 使用完整版 email_writing_skill.md（仅模板导入参考）")
    print("  concise - 使用精简版（仅模板导入参考）")
    new_mode = _prompt_with_hint(
        "输入模式（full/concise）或按 Enter 保持当前：",
        "[full] 完整 skill  [concise] 精简 skill  [Enter] 保持当前"
    ).strip().lower()
    if not new_mode:
        print("无变化。")
        return
    if new_mode not in ("full", "concise"):
        print("无效模式，必须是 'full' 或 'concise'。")
        return
    settings = data_store.load_settings()
    settings["skill_mode"] = new_mode
    data_store.save_settings(settings)
    config.SKILL_MODE = new_mode
    print(f"✅ Skill 模式已切换为 '{new_mode}'。下次启动仍有效。")


def menu_sender_profile():
    sender_profile_editor.edit_sender_profile_interactive()


def menu_settings():
    while True:
        _print_settings_menu()
        choice = _prompt_with_hint(
            "请选择设置项：",
            "[1]发送者信息 [2]切换模型 [3]切换skill [4]配置检查 [0]返回"
        ).strip()

        if choice == "1":
            menu_sender_profile()
            _wait_for_enter()
        elif choice == "2":
            menu_switch_model()
            _wait_for_enter()
        elif choice == "3":
            menu_toggle_skill()
            _wait_for_enter()
        elif choice == "4":
            menu_config()
            _wait_for_enter()
        elif choice == "0":
            print("返回主菜单。")
            break
        else:
            print("无效选择。")
            _wait_for_enter()


def menu_manage_archives():
    """List and delete archived templates organized by template_name/YYYY/MM/DD."""
    print("\n[管理模板归档]")
    archives = template_importer.list_archive_folders()
    if not archives:
        print("未找到模板归档。")
        return

    print(f"发现 {len(archives)} 个归档：\n")
    for i, entry in enumerate(archives, start=1):
        print(f"  [{i}] {entry['date']} - {entry['name']}")

    choice = _prompt_with_hint(
        '请输入编号、"all" 或 0：',
        '输入编号删除，"all" 清空全部，0 取消'
    ).strip()
    if choice == "0":
        print("已取消。")
        return

    if choice.lower() == "all":
        confirm = _prompt_with_hint(
            "确认删除全部归档？ (Y/n): ",
            "[Y] 删除全部归档  [n] 取消"
        ).strip().lower()
        if confirm in ("y", "yes"):
            for entry in archives:
                template_importer.delete_archive_entry(entry["path"])
            print("✅ 已全部删除归档。")
        else:
            print("已取消。")
        return

    try:
        idx = int(choice)
        if idx < 1 or idx > len(archives):
            print("无效编号。")
            return
    except ValueError:
        print("无效输入。")
        return

    target = archives[idx - 1]
    confirm = _prompt_with_hint(
        f"确认删除归档 #{idx}（{target['date']} - {target['name']}）? (Y/n): ",
        "[Y] 删除此归档  [n] 取消"
    ).strip().lower()
    if confirm in ("y", "yes"):
        template_importer.delete_archive_entry(target["path"])
        print("✅ 归档已删除。")
    else:
        print("已取消。")


def _import_template_flow():
    """Import a new template file from templates/import/."""
    try:
        changes = template_importer.detect_changes()
    except Exception as e:
        print(f"❌ 无法扫描导入文件夹：{e}")
        return

    if not changes:
        print("未检测到新模板文件。")
        return

    print(f"发现 {len(changes)} 个新/已更新文件：")
    for i, cand in enumerate(changes, start=1):
        print(f"  [{i}] {cand.filename}")

    choice = _prompt_with_hint(
        "请选择文件编号（0 取消）：",
        "输入要导入的文件编号"
    ).strip()
    if choice == "0":
        print("已取消。")
        return
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(changes):
            print("无效选择。")
            return
    except ValueError:
        print("无效输入。")
        return

    candidate = changes[idx]
    default_name = template_importer._template_name_from_filename(candidate.filename)
    print(f"从文件名推断模板：{default_name}")
    name_input = _prompt_with_hint(
        "输入模板名（直接回车使用默认值）：",
        "[Enter] 使用默认模板名"
    ).strip()
    template_name = name_input or default_name

    has_work, reason = template_importer.has_unfinished_work(template_name)
    if has_work:
        print(f"\n⚠️ 警告：当前模板有未完成任务：{reason}")
        force = _prompt_with_hint(
            "是否继续？ (y/N): ",
            "导入将归档当前模板"
        ).strip().lower()
        if force != "y":
            print("已取消。")
            return

    try:
        result = template_importer.activate_template(
            template_name, candidate.path, force=True
        )
        print(f"✅ 已导入为 '{result['template_name']}' ({result['source_language']})，已生成 {result['target_language']} 版本。")
        print(f"   主模板：{result['main_path']}")
        print(f"   双语模板：{result['other_path']}")
        if result.get("archive_path"):
            print(f"   旧模板已归档至：{result['archive_path']}")
        template_importer.save_import_state()
    except Exception as e:
        print(f"❌ 导入失败：{e}")
        return

    # Preview and confirm immediately after import
    _confirm_template_flow()


def _confirm_template_flow():
    """Preview active templates and confirm/reset the confirmation flag."""
    from email_agent.preview import open_template_preview

    templates = template_engine.list_templates()
    if not templates:
        print("没有激活模板可供确认。请先导入模板。")
        return

    for name in templates:
        try:
            preview_path = open_template_preview(name)
            print(f"🌐 已打开模板 '{name}' 的预览：{preview_path}")
        except Exception as e:
            print(f"⚠️ 无法打开模板 '{name}' 的预览：{e}")

    if config.is_template_confirmed():
        reset = _prompt_with_hint(
            "是否重置确认状态并要求重新确认？ (y/N): ",
            "[y] 重置确认  [Enter/N] 保持当前确认"
        ).strip().lower()
        if reset == "y":
            settings = data_store.load_settings()
            settings["template_confirmed"] = False
            settings["template_confirmed_at"] = None
            data_store.save_settings(settings)
            print("确认状态已重置。请在下方的预览后重新确认。")
        else:
            return

    confirm = _prompt_with_hint(
        "确认将此模板用于生成/发送？ (Y/n): ",
        "[Y] 确认  [n] 保持未确认"
    ).strip().lower()
    if confirm in ("y", "yes"):
        template_importer.confirm_active_template()
        print("✅ 模板已确认。")
    else:
        print("模板保持未确认。生成和发送已被阻断。")


def menu_import_template():
    print("\n[导入 / 确认模板]")

    # Detect stale import state when active templates are gone
    if template_importer.is_import_state_stale():
        print("检测到导入状态已过期：templates/email/ 为空，但 templates/import/ 中仍有已记录的文件。")
        reset = _prompt_with_hint(
            "是否重置导入状态并重新导入现有文件？ (Y/n): ",
            "[Y] 重置并继续  [n] 取消"
        ).strip().lower()
        if reset in ("y", "yes"):
            template_importer.reset_import_state()
            print("导入状态已重置。")
        else:
            print("已取消。")
            return

    while True:
        templates = template_engine.list_templates()
        print("\n当前激活模板：")
        if templates:
            for name in templates:
                langs = template_engine.list_template_languages(name)
                print(f"  - {name}: {', '.join(langs)}")
        else:
            print("  （无）")

        confirmed = config.is_template_confirmed()
        print(f"\n模板已确认：{'是' if confirmed else '否'}")

        if confirmed and not templates:
            print("⚠️ 模板已确认但未找到激活模板，正在重置确认状态。")
            settings = data_store.load_settings()
            settings["template_confirmed"] = False
            settings["template_confirmed_at"] = None
            data_store.save_settings(settings)
            confirmed = False

        choice = _prompt_with_hint(
            "请选择：",
            "[I] 导入新文件  [M] 管理归档  [R] 重置导入状态  [C] 确认/重置  [Q] 返回"
        ).strip().lower()

        if choice in ("i", "import"):
            _import_template_flow()
        elif choice in ("m", "manage"):
            menu_manage_archives()
        elif choice in ("r", "reset"):
            template_importer.reset_import_state()
            print("导入状态已重置。请重新选择导入。")
        elif choice in ("c", "confirm"):
            _confirm_template_flow()
        elif choice in ("q", "quit"):
            print("返回主菜单。")
            break
        else:
            print("无效选择。")


def menu_delete_drafts():
    print("\n[删除草稿]")
    drafts = data_store.load_drafts()
    if not drafts:
        print("没有草稿可删除。")
        return

    print(f"发现 {len(drafts)} 封草稿：\n")
    for i, draft in enumerate(drafts, start=1):
        name = draft.get("customer_id", "?")
        subject = draft.get("subject", "(无主题)")
        print(f"  [{i}] {name} - {subject}")

    choice = _prompt_with_hint(
        '\n请输入编号、"all" 或 0：',
        '输入编号删除，"all" 清空全部，0 取消'
    ).strip()
    if choice == "0":
        print("已取消。")
        return

    if choice.lower() == "all":
        confirm = _prompt_with_hint(
            "确认删除全部草稿？ (Y/n): ",
            "[Y] 删除全部草稿  [n] 取消"
        ).strip().lower()
        if confirm in ("y", "yes"):
            data_store.clear_drafts()
            data_store.clear_generation_state()
            print("✅ 全部草稿已删除。生成状态已重置。")
        else:
            print("已取消。")
        return

    try:
        idx = int(choice)
        if idx < 1 or idx > len(drafts):
            print("无效编号。")
            return
    except ValueError:
        print("无效输入。")
        return

    target = drafts[idx - 1]
    confirm = _prompt_with_hint(
        f"确认删除草稿 #{idx}（{target.get('subject', '')}）? (Y/n): ",
        "[Y] 删除此草稿  [n] 取消"
    ).strip().lower()
    if confirm in ("y", "yes"):
        data_store.delete_draft(target.get("draft_id"))
        print("✅ 草稿已删除。")
    else:
        print("已取消。")


def run():
    while True:
        _clear_screen()
        _print_header()
        _print_menu()
        choice = _prompt_with_hint(
            "请选择操作：",
            "[1]生成 [2]审核 [3]发送 [4]回复 [5]日志 [6]模板 [S]设置 [D]删除 [0]退出"
        ).strip()

        if choice == "1":
            menu_generate()
            _wait_for_enter()
        elif choice == "2":
            menu_review()
            _wait_for_enter()
        elif choice == "3":
            menu_send()
            _wait_for_enter()
        elif choice == "4":
            menu_check_replies()
            _wait_for_enter()
        elif choice == "5":
            menu_logs()
            _wait_for_enter()
        elif choice == "6":
            menu_import_template()
            _wait_for_enter()
        elif choice.lower() == "s":
            menu_settings()
        elif choice.lower() == "d":
            menu_delete_drafts()
            _wait_for_enter()
        elif choice == "0":
            print("\n再见！👋")
            sys.exit(0)
        else:
            print("无效选项，请重试。")
            _wait_for_enter()


if __name__ == "__main__":
    run()
