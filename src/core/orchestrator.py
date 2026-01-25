from src.context.builder import build_context
from src.db.state_store import json_dumps, new_event_id


DEFAULT_PROMPT_VERSIONS = {
    "interpreter": "v0",
    "planner": "v0",
    "narrator": "v0",
}


def run_turn(state_store, campaign_id, player_input, prompt_versions=None):
    context_packet = build_context()

    interpreter_output = {
        "intent": "unknown",
        "referenced_entities": [],
        "proposed_actions": [],
        "assumptions": [],
        "risk_flags": [],
    }

    validator_output = {
        "allowed_actions": [],
        "blocked_actions": [],
        "clarification_needed": False,
        "clarification_question": "",
        "costs": {"heat": 0, "time": 0, "cred": 0, "harm": 0, "rep": 0},
    }

    planner_output = {
        "beats": [],
        "tension_move": "",
        "clarification_question": "",
        "next_suggestions": [],
    }

    narrator_output = {
        "final_text": "Stub runner: pipeline not implemented yet. Your input is recorded. What do you do?",
        "next_prompt": "what_do_you_do",
        "suggested_actions": [],
    }

    engine_events = []
    state_diff = {
        "clocks": [],
        "facts_add": [],
        "facts_update": [],
        "inventory_changes": [],
        "scene_update": {"location_id": "", "present_entity_ids": []},
        "threads_update": [],
    }

    pass_outputs = {
        "interpreter": interpreter_output,
        "validator": validator_output,
        "planner": planner_output,
        "narrator": narrator_output,
    }

    versions = DEFAULT_PROMPT_VERSIONS.copy()
    if prompt_versions:
        versions.update(prompt_versions)

    turn_no = state_store.get_next_turn_no(campaign_id)
    event_record = {
        "id": new_event_id(),
        "campaign_id": campaign_id,
        "turn_no": turn_no,
        "player_input": player_input,
        "context_packet_json": json_dumps(context_packet),
        "pass_outputs_json": json_dumps(pass_outputs),
        "engine_events_json": json_dumps(engine_events),
        "state_diff_json": json_dumps(state_diff),
        "final_text": narrator_output["final_text"],
        "prompt_versions_json": json_dumps(versions),
    }

    state_store.append_event(event_record)

    return {
        "turn_no": turn_no,
        "final_text": narrator_output["final_text"],
        "event_id": event_record["id"],
    }
