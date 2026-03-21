import os, time, requests
from notion_write import write_all

API_URL = os.environ["FUNDING_API_URL"]

def get_json_with_retry(url, retries=3, timeout=120):
    for i in range(retries):
        try:
            return requests.get(url, timeout=timeout).json()
        except requests.exceptions.ReadTimeout:
            print(f"Timeout on attempt {i+1}, retrying...")
            time.sleep(30)  # wait 30s for Render to wake up
    raise Exception("All retries failed")

def main():
    items = get_json_with_retry(f"{API_URL}/get_recent_funding?since_hours=24")
    write_all(items)

if __name__ == "__main__":
    main()
