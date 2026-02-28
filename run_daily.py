import requests
from notion_write import write_all

def main():
    items = requests.get("http://localhost:8000/get_recent_funding?since_hours=24", timeout=30).json()
    write_all(items)

if __name__ == "__main__":
    main()