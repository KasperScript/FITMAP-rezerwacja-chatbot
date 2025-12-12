import re
import json
from typing import Any, Dict, Optional

def extract_json_candidate(text: Optional[str]) -> Optional[str]:
    
    if not text:
        return None
    match = re.search(r"```json(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1].strip()

def extract_json_block(text: Optional[str]) -> Optional[Dict[str, Any]]:
    
    candidate = extract_json_candidate(text)
    if not candidate:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None
