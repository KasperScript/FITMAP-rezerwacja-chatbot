import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from prompts import FILTER_PROMPT, ANSWER_PROMPT
from llm_client import call_gemini
from parsing import extract_json_block

DEFAULT_FILTERS = {
    "activities": [],
    "city": None,
    "date": None,
    "day_of_week": None,
    "earliest_time": None,
    "latest_time": None,
    "max_price_per_hour": None,
}

def parse_time_to_minutes(value: Optional[str]) -> Optional[int]:
    if not value or not isinstance(value, str):
        return None
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", value)
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))

def match_time_window(time_range: str, earliest: Optional[int], latest: Optional[int]) -> bool:
    parts = time_range.split("-")
    if len(parts) != 2:
        return False
    start = parse_time_to_minutes(parts[0])
    end = parse_time_to_minutes(parts[1])
    if start is None or end is None:
        return False
    if earliest is not None and start < earliest:
        return False
    if latest is not None and end > latest:
        return False
    return True

def day_name(date_str: str) -> Optional[str]:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        names = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
        return names[dt.weekday()]
    except Exception:
        return None

def format_date(year: int, month: int, day: int) -> Optional[str]:
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except Exception:
        return None

def find_date_in_db(day: int, month: int, db_json: Dict[str, Any]) -> Optional[str]:
    candidates = []
    for obj in db_json.get("objects") or []:
        for date_val, _ in schedule_entries(obj):
            if not date_val:
                continue
            try:
                dt = datetime.strptime(date_val, "%Y-%m-%d")
            except Exception:
                continue
            if dt.day == day and dt.month == month:
                candidates.append(date_val)
    if candidates:
        return sorted(set(candidates))[0]
    return None

def infer_date_from_query(user_query: str, db_json: Dict[str, Any]) -> Optional[str]:
    q = user_query.strip().lower()
    m_iso = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", q)
    if m_iso:
        return format_date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
    m_dmy = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b", q)
    if m_dmy:
        day = int(m_dmy.group(1))
        month = int(m_dmy.group(2))
        year = int(m_dmy.group(3))
        if year < 100:
            year += 2000
        return format_date(year, month, day)
    m_dm = re.search(r"\b(\d{1,2})[./](\d{1,2})\b", q)
    if m_dm:
        day = int(m_dm.group(1))
        month = int(m_dm.group(2))
        date_val = find_date_in_db(day, month, db_json)
        if date_val:
            return date_val
        return format_date(datetime.now().year, month, day)
    return None

def time_explicit_in_query(user_query: str) -> bool:
    q = user_query.lower()
    if re.search(r"\b(po|od|mi[eę]dzy|do)\s*\d{1,2}(?::\d{2})?\b", q):
        return True
    if re.search(r"\b\d{1,2}:\d{2}\b", q):
        return True
    return False

def merge_filters(current: Dict[str, Any], previous: Optional[Dict[str, Any]], user_query: str) -> Dict[str, Any]:
    if not previous:
        return current
    merged = current.copy()
    if not merged.get("activities"):
        merged["activities"] = previous.get("activities")
    if not merged.get("city"):
        merged["city"] = previous.get("city")
    if not merged.get("date"):
        merged["date"] = previous.get("date")
    if not merged.get("day_of_week"):
        merged["day_of_week"] = previous.get("day_of_week")
    if merged.get("max_price_per_hour") in [None, ""]:
        merged["max_price_per_hour"] = previous.get("max_price_per_hour")
    if not time_explicit_in_query(user_query):
        if not merged.get("earliest_time"):
            merged["earliest_time"] = previous.get("earliest_time")
        if not merged.get("latest_time"):
            merged["latest_time"] = previous.get("latest_time")
    return merged

def format_price(value: Any) -> Optional[str]:
    try:
        val = float(value)
    except Exception:
        return None
    if val.is_integer():
        return str(int(val))
    return str(val)

def describe_time_window(earliest: Optional[str], latest: Optional[str]) -> Optional[str]:
    if earliest and latest:
        return f"między {earliest} a {latest}"
    if earliest:
        return f"po {earliest}"
    if latest:
        return f"do {latest}"
    return None

def no_match_message(filters: Dict[str, Any]) -> str:
    parts = []
    date_val = filters.get("date")
    if date_val:
        parts.append(f"dzień {date_val}")
    time_desc = describe_time_window(filters.get("earliest_time"), filters.get("latest_time"))
    if time_desc:
        parts.append(f"godzina {time_desc}")
    price_val = format_price(filters.get("max_price_per_hour"))
    if price_val:
        parts.append(f"cena do {price_val} zł/h")
    if parts:
        return "Nie ma dopasowań dla tej kombinacji: " + ", ".join(parts) + "."
    return "Nie znalazłem pasujących opcji dla podanego zapytania."

def normalize_filters(filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out = DEFAULT_FILTERS.copy()
    if not filters:
        return out
    for key in out.keys():
        if key in filters:
            out[key] = filters[key]
    if out["activities"] is None:
        out["activities"] = []
    if not isinstance(out["activities"], list):
        out["activities"] = [out["activities"]] if out["activities"] else []
    out["activities"] = [str(a).strip() for a in out["activities"] if str(a).strip()]
    if out["city"]:
        out["city"] = str(out["city"]).strip()
    if out["earliest_time"]:
        m = parse_time_to_minutes(out["earliest_time"])
        out["earliest_time"] = out["earliest_time"] if m is not None else None
    if out["latest_time"]:
        m = parse_time_to_minutes(out["latest_time"])
        out["latest_time"] = out["latest_time"] if m is not None else None
    if out["max_price_per_hour"] is not None:
        try:
            out["max_price_per_hour"] = float(out["max_price_per_hour"])
        except Exception:
            out["max_price_per_hour"] = None
    return out

def heuristic_filters(user_query: str) -> Dict[str, Any]:
    filters = DEFAULT_FILTERS.copy()
    q = user_query.lower()
    activity_keywords = ["joga", "pilates", "crossfit", "zumba", "mma", "cardio", "stretching", "medytacja", "koszykówka", "piłka nożna"]
    activities = [a.title() for a in activity_keywords if a in q]
    filters["activities"] = activities
    m_between = re.search(r"(?:mi[eę]dzy|od)\s*(\d{1,2})(?::(\d{2}))?\s*(?:-|do|a)\s*(\d{1,2})(?::(\d{2}))?", q)
    if m_between:
        h1 = int(m_between.group(1))
        m1 = int(m_between.group(2) or 0)
        h2 = int(m_between.group(3))
        m2 = int(m_between.group(4) or 0)
        filters["earliest_time"] = f"{h1:02d}:{m1:02d}"
        filters["latest_time"] = f"{h2:02d}:{m2:02d}"
    m_time = re.search(r"po\s*(\d{1,2})(?::(\d{2}))?", q)
    if m_time:
        h = int(m_time.group(1))
        mi = int(m_time.group(2) or 0)
        filters["earliest_time"] = f"{h:02d}:{mi:02d}"
    m_price = re.search(r"(?:do|poniżej)\s*(\d+)", q)
    if m_price:
        filters["max_price_per_hour"] = float(m_price.group(1))
    return normalize_filters(filters)

def build_filters_with_llm(user_query: str) -> Dict[str, Any]:
    heuristic = heuristic_filters(user_query)
    try:
        raw = call_gemini(FILTER_PROMPT, user_query)
        parsed = extract_json_block(raw)
        filters = normalize_filters(parsed)
        merged = heuristic.copy()
        trusted_keys = ["activities", "city", "earliest_time", "latest_time", "max_price_per_hour"]
        for k in trusted_keys:
            v = filters.get(k)
            if v not in [None, [], ""]:
                merged[k] = v
        return merged
    except Exception:
        return heuristic

def schedule_entries(obj: Dict[str, Any]) -> List[Tuple[Optional[str], str]]:
    entries = []
    for slot in obj.get("schedule") or []:
        if isinstance(slot, dict):
            date_val = slot.get("date")
            tr = slot.get("time_range")
        else:
            date_val, tr = None, slot
        if not tr:
            continue
        if " " in tr and date_val is None:
            parts = tr.split(" ", 1)
            date_val, tr = parts[0], parts[1] if len(parts) > 1 else None
        entries.append((date_val, tr))
    return entries

def matches_filters(obj: Dict[str, Any], slot: Tuple[Optional[str], str], filters: Dict[str, Any]) -> bool:
    date_val, time_range = slot
    if filters["activities"]:
        obj_acts = [a.lower() for a in obj.get("activities") or [] if isinstance(a, str)]
        if not any(a.lower() == act.lower() or act.lower() in a.lower() for act in filters["activities"] for a in obj_acts):
            return False
    if filters["city"]:
        if not obj.get("city") or filters["city"].lower() not in obj.get("city").lower():
            return False
    earliest = parse_time_to_minutes(filters["earliest_time"])
    latest = parse_time_to_minutes(filters["latest_time"])
    if not match_time_window(time_range, earliest, latest):
        return False
    if filters["max_price_per_hour"] is not None:
        price = obj.get("price_per_hour")
        try:
            if price is not None and float(price) > filters["max_price_per_hour"]:
                return False
        except Exception:
            pass
    if filters["date"]:
        if date_val != filters["date"]:
            return False
    if filters["day_of_week"]:
        if date_val:
            dn = day_name(date_val)
            if not dn or dn.lower() != str(filters["day_of_week"]).lower():
                return False
    return True

def search_database(filters: Dict[str, Any], db_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = []
    for obj in db_json.get("objects") or []:
        for date_val, time_range in schedule_entries(obj):
            if matches_filters(obj, (date_val, time_range), filters):
                results.append(
                    {
                        "object_id": obj.get("id"),
                        "object_name": obj.get("name"),
                        "object_type": obj.get("type"),
                        "city": obj.get("city"),
                        "activities": obj.get("activities") or [],
                        "date": date_val,
                        "time_range": time_range,
                        "price_per_hour": obj.get("price_per_hour"),
                    }
                )
    return results

def build_answer_with_llm(user_query: str, filters: Dict[str, Any], options: List[Dict[str, Any]]) -> Tuple[str, Optional[Dict[str, Any]]]:
    contents = (
        "USER_QUERY:\n"
        + user_query
        + "\n\nFILTERS_JSON:\n"
        + json.dumps(filters, ensure_ascii=False, indent=2)
        + "\n\nMATCHED_OPTIONS_JSON:\n"
        + json.dumps(options[:20], ensure_ascii=False, indent=2)
    )
    try:
        raw = call_gemini(ANSWER_PROMPT, contents)
    except Exception:
        raw = None
    parsed = extract_json_block(raw) if raw else None
    if not raw:
        if options:
            preview = options[:3]
            parts = []
            for opt in preview:
                acts = ", ".join(opt.get("activities") or [])
                city = f", {opt['city']}" if opt.get("city") else ""
                parts.append(f"{opt.get('object_name')} ({opt.get('object_type')}{city}) {opt.get('time_range')} – {acts}")
            raw = "Znalazłem pasujące opcje: " + "; ".join(parts)
        else:
            raw = "Nie znalazłem pasujących opcji dla podanego zapytania."
    return raw, parsed

def handle_user_query(user_query: str, db_json: Dict[str, Any], previous_filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    filters = build_filters_with_llm(user_query)
    inferred_date = infer_date_from_query(user_query, db_json)
    if inferred_date:
        filters["date"] = inferred_date
    filters = merge_filters(filters, previous_filters, user_query)
    options = search_database(filters, db_json)
    payload = {
        "action": "LIST_OPTIONS",
        "query_understanding": user_query,
        "options": options,
        "chosen_option_id": options[0]["object_id"] if options else None,
    }
    raw_answer, llm_payload = build_answer_with_llm(user_query, filters, options)
    if not options:
        raw_answer = no_match_message(filters)
    if llm_payload:
        payload["query_understanding"] = llm_payload.get("query_understanding", payload["query_understanding"])
    return {
        "raw_answer": raw_answer,
        "parsed_payload": payload,
        "filters": filters,
    }
