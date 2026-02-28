# Startup Funding Bot

Fetches recent startup funding news from RSS feeds and writes normalized entries to a Notion database.

## Features

- FastAPI endpoint to extract recent funding stories
- Heuristic parsing for company, amount, round, HQ, and investors
- Notion writer that adapts to database schema types
- Daily runner script to sync latest items

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with your Notion credentials:

```dotenv
NOTION_TOKEN=ntn_...
NOTION_DATABASE_ID=...
```

## Run API

```bash
uvicorn main:app --reload --port 8000
```

Endpoint:

```bash
GET /get_recent_funding?since_hours=24
```

## Run Daily Sync

Start API first, then run:

```bash
python run_daily.py
```
