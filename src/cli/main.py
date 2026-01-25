import argparse
import json
import sys
from pathlib import Path

from src.core.orchestrator import run_turn
from src.db.state_store import StateStore
from src.eval.replay import format_replay_report, rerun_turns


def _load_json(value):
    if value is None:
        return None
    return json.loads(value)


def init_db(args):
    store = StateStore(args.db)
    store.ensure_schema()
    print(f"Initialized db at {args.db}")


def run_turn_cmd(args):
    store = StateStore(args.db)
    store.ensure_schema()
    prompt_versions = _load_json(args.prompt_versions)
    result = run_turn(store, args.campaign, args.input, prompt_versions)

    if args.json:
        print(json.dumps(result, ensure_ascii=True))
    else:
        print(result["final_text"])


def show_event_cmd(args):
    store = StateStore(args.db)
    event = store.get_event(args.campaign, args.turn)
    if not event:
        print("Event not found")
        return

    if args.field:
        if args.field not in event:
            print("Field not found")
            return
        print(event[args.field])
        return

    print(json.dumps(event, ensure_ascii=True))


def replay_cmd(args):
    store = StateStore(args.db)
    report = rerun_turns(
        store,
        args.campaign,
        args.start_turn,
        args.end_turn,
        _load_json(args.prompt_overrides),
    )
    print(format_replay_report(report))


def build_parser():
    parser = argparse.ArgumentParser(
        description="Freeform RPG Engine CLI (stub)."
    )
    parser.add_argument(
        "--db",
        default="game.db",
        help="SQLite db path (default: ./game.db)",
    )
    parser.add_argument(
        "--campaign",
        default="default",
        help="Campaign id (default: default)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    init_db_parser = sub.add_parser("init-db", help="Initialize the SQLite schema")
    init_db_parser.set_defaults(func=init_db)

    run_turn_parser = sub.add_parser("run-turn", help="Run a single turn (stub)")
    run_turn_parser.add_argument("--input", required=True, help="Player input text")
    run_turn_parser.add_argument(
        "--prompt-versions",
        help='JSON object, e.g. {"interpreter":"v1"}',
    )
    run_turn_parser.add_argument("--json", action="store_true", help="Print JSON output")
    run_turn_parser.set_defaults(func=run_turn_cmd)

    show_event_parser = sub.add_parser("show-event", help="Show a stored event")
    show_event_parser.add_argument("--turn", type=int, required=True, help="Turn number")
    show_event_parser.add_argument(
        "--field",
        help="Optional event field (context_packet_json, state_diff_json, etc)",
    )
    show_event_parser.set_defaults(func=show_event_cmd)

    replay_parser = sub.add_parser("replay", help="Replay turns (stub)")
    replay_parser.add_argument("--start-turn", type=int, required=True)
    replay_parser.add_argument("--end-turn", type=int, required=True)
    replay_parser.add_argument(
        "--prompt-overrides",
        help='JSON object, e.g. {"narrator":"v2"}',
    )
    replay_parser.set_defaults(func=replay_cmd)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
