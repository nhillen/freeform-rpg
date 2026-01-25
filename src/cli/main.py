"""
Freeform RPG Engine CLI.

Commands:
  init-db     Initialize the SQLite schema
  new-game    Start a new game with Session Zero setup
  run-turn    Execute a single turn
  play        Interactive play mode (REPL)
  show-event  Show a stored event
  replay      Replay turns for A/B testing
"""

import argparse
import json
import sys
from pathlib import Path

from src.core.orchestrator import Orchestrator, run_turn
from src.db.state_store import StateStore
from src.llm.gateway import MockGateway
from src.llm.prompt_registry import PromptRegistry
from src.setup import SetupPipeline, ScenarioLoader, load_template, list_templates
from src.eval.replay import format_replay_report, rerun_turns


def _load_json(value):
    if value is None:
        return None
    return json.loads(value)


def init_db(args):
    """Initialize the database schema."""
    store = StateStore(args.db)
    store.ensure_schema()
    print(f"Initialized database at {args.db}")


def new_game(args):
    """Start a new game with Session Zero setup."""
    store = StateStore(args.db)
    store.ensure_schema()

    # Try setup pipeline first (for templates), fall back to scenario loader
    if args.scenario:
        # Use scenario loader for full YAML scenarios
        loader = ScenarioLoader(store)
        result = loader.load_scenario(
            args.scenario,
            campaign_id=args.campaign
        )
        print(f"\n{'='*60}")
        print(f"Campaign: {result['campaign_name']}")
        print(f"Campaign ID: {result['campaign_id']}")
        print(f"Entities loaded: {result['entities_loaded']}")
        print(f"Clocks loaded: {result['clocks_loaded']}")
        print(f"{'='*60}")
        if result.get('opening_text'):
            print(f"\n{result['opening_text']}")
    else:
        # Use setup pipeline for template-based setup
        pipeline = SetupPipeline(store)

        # Collect character info if interactive
        char_responses = {}
        if args.interactive:
            print("\n=== Session Zero: Character Creation ===\n")
            char_responses["name"] = input("What is your character's name? ").strip() or "Anonymous"
            char_responses["background"] = input("Brief background (1-2 sentences): ").strip() or "A survivor"
            char_responses["skills"] = input("What are you good at? (comma-separated): ").strip() or "survival"
            char_responses["weakness"] = input("What's your weakness? ").strip() or "Trust issues"
            char_responses["motivation"] = input("What drives you? ").strip() or "Find the truth"

        result = pipeline.run_setup(
            template_id=args.template or "default",
            calibration_preset=args.preset or "noir_standard",
            character_responses=char_responses,
            campaign_id=args.campaign
        )

        print(f"\n{'='*60}")
        print(f"Campaign initialized!")
        print(f"Campaign ID: {result.campaign_id}")
        print(f"Character: {result.character.name}")
        print(f"Calibration: {args.preset or 'noir_standard'}")
        print(f"{'='*60}")
        print(f"\n{result.opening_text}")

    print(f"\nTo continue, run:")
    print(f"  python -m src.cli.main --db {args.db} --campaign {args.campaign} play")


def run_turn_cmd(args):
    """Execute a single turn."""
    store = StateStore(args.db)
    store.ensure_schema()

    # Check campaign exists
    campaign = store.get_campaign(args.campaign)
    if not campaign:
        print(f"Error: Campaign '{args.campaign}' not found.")
        print("Run 'new-game' first to create a campaign.")
        sys.exit(1)

    prompt_versions = _load_json(args.prompt_versions)
    result = run_turn(store, args.campaign, args.input, prompt_versions)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\n{result['final_text']}\n")
        if result.get('clarification_needed'):
            print(f"[Clarification needed: {result.get('clarification_question', '')}]")


def play_cmd(args):
    """Interactive play mode (REPL)."""
    store = StateStore(args.db)
    store.ensure_schema()

    # Check campaign exists
    campaign = store.get_campaign(args.campaign)
    if not campaign:
        print(f"Error: Campaign '{args.campaign}' not found.")
        print("Run 'new-game' first to create a campaign.")
        sys.exit(1)

    # Setup orchestrator
    prompts_dir = Path(__file__).parent.parent / "prompts"
    prompt_registry = PromptRegistry(prompts_dir)
    gateway = MockGateway()  # Use mock for now

    orchestrator = Orchestrator(
        state_store=store,
        llm_gateway=gateway,
        prompt_registry=prompt_registry
    )

    print(f"\n{'='*60}")
    print(f"Freeform RPG - Interactive Mode")
    print(f"Campaign: {campaign.get('name', args.campaign)}")
    print(f"{'='*60}")
    print("Type your actions, or 'quit' to exit.")
    print("Commands: /status, /clocks, /scene, /help\n")

    # Show any opening text from last event
    events = store.get_events_range(args.campaign, 0, 1)
    if not events:
        # First time - show scene
        scene = store.get_scene()
        if scene:
            location = store.get_entity(scene.get("location_id"))
            if location:
                print(f"[Location: {location.get('name', 'Unknown')}]")
                if location.get("attrs", {}).get("description"):
                    print(f"{location['attrs']['description']}\n")
    else:
        # Show last event text
        last = events[-1]
        print(f"{last.get('final_text', '')}\n")

    # REPL loop
    turn_count = len(events)
    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break

        # Handle commands
        if user_input.startswith('/'):
            _handle_command(user_input, store, args.campaign)
            continue

        # Run turn
        try:
            result = orchestrator.run_turn(args.campaign, user_input)
            turn_count += 1
            print(f"\n{result.final_text}\n")

            if result.clarification_needed:
                print(f"[{result.clarification_question}]")

        except Exception as e:
            print(f"Error: {e}")


def _handle_command(cmd, store, campaign_id):
    """Handle REPL commands."""
    cmd = cmd.lower()

    if cmd == '/help':
        print("""
Commands:
  /status  - Show character status (harm, cred)
  /clocks  - Show all clocks
  /scene   - Show current scene
  /threads - Show active threads
  /quit    - Exit the game
""")
    elif cmd == '/status' or cmd == '/clocks':
        clocks = store.get_all_clocks()
        print("\n=== Clocks ===")
        for c in clocks:
            bar = _progress_bar(c['value'], c['max'])
            print(f"  {c['name']}: {bar} {c['value']}/{c['max']}")
        print()

    elif cmd == '/scene':
        scene = store.get_scene()
        if scene:
            loc = store.get_entity(scene.get('location_id'))
            print(f"\n=== Scene ===")
            print(f"Location: {loc.get('name') if loc else 'Unknown'}")
            print(f"Time: {scene.get('time', {})}")
            print(f"Present: {', '.join(scene.get('present_entity_ids', []))}")
            print()
        else:
            print("No scene set.")

    elif cmd == '/threads':
        threads = store.get_active_threads()
        print("\n=== Active Threads ===")
        for t in threads:
            print(f"  - {t['title']}")
            stakes = t.get('stakes', {})
            if stakes.get('success'):
                print(f"    Success: {stakes['success']}")
            if stakes.get('failure'):
                print(f"    Failure: {stakes['failure']}")
        print()

    else:
        print(f"Unknown command: {cmd}")
        print("Type /help for available commands.")


def _progress_bar(value, max_val, width=20):
    """Create a simple progress bar."""
    if max_val <= 0:
        return "[" + "?" * width + "]"
    filled = int((value / max_val) * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def show_event_cmd(args):
    """Show a stored event."""
    store = StateStore(args.db)
    event = store.get_event(args.campaign, args.turn)
    if not event:
        print("Event not found")
        return

    if args.field:
        if args.field not in event:
            print("Field not found")
            return
        value = event[args.field]
        if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
            try:
                value = json.loads(value)
                print(json.dumps(value, indent=2, ensure_ascii=False))
                return
            except:
                pass
        print(value)
        return

    print(json.dumps(event, indent=2, ensure_ascii=False))


def replay_cmd(args):
    """Replay turns for A/B testing."""
    store = StateStore(args.db)
    report = rerun_turns(
        store,
        args.campaign,
        args.start_turn,
        args.end_turn,
        _load_json(args.prompt_overrides),
    )
    print(format_replay_report(report))


def list_scenarios_cmd(args):
    """List available scenarios."""
    store = StateStore(args.db)
    loader = ScenarioLoader(store)
    scenarios = loader.list_scenarios()

    if not scenarios:
        print("No scenarios found in scenarios/ directory")
        return

    print("\nAvailable Scenarios:")
    print("-" * 40)
    for s in scenarios:
        print(f"  {s['id']}: {s['name']}")
        if s.get('description'):
            print(f"      {s['description'][:60]}...")
    print()


def build_parser():
    parser = argparse.ArgumentParser(
        description="Freeform RPG Engine CLI - AI-driven narrative RPG"
    )
    parser.add_argument(
        "--db",
        default="game.db",
        help="SQLite database path (default: game.db)",
    )
    parser.add_argument(
        "--campaign",
        default="default",
        help="Campaign ID (default: default)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # init-db
    init_db_parser = sub.add_parser("init-db", help="Initialize the SQLite schema")
    init_db_parser.set_defaults(func=init_db)

    # new-game
    new_game_parser = sub.add_parser("new-game", help="Start a new game")
    new_game_parser.add_argument(
        "--scenario",
        help="Scenario file to load (e.g., dead_drop)"
    )
    new_game_parser.add_argument(
        "--template",
        help="Template to use if no scenario specified"
    )
    new_game_parser.add_argument(
        "--preset",
        default="noir_standard",
        help="Calibration preset (noir_standard, pulp_adventure, hard_boiled)"
    )
    new_game_parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Interactive character creation"
    )
    new_game_parser.set_defaults(func=new_game)

    # list-scenarios
    list_parser = sub.add_parser("list-scenarios", help="List available scenarios")
    list_parser.set_defaults(func=list_scenarios_cmd)

    # run-turn
    run_turn_parser = sub.add_parser("run-turn", help="Execute a single turn")
    run_turn_parser.add_argument("--input", "-i", required=True, help="Player input text")
    run_turn_parser.add_argument(
        "--prompt-versions",
        help='JSON object, e.g. {"interpreter":"v1"}',
    )
    run_turn_parser.add_argument("--json", action="store_true", help="Output JSON")
    run_turn_parser.set_defaults(func=run_turn_cmd)

    # play (interactive mode)
    play_parser = sub.add_parser("play", help="Interactive play mode")
    play_parser.set_defaults(func=play_cmd)

    # show-event
    show_event_parser = sub.add_parser("show-event", help="Show a stored event")
    show_event_parser.add_argument("--turn", type=int, required=True, help="Turn number")
    show_event_parser.add_argument(
        "--field",
        help="Specific field to show (final_text, context_packet_json, etc.)"
    )
    show_event_parser.set_defaults(func=show_event_cmd)

    # replay
    replay_parser = sub.add_parser("replay", help="Replay turns for A/B testing")
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
