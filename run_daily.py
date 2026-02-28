import os, time, requests
from notion_write import write_all

API_URL = os.environ["FUNDING_API_URL"]

def get_json_with_retry(url, tries=3):
    for i in range(tries):
        try:
            return requests.get(url, timeout=90).json()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(10)

def main():
    items = get_json_with_retry(f"{API_URL}/get_recent_funding?since_hours=24")
    write_all(items)

if __name__ == "__main__":
    main()