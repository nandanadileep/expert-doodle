import os
import requests
from datetime import date
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DB_ID = os.environ["NOTION_DATABASE_ID"]

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# ------------------------
# CHECK IF COMPANY EXISTS
# ------------------------
def company_exists(company_key: str):
    payload = {
        "filter": {
            "property": "Company Key",
            "rich_text": {
                "equals": company_key
            }
        }
    }

    r = requests.post(
        f"https://api.notion.com/v1/databases/{DB_ID}/query",
        headers=HEADERS,
        json=payload,
        timeout=20,
    )
    r.raise_for_status()

    results = r.json().get("results", [])
    return len(results) > 0


# ------------------------
# CREATE ROW
# ------------------------
def notion_create_row(item: dict, run_date: str):
    company_key = item["name"].strip().lower()

    if company_exists(company_key):
        print(f"Skipping duplicate: {item['name']}")
        return

    props = {
        "Name": {"title": [{"text": {"content": item["name"]}}]},
        "Company Key": {"rich_text": [{"text": {"content": company_key}}]},
        "Round": {"rich_text": [{"text": {"content": item.get("round", "Unknown")}}]},
        "Amount": {"rich_text": [{"text": {"content": item.get("amount", "Unknown")}}]},
        "Funding Date": {"date": {"start": item.get("date", run_date)}},
        "HQ": {"rich_text": [{"text": {"content": item.get("hq", "")}}]},
        "Investors": {"rich_text": [{"text": {"content": item.get("investors", "")}}]},
        "Source URL": {"url": item.get("source_url", "")},
        "Run date": {"date": {"start": run_date}},
        "Status": {"select": {"name": "New"}},
    }

    payload = {
        "parent": {"database_id": DB_ID},
        "properties": props,
    }

    r = requests.post(
        "https://api.notion.com/v1/pages",
        headers=HEADERS,
        json=payload,
        timeout=20,
    )
    r.raise_for_status()

    print(f"Inserted: {item['name']}")


# ------------------------
# WRITE ALL
# ------------------------
def write_all(items: list[dict]):
    run_date = date.today().isoformat()

    for item in items:
        if not item.get("name") or not item.get("source_url"):
            continue
        notion_create_row(item, run_date)