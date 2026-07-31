import argparse
from email_agent.logger import init_log_files
from email_agent.sender import process_drafts
from email_agent.receiver import check_replies

def main():
    parser = argparse.ArgumentParser(description="AI Sales Email Agent Demo")
    parser.add_argument("--send", action="store_true", help="Read drafts.csv and send approved emails")
    parser.add_argument("--check-replies", action="store_true", help="Check inbox for replies to sent emails")
    parser.add_argument("--init", action="store_true", help="Initialize log files")
    
    args = parser.parse_args()
    
    # Always ensure log files exist
    init_log_files()
    
    if args.init:
        print("✅ Log files initialized in data/ directory.")
        return
        
    if args.send:
        print("🚀 Starting sending process...")
        process_drafts()
        
    if args.check_replies:
        print("🔍 Checking for replies...")
        check_replies()
        
    if not (args.send or args.check_replies or args.init):
        parser.print_help()

if __name__ == "__main__":
    main()
