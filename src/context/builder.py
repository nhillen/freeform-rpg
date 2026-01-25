from datetime import datetime


def build_context():
    return {
        "scene": {"location_id": "", "time": {"utc": datetime.utcnow().isoformat()}, "constraints": {}},
        "present_entities": [],
        "entities": [],
        "facts": [],
        "threads": [],
        "clocks": [],
        "inventory": [],
        "summary": {"scene": "", "threads": ""},
        "recent_events": [],
    }
