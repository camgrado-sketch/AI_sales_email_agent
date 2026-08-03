import os
import sys

from email_agent import config, data_store


def _clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def _print_header():
    print("=" * 60)
    print("     🤖 AI Sales Email Agent - Interactive Console")
    print("=" * 60)


def _print_menu():
    print("\nMain Menu:")
    print("  1. Generate drafts")
    print("  2. Review drafts")
    print("  3. Send approved emails")
    print("  4. Check replies")
    print("  5. View logs")
    print("  6. Configuration check")
    print("  0. Exit")
    print()


def _wait_for_enter():
    input("\nPress Enter to return to the menu...")


def menu_generate():
    print("\n[Generate Drafts]")
    print("This will analyze customers and generate personalized email drafts.")
    confirm = input("Proceed? (Y/n): ").strip().lower()
    if confirm and confirm not in ("y", "yes"):
        print("Cancelled.")
        return

    try:
        # Lazy import to avoid circular dependencies while other modules are developed
        from email_agent.email_generator import generate_all
        drafts = generate_all()
        print(f"✅ Generated {len(drafts)} draft(s). Saved to {config.DRAFTS_JSON_FILE}")
    except Exception as e:
        print(f"❌ Error generating drafts: {e}")


def menu_review():
    print("\n[Review Drafts]")
    drafts = data_store.load_drafts(status="pending")
    if not drafts:
        print("No pending drafts to review.")
        return

    print(f"Found {len(drafts)} pending draft(s). Reviewing one by one...\n")
    for draft in drafts:
        print("-" * 60)
        print(f"Customer: {draft.get('customer_id')} <{draft.get('email')}>")
        print(f"Template: {draft.get('template')} | Stage: {draft.get('stage')}")
        print(f"Subject: {draft.get('subject')}")
        print(f"Personalization: {draft.get('personalization_note')}")
        print("\nBody preview (first 400 chars):")
        text = draft.get("text_body") or draft.get("html_body", "")
        print(text[:400] + ("..." if len(text) > 400 else ""))
        print()

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
    from email_agent.sender import process_queue
    process_queue()


def menu_check_replies():
    print("\n[Check Replies]")
    from email_agent.receiver import check_replies
    check_replies()


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
    print(f"Email account:     {config.EMAIL_ACCOUNT or 'NOT SET'}")
    print(f"Email password:    {'SET' if config.EMAIL_PASSWORD else 'NOT SET'}")
    print(f"LLM API key:       {'SET' if config.LLM_API_KEY else 'NOT SET'}")
    print(f"LLM model:         {config.LLM_MODEL}")
    print(f"LLM base URL:      {config.LLM_BASE_URL or 'default'}")
    print(f"Demo mode:         {config.DEMO_MODE}")
    print(f"Allowed emails:    {config.ALLOWED_TEST_EMAILS}")
    print(f"Daily send limit:  {config.MAX_DAILY_SENDS}")
    print(f"Delay range:       {config.MIN_DELAY_SECONDS}s - {config.MAX_DELAY_SECONDS}s")
    print(f"Drafts JSON:       {config.DRAFTS_JSON_FILE}")
    print(f"Templates dir:     {config.TEMPLATES_DIR}")
    print(f"Images dir:        {config.IMAGES_DIR}")


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
        elif choice == "0":
            print("\nGoodbye! 👋")
            sys.exit(0)
        else:
            print("Invalid option. Please try again.")
            _wait_for_enter()


if __name__ == "__main__":
    run()
