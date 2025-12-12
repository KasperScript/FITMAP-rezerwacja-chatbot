import json
from datetime import datetime, timezone
from typing import Any, Dict, List

def load_reservations(path: str = "rezerwacje.json") -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []

def save_reservations(res_list: List[Dict[str, Any]], path: str = "rezerwacje.json") -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res_list, f, ensure_ascii=False, indent=2)

def add_reservation(
    option: Dict[str, Any],
    customer_name: str,
    customer_email: str,
    original_query: str,
    path: str = "rezerwacje.json",
) -> Dict[str, Any]:
    reservations = load_reservations(path)
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
