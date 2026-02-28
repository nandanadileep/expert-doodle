from fastapi import FastAPI
import feedparser, requests, re, os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from ftfy import fix_text
from dotenv import load_dotenv
from typing import Optional

load_dotenv()
app = FastAPI()

FEEDS = [
    # Inc42 buzz feed (often includes funding)
    "https://inc42.com/buzz/feed/",
    # Entrackr (general; funding items appear mixed)
    "https://entrackr.com/feed/",
]

FUNDING_VERBS = r"(raises|raised|bags|secures|gets|closes|snags|funding)"
ROUNDUP_HINTS = r"(this week|weekly|roundup|top\s+\d+|startups raised|from .* to .*)"

UA = {"User-Agent": "startup-funding-bot/1.0"}

def clean(s: str) -> str:
    return fix_text(s or "").strip()

def looks_like_single_funding(title: str) -> bool:
    t = clean(title).lower()
    if re.search(ROUNDUP_HINTS, t):
        return False
    return bool(re.search(rf"\b{FUNDING_VERBS}\b", t))

def extract_company_from_title(title: str) -> Optional[str]:
    t = clean(title)
    tl = t.lower()
    m = re.match(rf"^(.+?)\s+{FUNDING_VERBS}\b", tl, flags=re.IGNORECASE)
    if not m:
        return None
    company = t[: len(m.group(1))].strip(" -–—:|")
    company = clean(company)
    return company if company else None

def parse_amount(text: str) -> str:
    # $20M, $220 Mn, ₹100 Cr, etc
    m = re.search(r"(\$|₹)\s?\d+(\.\d+)?\s?(mn|m|bn|b|cr|crore|l|lakh)?", text, re.IGNORECASE)
    return clean(m.group(0)) if m else "Unknown"

def extract_investors_from_html(html: str) -> str:
    # best-effort heuristic: look for "led by" / "participation from"
    txt = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    txt = re.sub(r"\s+", " ", txt)
    m = re.search(r"(led by|participation from|backed by|investors include)\s+([^.\n]{20,180})", txt, re.IGNORECASE)
    if not m:
        return ""
    chunk = m.group(2)
    # stop at common separators
    chunk = re.split(r"( in a | while | that | which )", chunk, maxsplit=1, flags=re.IGNORECASE)[0]
    return clean(chunk)

def guess_round_from_text(text: str) -> str:
    t = text.lower()
    for r in ["pre-seed", "seed", "series a", "series b", "series c", "series d", "bridge", "debt"]:
        if r in t:
            return r.title().replace("Series", "Series")
    return "Unknown"

def guess_hq_from_text(text: str) -> str:
    # lightweight; you can extend later
    cities = ["bengaluru", "bangalore", "mumbai", "delhi", "gurugram", "hyderabad", "chennai", "pune", "dubai"]
    tl = text.lower()
    for c in cities:
        if c in tl:
            return c.title()
    return "India"

def fetch(url: str) -> str:
    r = requests.get(url, headers=UA, timeout=15)
    r.raise_for_status()
    return r.text

@app.get("/get_recent_funding")
def get_recent_funding(since_hours: int = 24):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    out = []
    seen = set()

    for feed_url in FEEDS:
        feed = feedparser.parse(feed_url)
        for e in getattr(feed, "entries", []):
            title = clean(getattr(e, "title", ""))
            link = clean(getattr(e, "link", ""))

            if not title or not link or not looks_like_single_funding(title):
                continue

            published_dt = None
            if hasattr(e, "published_parsed") and e.published_parsed:
                published_dt = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
            if published_dt and published_dt < cutoff:
                continue

            company = extract_company_from_title(title)
            if not company:
                continue
            key = company.lower()
            if key in seen:
                continue

            # fetch article page to extract more fields
            try:
                html = fetch(link)
            except Exception:
                html = ""

            investors = extract_investors_from_html(html) if html else ""
            round_ = guess_round_from_text(title + " " + investors + " " + (BeautifulSoup(html, "lxml").get_text(" ", strip=True)[:5000] if html else ""))
            hq = guess_hq_from_text(title + " " + (BeautifulSoup(html, "lxml").get_text(" ", strip=True)[:3000] if html else ""))

            item = {
                "name": company,
                "round": round_,
                "amount": parse_amount(title),
                "date": (published_dt.date().isoformat() if published_dt else datetime.now(timezone.utc).date().isoformat()),
                "hq": hq,
                "investors": investors,
                "source_url": link,
            }

            out.append(item)
            seen.add(key)
            if len(out) >= 25:
                break

    return out
