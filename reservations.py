import json
import re
from threading import Lock

_BOOKING_LOCK = Lock()
from datetime import datetime, timezone
from typing import Any, Dict, List

def load_reservations(path: str = "rezerwacje.json") -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        raise ValueError("Reservation file must contain a list")
    except FileNotFoundError:
        return []

def save_reservations(res_list: List[Dict[str, Any]], path: str = "rezerwacje.json") -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res_list, f, ensure_ascii=False, indent=2)

def _slot(option: Dict[str, Any]):
    object_id = option.get("object_id")
    date = option.get("date")
    time_range = option.get("time_range")
    if object_id is None or not isinstance(date, str):
        raise ValueError("Reservation requires an object ID and date")
    datetime.strptime(date, "%Y-%m-%d")
    if not isinstance(time_range, str) or not re.fullmatch(r"\d{2}:\d{2}-\d{2}:\d{2}", time_range):
        raise ValueError("Time range must use HH:MM-HH:MM")
    start, end = [datetime.strptime(t, "%H:%M").time() for t in time_range.split("-")]
    if start >= end:
        raise ValueError("Reservation end must be after start on the same day")
    return str(object_id), date, start, end


def has_conflict(option: Dict[str, Any], reservations: List[Dict[str, Any]]) -> bool:
    object_id, date, start, end = _slot(option)
    for existing in reservations:
        if not isinstance(existing, dict):
            raise ValueError("Invalid saved reservation")
        if str(existing.get("object_id")) == object_id and existing.get("date") == date:
            _, _, saved_start, saved_end = _slot(existing)
            if start < saved_end and saved_start < end:
                return True
    return False


def add_reservation(
    option: Dict[str, Any],
    customer_name: str,
    customer_email: str,
    original_query: str,
    path: str = "rezerwacje.json",
) -> Dict[str, Any]:
    # Streamlit sessions share a process. Keep check-and-save indivisible there.
    with _BOOKING_LOCK:
        return _add_reservation(option, customer_name, customer_email, original_query, path)


def _add_reservation(
    option: Dict[str, Any],
    customer_name: str,
    customer_email: str,
    original_query: str,
    path: str = "rezerwacje.json",
) -> Dict[str, Any]:
    reservations = load_reservations(path)
    if has_conflict(option, reservations):
        raise ValueError("Selected object already has a reservation during this time")
    ids = []
    for r in reservations:
        if isinstance(r, dict):
            rid = r.get("id")
            if isinstance(rid, int):
                ids.append(rid)
    new_id = (max(ids) if ids else 0) + 1
    activities = option.get("activities") or []
    if not isinstance(activities, list):
        activities = [activities]
    reservation = {
        "id": new_id,
        "object_id": option.get("object_id"),
        "object_name": option.get("object_name"),
        "object_type": option.get("object_type"),
        "activities": activities,
        "city": option.get("city"),
        "date": option.get("date"),
        "time_range": option.get("time_range"),
        "price_per_hour": option.get("price_per_hour"),
        "customer_name": customer_name,
        "customer_email": customer_email,
        "original_query": original_query,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    reservations.append(reservation)
    save_reservations(reservations, path)
    return reservation
