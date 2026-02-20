"""
Persistent global API request counter to prevent demo exhaustion.
Stores count in a local JSON file (api_usage.json).
"""

import json
from pathlib import Path

USAGE_FILE = Path("api_usage.json")
MAX_GLOBAL_REQUESTS = 50


def get_global_api_count() -> int:
    """Read the global API request count from api_usage.json. Returns 0 if file is missing or invalid."""
    if not USAGE_FILE.exists():
        return 0
    try:
        data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
        return int(data.get("count", 0))
    except (json.JSONDecodeError, OSError, ValueError):
        return 0


def increment_global_api_count() -> None:
    """Increment the global API request count by 1 and save to api_usage.json."""
    count = get_global_api_count()
    count += 1
    USAGE_FILE.write_text(json.dumps({"count": count}, indent=2), encoding="utf-8")
