from src.db.state_store import json_dumps


def rerun_turns(state_store, campaign_id, start_turn, end_turn, prompt_overrides=None):
    events = state_store.get_events_range(campaign_id, start_turn, end_turn)
    return {
        "status": "stub",
        "note": "Replay harness not implemented yet. Returning stored events only.",
        "prompt_overrides": prompt_overrides or {},
        "events": events,
    }


def format_replay_report(report):
    payload = {
        "status": report["status"],
        "note": report["note"],
        "event_count": len(report["events"]),
        "prompt_overrides": report["prompt_overrides"],
    }
    return json_dumps(payload)
