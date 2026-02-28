import os, requests
from notion_write import write_all

API_URL = os.environ.get("FUNDING_API_URL")  # set in GitHub Actions

def main():
    items = requests.get(f"{API_URL}/get_recent_funding?since_hours=24", timeout=60).json()
    write_all(items)

if __name__ == "__main__":
    main()