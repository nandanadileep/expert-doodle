import os
from datetime import date
from typing import Any, Dict, Optional, Set

import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DB_ID = os.environ["NOTION_DATABASE_ID"]

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

_DB_PROPS_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def _normalize(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _clip_text(value: str, max_chars: int = 1900) -> str:
    # Keep text below Notion's 2000-char rich_text limit.
    return (value or "").strip()[:max_chars]


def _response_debug(resp: requests.Response) -> str:
    try:
        return str(resp.json())
    except Exception:
        return resp.text[:1000]


def _pick_option_name(prop_def: Dict[str, Any], preferred: list[str]) -> Optional[str]:
    ptype = prop_def.get("type")
    type_block = prop_def.get(ptype, {}) if isinstance(prop_def.get(ptype), dict) else {}
    options = type_block.get("options", []) if isinstance(type_block, dict) else []
    option_names = {opt.get("name", "") for opt in options if isinstance(opt, dict)}

    if not option_names:
        return preferred[0] if preferred else None

    normalized = {_normalize(name): name for name in option_names}
    for candidate in preferred:
        picked = normalized.get(_normalize(candidate))
        if picked:
            return picked
    return next(iter(option_names), None)


def _fetch_database_properties() -> Dict[str, Dict[str, Any]]:
    global _DB_PROPS_CACHE
    if _DB_PROPS_CACHE is not None:
        return _DB_PROPS_CACHE

    resp = requests.get(
        f"https://api.notion.com/v1/databases/{DB_ID}",
        headers=HEADERS,
        timeout=20,
    )
    if not resp.ok:
        raise RuntimeError(f"Notion database read failed ({resp.status_code}): {_response_debug(resp)}")

    payload = resp.json()
    props = payload.get("properties")
    if not isinstance(props, dict):
        raise RuntimeError("Notion database response did not include a 'properties' object.")

    _DB_PROPS_CACHE = props
    return props


def _find_property(
    db_props: Dict[str, Dict[str, Any]],
    aliases: list[str],
    allowed_types: Set[str],
) -> Optional[str]:
    exact_index = {}
    for prop_name, prop_def in db_props.items():
        if prop_def.get("type") in allowed_types:
            exact_index[_normalize(prop_name)] = prop_name

    for alias in aliases:
        hit = exact_index.get(_normalize(alias))
        if hit:
            return hit

    alias_norms = [_normalize(alias) for alias in aliases]
    for prop_name, prop_def in db_props.items():
        if prop_def.get("type") not in allowed_types:
            continue
        prop_norm = _normalize(prop_name)
        if any(a and (a in prop_norm or prop_norm in a) for a in alias_norms):
            return prop_name
    return None


def _as_rich_text(value: str) -> Dict[str, Any]:
    text = _clip_text(value)
    if not text:
        return {"rich_text": []}
    return {"rich_text": [{"text": {"content": text}}]}


def _build_properties(item: Dict[str, Any], run_date: str) -> Dict[str, Any]:
    db_props = _fetch_database_properties()
    props: Dict[str, Any] = {}

    title_prop = _find_property(db_props, ["Name", "Company", "Startup", "Title"], {"title"})
    if not title_prop:
        raise RuntimeError("No title property found in the Notion database.")
    props[title_prop] = {"title": [{"text": {"content": _clip_text(item.get("name", ""), max_chars=200)}}]}

    mapping = [
        ("round", ["Round", "Funding Round"], {"rich_text", "select", "multi_select"}),
        ("amount", ["Amount", "Funding Amount"], {"rich_text", "select", "multi_select"}),
        ("date", ["Funding Date", "Date"], {"date"}),
        ("hq", ["HQ", "Location", "City", "Headquarters"], {"rich_text", "select", "multi_select"}),
        ("investors", ["Investors", "Investor", "Backers"], {"rich_text"}),
        ("source_url", ["Source URL", "Source", "URL", "Link"], {"url"}),
    ]

    for item_key, aliases, allowed_types in mapping:
        value = item.get(item_key)
        if value in (None, ""):
            continue
        prop_name = _find_property(db_props, aliases, allowed_types)
        if not prop_name:
            continue
        prop_def = db_props[prop_name]
        ptype = prop_def.get("type")

        if ptype == "date":
            props[prop_name] = {"date": {"start": str(value)}}
        elif ptype == "url":
            props[prop_name] = {"url": _clip_text(str(value), max_chars=2000)}
        elif ptype == "rich_text":
            props[prop_name] = _as_rich_text(str(value))
        elif ptype in {"select", "multi_select"}:
            picked = _pick_option_name(prop_def, [str(value)])
            if not picked:
                continue
            if ptype == "select":
                props[prop_name] = {"select": {"name": picked}}
            else:
                props[prop_name] = {"multi_select": [{"name": picked}]}

    run_date_prop = _find_property(db_props, ["Run date", "Run Date", "Ingested At"], {"date"})
    if run_date_prop:
        props[run_date_prop] = {"date": {"start": run_date}}

    status_prop = _find_property(db_props, ["Status"], {"status", "select"})
    if status_prop:
        status_def = db_props[status_prop]
        status_type = status_def.get("type")
        picked_status = _pick_option_name(status_def, ["New", "Not started", "Todo", "To do", "Backlog"])
        if picked_status:
            if status_type == "status":
                props[status_prop] = {"status": {"name": picked_status}}
            elif status_type == "select":
                props[status_prop] = {"select": {"name": picked_status}}

    return props


def notion_create_row(item: dict, run_date: str):
    payload = {
        "parent": {"database_id": DB_ID},
        "properties": _build_properties(item, run_date),
    }
    resp = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=payload, timeout=20)
    if not resp.ok:
        raise RuntimeError(f"Notion page create failed ({resp.status_code}): {_response_debug(resp)}")
    return resp.json()

def write_all(items: list[dict]):
    run_date = date.today().isoformat()
    created, failed, skipped = 0, 0, 0
    for it in items:
        # skip garbage
        if not it.get("name") or not it.get("source_url"):
            skipped += 1
            continue
        try:
            notion_create_row(it, run_date)
            created += 1
        except Exception as exc:
            failed += 1
            print(f"[notion] failed for '{it.get('name', 'unknown')}': {exc}")
    print(f"[notion] complete: created={created}, failed={failed}, skipped={skipped}")
