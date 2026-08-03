import argparse

from email_agent.cli_controller import run as run_cli
from email_agent.logger import init_log_files


def main():
    parser = argparse.ArgumentParser(description="AI Sales Email Agent")
    parser.add_argument("--send", action="store_true", help="Send approved drafts (legacy CLI mode)")
    parser.add_argument("--check-replies", action="store_true", help="Check inbox for replies (legacy CLI mode)")
    parser.add_argument("--init", action="store_true", help="Initialize log files")

    args = parser.parse_args()

    # Always ensure log files exist
    init_log_files()

    if args.init:
        print("✅ Log files initialized in data/ directory.")
        return

    if args.send:
        # Lazy import allows sender refactor to happen in a later phase
        from email_agent.sender import process_drafts
        print("🚀 Starting sending process...")
        process_drafts()
        return

    if args.check_replies:
        from email_agent.receiver import check_replies
        print("🔍 Checking for replies...")
        check_replies()
        return

    # Default to interactive CLI
    run_cli()


if __name__ == "__main__":
    main()
