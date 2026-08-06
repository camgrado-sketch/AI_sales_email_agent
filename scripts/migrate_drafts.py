import csv
import html
import os

from email_agent import config, data_store


def migrate_csv_to_json():
    """One-time migration of legacy drafts.csv to drafts.json."""
    if not os.path.exists(config.DRAFTS_FILE):
        print(f"No legacy drafts file at {config.DRAFTS_FILE}. Nothing to migrate.")
        return

    drafts = []
    with open(config.DRAFTS_FILE, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            customer_id = row.get("customer_id", "").strip()
            if not customer_id:
                continue
            body = row.get("body", "")
            draft = {
                "draft_id": data_store.generate_draft_id(customer_id),
                "customer_id": customer_id,
                "email": row.get("email", ""),
                "template": "initial_contact",
                "stage": "new_lead",
                "subject": row.get("subject", ""),
                "html_body": f"<html><body><pre>{html.escape(body)}</pre></body></html>",
                "text_body": body,
                "images": [],
                "personalization_note": row.get("personalization_note", ""),
                "review_status": row.get("review_status", "pending").lower(),
                "created_at": data_store.generate_draft_id(customer_id).split("-")[0],
            }
            drafts.append(draft)

    data_store.save_drafts(drafts)
    print(f"Migrated {len(drafts)} draft(s) to {config.DRAFTS_JSON_FILE}")


if __name__ == "__main__":
    migrate_csv_to_json()
