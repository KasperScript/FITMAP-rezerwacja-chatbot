import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

def normalize_activities(obj: Dict[str, Any]) -> List[str]:
    activities = obj.get("activities")
    if not activities:
        activity = obj.get("activity")
        if isinstance(activity, str):
            activities = [item.strip() for item in activity.split(",") if item.strip()]
    if activities is None:
        activities = []
    if not isinstance(activities, list):
        activities = [activities] if activities else []
    activities = [str(a).strip() for a in activities if str(a).strip()]
    return activities

def split_schedule(entry: Any) -> Optional[Dict[str, Optional[str]]]:
    if not isinstance(entry, str):
        return None
    m = re.match(r"^(?:(\d{4}-\d{2}-\d{2})\s+)?(\d{1,2}:\d{2}-\d{1,2}:\d{2})$", entry.strip())
    if not m:
        return None
    return {"date": m.group(1), "time_range": m.group(2)}

def normalize_schedule(obj: Dict[str, Any]) -> List[Dict[str, Optional[str]]]:
    schedule = obj.get("schedule") or []
    normalized = []
    for entry in schedule:
        parsed = split_schedule(entry)
        if parsed:
            normalized.append(parsed)
    return normalized

def load_availability(path: str = "dostepnosc.json") -> Dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    data = json.loads(text)

    if "objects" not in data or not isinstance(data["objects"], list):
        raise ValueError('Plik dostepnosc.json musi mieć strukturę {"objects": [...]}')

    normalized_objects = []
    for obj in data["objects"]:
        activities = normalize_activities(obj)
        schedule = normalize_schedule(obj)
        normalized_objects.append(
            {
                "id": obj.get("id"),
                "type": obj.get("type"),
                "name": obj.get("name"),
                "city": obj.get("city"),
                "activities": activities,
                "price_per_hour": obj.get("price_per_hour"),
                "schedule": schedule,
            }
        )

    return {"objects": normalized_objects}
