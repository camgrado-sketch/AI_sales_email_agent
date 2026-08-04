import os
import sys

from email_agent import config, data_store, status, template_engine, template_importer


def _clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def _print_header():
    print("=" * 60)
    print("     🤖 AI Sales Email Agent - Interactive Console")
    print("=" * 60)
    status.print_status_bar()


def _print_menu():
    print("\nMain Menu:")
    print("  1. Generate drafts")
    print("  2. Review drafts")
    print("  3. Send approved emails")
    print("  4. Check replies")
    print("  5. View logs")
    print("  6. Configuration check")
    print("  7. Switch active model")
    print("  8. Import / confirm template")
    print("  9. Toggle skill mode")
    print("  D. Delete drafts")
    print("  0. Exit")
    print()


def _wait_for_enter():
    input("\nPress Enter to return to the menu...")


def _require_confirmed_template():
    if not config.is_template_confirmed():
        print("❌ No template confirmed. Please go to menu 8 to import/confirm a template first.")
        return False
    return True


def menu_generate():
    print("\n[Generate Drafts]")
    if not _require_confirmed_template():
        return
    print("This will analyze customers and generate personalized email drafts.")
    confirm = input("Proceed? (Y/n): ").strip().lower()
    if confirm and confirm not in ("y", "yes"):
        print("Cancelled.")
        return

    try:
        from email_agent.email_generator import generate_all
        drafts = generate_all()
        print(f"✅ Generated/loaded {len(drafts)} draft(s). Saved to {config.DRAFTS_JSON_FILE}")
    except Exception as e:
        print(f"❌ Error generating drafts: {e}")


def menu_review():
    print("\n[Review Drafts]")
    drafts = data_store.load_drafts(status="pending")
    if not drafts:
        print("No pending drafts to review.")
        return

    print(f"Found {len(drafts)} pending draft(s). Reviewing one by one...\n")
    from email_agent.preview import open_draft_preview

    for draft in drafts:
        print("-" * 60)
        print(f"Customer: {draft.get('customer_id')} <{draft.get('email')}>")
        print(f"Template: {draft.get('template')} | Stage: {draft.get('stage')} | Language: {draft.get('language', 'default')}")
        print(f"Subject: {draft.get('subject')}")
        print(f"Personalization: {draft.get('personalization_note')}")
        print(f"Model: {draft.get('model_used')} | Tokens: {draft.get('generation_meta', {}).get('total_tokens', 0)}")

        try:
            preview_path = open_draft_preview(draft)
            print(f"🌐 Browser preview opened: {preview_path}")
        except Exception as e:
            print(f"⚠️ Could not open browser preview: {e}")

        while True:
            choice = input("[Y] Approve  [N] Reject  [S] Skip  [E] Edit  [Q] Quit review: ").strip().lower()
            if choice in ("y", "yes"):
                data_store.update_draft_status(draft.get("draft_id"), "approved")
                print("Approved.")
                break
            elif choice in ("n", "no"):
                data_store.update_draft_status(draft.get("draft_id"), "rejected")
                print("Rejected.")
                break
            elif choice in ("s", "skip"):
                print("Skipped.")
                break
            elif choice in ("e", "edit"):
                new_body = input("Enter updated text body (or press Enter to keep): ").strip()
                if new_body:
                    draft["text_body"] = new_body
                    all_drafts = data_store.load_drafts()
                    for i, d in enumerate(all_drafts):
                        if d.get("draft_id") == draft.get("draft_id"):
                            all_drafts[i] = draft
                            break
                    data_store.save_drafts(all_drafts)
                    print("Body updated.")
                data_store.update_draft_status(draft.get("draft_id"), "approved")
                print("Approved after edit.")
                break
            elif choice in ("q", "quit"):
                print("Exiting review.")
                return
            else:
                print("Invalid choice. Please try again.")


def menu_send():
    print("\n[Send Approved Emails]")
    if not _require_confirmed_template():
        return
    from email_agent.sender import process_queue
    process_queue()


def menu_check_replies():
    print("\n[Check Replies]")
    from email_agent.receiver import check_replies
    from email_agent.preview import open_replies_preview

    replies = check_replies(dry_run=True)
    if replies:
        try:
            preview_path = open_replies_preview(replies)
            print(f"🌐 Browser preview opened: {preview_path}")
        except Exception as e:
            print(f"⚠️ Could not open browser preview: {e}")

        while True:
            choice = input("[S] Save replies to log  [R] Refresh  [Q] Quit: ").strip().lower()
            if choice in ("s", "save"):
                check_replies(dry_run=False)
                print("✅ Replies saved to reply_logs.csv.")
                break
            elif choice in ("r", "refresh"):
                replies = check_replies(dry_run=True)
                if replies:
                    try:
                        open_replies_preview(replies)
                    except Exception as e:
                        print(f"⚠️ Could not refresh preview: {e}")
                else:
                    print("No replies found.")
            elif choice in ("q", "quit"):
                print("Cancelled without saving.")
                break
            else:
                print("Invalid choice.")
    else:
        print("No replies found.")


def menu_logs():
    print("\n[View Logs]")
    email_logs = data_store.load_email_logs()
    reply_logs = data_store.load_reply_logs()
    print(f"Email logs: {len(email_logs)} record(s)")
    if email_logs:
        for row in email_logs[-5:]:
            print(f"  - {row.get('send_time')} | {row.get('recipient')} | {row.get('status')}")
    print(f"Reply logs: {len(reply_logs)} record(s)")
    if reply_logs:
        for row in reply_logs[-5:]:
            print(f"  - {row.get('receive_time')} | {row.get('sender')} | {row.get('status')}")


def menu_config():
    print("\n[Configuration Check]")
    active = config.get_active_model()
    print(f"Email account:     {config.EMAIL_ACCOUNT or 'NOT SET'}")
    print(f"Email password:    {'SET' if config.EMAIL_PASSWORD else 'NOT SET'}")
    print(f"Active model:      {active.get('name') if active else 'NOT SET'} ({active.get('model') if active else ''})")
    print(f"Active base URL:   {active.get('base_url') or 'default' if active else ''}")
    print(f"Sender profile:    {config.SENDER_PROFILE_FILE}")
    print(f"  name:            {config.load_sender_profile().get('sender_name')}")
    print(f"  title:           {config.load_sender_profile().get('sender_title')}")
    print(f"  region:          {config.load_sender_profile().get('sender_market_region')}")
    print(f"Skill mode:        {config.SKILL_MODE}")
    print(f"Template confirmed:{config.is_template_confirmed()}")
    print(f"Demo mode:         {config.DEMO_MODE}")
    print(f"Allowed emails:    {config.ALLOWED_TEST_EMAILS}")
    print(f"Daily send limit:  {config.MAX_DAILY_SENDS}")
    print(f"Delay range:       {config.MIN_DELAY_SECONDS}s - {config.MAX_DELAY_SECONDS}s")
    print(f"Drafts JSON:       {config.DRAFTS_JSON_FILE}")
    print(f"Templates dir:     {config.TEMPLATES_DIR}")
    print(f"Images dir:        {config.IMAGES_DIR}")


def menu_switch_model():
    print("\n[Switch Active Model]")
    models = config.load_available_models()
    if not models:
        print("❌ No models configured. Check .env")
        return

    print("Available models:")
    for i, m in enumerate(models):
        marker = " *" if i == config._active_model_index() else "  "
        print(f"{marker}[{i}] {m.get('name')} ({m.get('model')})")

    choice = input(f"Select model (0-{len(models)-1}) or press Enter to keep: ").strip()
    if not choice:
        print("No change.")
        return
    try:
        idx = int(choice)
        if idx < 0 or idx >= len(models):
            print("Invalid selection.")
            return
    except ValueError:
        print("Invalid input.")
        return

    settings = data_store.load_settings()
    settings["active_model_index"] = idx
    data_store.save_settings(settings)
    print(f"✅ Active model switched to [{idx}] {models[idx].get('name')}.")


def menu_import_template():
    print("\n[Import / Confirm Template]")
    try:
        changes = template_importer.detect_changes()
    except Exception as e:
        print(f"❌ Could not scan import folder: {e}")
        return

    if not changes:
        print("No new template files detected in templates/import/.")
        print("\nCurrent templates:")
        for name in template_engine.list_templates():
            langs = template_engine.list_template_languages(name)
            print(f"  - {name}: {', '.join(langs)}")

        if config.is_template_confirmed():
            print("\nTemplate is already confirmed.")
            reset = input("Reset confirmation and require re-confirmation? (y/N): ").strip().lower()
            if reset == "y":
                settings = data_store.load_settings()
                settings["template_confirmed"] = False
                data_store.save_settings(settings)
                print("Confirmation reset. Please review and confirm below.")
            else:
                return
    else:
        print(f"Found {len(changes)} new/updated file(s):")
        for i, cand in enumerate(changes, start=1):
            print(f"  [{i}] {cand.filename}")

        choice = input("Select file number to import (or 0 to cancel): ").strip()
        if choice == "0":
            print("Cancelled.")
            return
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(changes):
                print("Invalid selection.")
                return
        except ValueError:
            print("Invalid input.")
            return

        candidate = changes[idx]
        default_name = template_importer._template_name_from_filename(candidate.filename)
        print(f"Inferred template name: {default_name}")
        name_input = input("Enter template name to import into (or press Enter to use inferred): ").strip()
        template_name = name_input or default_name

        has_work, reason = template_importer.has_unfinished_work(template_name)
        if has_work:
            print(f"\n⚠️ Warning: current template has unfinished work: {reason}")
            force = input("Importing will archive the current template. Continue? (y/N): ").strip().lower()
            if force != "y":
                print("Cancelled.")
                return

        try:
            result = template_importer.activate_template(template_name, candidate.path, force=True)
            print(f"✅ Imported as '{result['template_name']}' ({result['source_language']}).")
            print(f"   Archived old template to: {result['archive_path']}")
            template_importer.save_import_state()
        except Exception as e:
            print(f"❌ Import failed: {e}")
            return

    # Preview and confirm
    for name in template_engine.list_templates():
        try:
            preview_html = template_importer.build_preview_html(name)
            from email_agent.preview import _open_html
            preview_path = _open_html(preview_html)
            print(f"🌐 Browser preview opened for '{name}': {preview_path}")
        except Exception as e:
            print(f"⚠️ Could not open preview for '{name}': {e}")

    if config.is_template_confirmed():
        print("\nTemplate already confirmed.")
    else:
        confirm = input("Confirm this template for generation/sending? (Y/n): ").strip().lower()
        if confirm in ("y", "yes"):
            template_importer.confirm_active_template()
            print("✅ Template confirmed.")
        else:
            print("Template remains unconfirmed. Generation and sending are blocked.")


def menu_toggle_skill():
    print("\n[Toggle Skill Mode]")
    print(f"Current mode: {config.SKILL_MODE}")
    print("  full    - Use the complete email_writing_skill.md (slower, more detailed)")
    print("  concise - Use the concise version (faster, ~50 lines)")
    new_mode = input("Enter mode (full/concise) or press Enter to keep current: ").strip().lower()
    if not new_mode:
        print("No change.")
        return
    if new_mode not in ("full", "concise"):
        print("Invalid mode. Must be 'full' or 'concise'.")
        return
    settings = data_store.load_settings()
    settings["skill_mode"] = new_mode
    data_store.save_settings(settings)
    config.SKILL_MODE = new_mode
    print(f"✅ Skill mode switched to '{new_mode}'. This will be remembered for next runs.")


def menu_delete_drafts():
    print("\n[Delete Drafts]")
    drafts = data_store.load_drafts()
    if not drafts:
        print("No drafts to delete.")
        return

    print(f"Found {len(drafts)} draft(s):\n")
    for i, draft in enumerate(drafts, start=1):
        name = draft.get("customer_id", "?")
        subject = draft.get("subject", "(no subject)")
        print(f"  [{i}] {name} - {subject}")

    choice = input('\nEnter number to delete, "all" to clear everything, or 0 to cancel: ').strip()
    if choice == "0":
        print("Cancelled.")
        return

    if choice.lower() == "all":
        confirm = input("Confirm delete ALL drafts? (Y/n): ").strip().lower()
        if confirm in ("y", "yes"):
            data_store.clear_drafts()
            data_store.clear_generation_state()
            print("✅ All drafts deleted. Generation state reset.")
        else:
            print("Cancelled.")
        return

    try:
        idx = int(choice)
        if idx < 1 or idx > len(drafts):
            print("Invalid number.")
            return
    except ValueError:
        print("Invalid input.")
        return

    target = drafts[idx - 1]
    confirm = input(f"Confirm delete draft #{idx} ({target.get('subject', '')})? (Y/n): ").strip().lower()
    if confirm in ("y", "yes"):
        data_store.delete_draft(target.get("draft_id"))
        print("✅ Draft deleted.")
    else:
        print("Cancelled.")


def run():
    while True:
        _clear_screen()
        _print_header()
        _print_menu()
        choice = input("Select an option: ").strip()

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
            menu_config()
            _wait_for_enter()
        elif choice == "7":
            menu_switch_model()
            _wait_for_enter()
        elif choice == "8":
            menu_import_template()
            _wait_for_enter()
        elif choice == "9":
            menu_toggle_skill()
            _wait_for_enter()
        elif choice.lower() == "d":
            menu_delete_drafts()
            _wait_for_enter()
        elif choice == "0":
            print("\nGoodbye! 👋")
            sys.exit(0)
        else:
            print("Invalid option. Please try again.")
            _wait_for_enter()


if __name__ == "__main__":
    run()
