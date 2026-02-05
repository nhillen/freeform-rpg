"""
Freeform RPG Engine CLI.

Commands:
  init-db     Initialize the SQLite schema
  new-game    Start a new game with Session Zero setup
  run-turn    Execute a single turn
  play        Interactive play mode (REPL)
  show-event  Show a stored event
  replay      Replay turns for A/B testing

Content Pack Commands:
  pack-test         Test a content pack (analyze, probe, report)

Ingest Commands:
  pack-ingest       Full PDF-to-content-pack pipeline
  ingest-extract    Stage 1: PDF text extraction
  ingest-structure  Stage 2: Document structure detection
  ingest-segment    Stage 3: Content segmentation
  ingest-classify   Stage 4: Content classification
  ingest-enrich     Stage 5: Lore enrichment
  ingest-assemble   Stage 6: Content pack assembly
  ingest-validate   Stage 7: Pack validation
  ingest-systems-extract   Stage S1: Systems extraction
  ingest-systems-assemble  Stage S2: Systems assembly
  ingest-systems-validate  Stage S3: Systems validation
"""

import argparse
import json
import sys
from pathlib import Path

from src.config import (
    get_api_key, interactive_login, check_auth_or_prompt,
    clear_api_key, get_config_path
)
from src.core.orchestrator import Orchestrator, run_turn
from src.db.state_store import StateStore
from src.llm.gateway import MockGateway, ClaudeGateway
from src.llm.prompt_registry import PromptRegistry
from src.setup import SetupPipeline, ScenarioLoader, load_template, list_templates
from src.eval.replay import format_replay_report, rerun_turns
from src.content.pack_loader import PackLoader
from src.content.chunker import Chunker
from src.content.indexer import LoreIndexer
from src.content.retriever import LoreRetriever
from src.content.scene_cache import SceneLoreCacheManager
from src.content.session_manager import SessionManager
from src.content.vector_store import create_vector_store
from src.cli.vibe_check import vibe_check_cmd


def _load_json(value):
    if value is None:
        return None
    return json.loads(value)


def init_db(args):
    """Initialize the database schema."""
    store = StateStore(args.db)
    store.ensure_schema()
    print(f"Initialized database at {args.db}")


def login_cmd(args):
    """Interactive login to set up API key."""
    success = interactive_login()
    sys.exit(0 if success else 1)


def logout_cmd(args):
    """Remove stored API key."""
    clear_api_key()
    print(f"Logged out. API key removed from {get_config_path()}")


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
    print(f"  freeform-rpg --db {args.db} --campaign {args.campaign} play")


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

    # Check for API key
    api_key = check_auth_or_prompt()
    if not api_key:
        print("\n  Cannot run turn without an API key.")
        print("  Run 'login' to set one up, or set ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)

    # Setup LLM gateway
    prompts_dir = Path(__file__).parent.parent / "prompts"
    prompt_registry = PromptRegistry(prompts_dir)
    gateway = ClaudeGateway(api_key=api_key)

    prompt_versions = _load_json(args.prompt_versions)
    result = run_turn(
        store, args.campaign, args.input, prompt_versions,
        llm_gateway=gateway, prompt_registry=prompt_registry
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\n{result['final_text']}\n")
        if result.get('clarification_needed'):
            print(f"[Clarification needed: {result.get('clarification_question', '')}]")


def _format_clock_deltas(clock_deltas: list) -> str:
    """Format clock deltas as an inline display line.

    Only shows consequence-driven changes (roll results, complications,
    tension moves), not routine action costs.
    """
    if not clock_deltas:
        return ""
    consequence_deltas = [d for d in clock_deltas if d.get("consequence", False)]
    if not consequence_deltas:
        return ""
    parts = []
    for delta in consequence_deltas:
        name = delta.get("name", delta.get("id", "?"))
        old = delta["old"]
        new = delta["new"]
        parts.append(f"[{name}: {old} \u2192 {new}]")
    return "  ".join(parts)


def _format_rolls(debug_info: dict) -> str:
    """Format dice rolls as a brief inline display."""
    if not debug_info:
        return ""
    resolver = debug_info.get("resolver", {})
    rolls = resolver.get("rolls", [])
    if not rolls:
        return ""

    parts = []
    for roll in rolls:
        dice = roll.get("dice", "2d6")
        total = roll.get("total", "?")
        outcome = roll.get("outcome", "?")
        action = roll.get("action", "")
        label = {"success": "Success", "critical": "Critical!", "mixed": "Mixed", "failure": "Failure"}.get(outcome, outcome)
        prefix = f"{action.capitalize()} " if action else ""
        parts.append(f"[{prefix}{dice}: {total} — {label}]")
    return "  ".join(parts)


def _format_debug_panel(debug_info: dict) -> str:
    """Format debug info as a readable panel."""
    lines = []
    lines.append("─── debug ───")

    timings = debug_info.get("timings", {})
    total = debug_info.get("total_ms", 0)

    # Interpreter summary
    interp = debug_info.get("interpreter", {})
    actions = interp.get("proposed_actions", [])
    if actions:
        action_strs = [f"{a.get('action', '?')}→{a.get('target_id', '?')}" for a in actions]
        lines.append(f"  interpreter: {', '.join(action_strs)}  ({timings.get('interpreter_ms', '?')}ms)")
    else:
        lines.append(f"  interpreter: (no actions)  ({timings.get('interpreter_ms', '?')}ms)")

    # Validator summary
    validator = debug_info.get("validator", {})
    allowed = len(validator.get("allowed_actions", []))
    blocked = len(validator.get("blocked_actions", []))
    lines.append(f"  validator: {allowed} allowed, {blocked} blocked")

    # Resolver summary
    resolver = debug_info.get("resolver", {})
    events = resolver.get("engine_events", [])
    if events:
        event_types = [e.get("type", "?") for e in events]
        lines.append(f"  resolver: {', '.join(event_types)}")

    # Show dice rolls from resolver
    rolls = resolver.get("rolls", [])
    for roll in rolls:
        dice = roll.get("dice", "2d6")
        raw = roll.get("raw_values", [])
        total = roll.get("total", "?")
        outcome = roll.get("outcome", "?")
        margin = roll.get("margin", 0)
        action = roll.get("action", "?")
        lines.append(f"    roll [{action}]: {dice}={raw} total={total} → {outcome} (margin={margin})")

    # Timing
    stage_parts = []
    for key in ["interpreter_ms", "planner_ms", "narrator_ms"]:
        if key in timings:
            label = key.replace("_ms", "")
            stage_parts.append(f"{label}={timings[key]}ms")
    lines.append(f"  timing: {', '.join(stage_parts)}  (total {total}ms)")
    lines.append("─────────────")
    return "\n".join(lines)


def play_cmd(args):
    """Interactive play mode (REPL)."""
    from src.cli.spinner import Spinner

    store = StateStore(args.db)
    store.ensure_schema()

    # Check campaign exists
    campaign = store.get_campaign(args.campaign)
    if not campaign:
        print(f"Error: Campaign '{args.campaign}' not found.")
        print("Run 'new-game' first to create a campaign.")
        sys.exit(1)

    # Check for API key
    api_key = check_auth_or_prompt()
    if not api_key:
        print("\n  Cannot play without an API key.")
        print("  Run 'login' to set one up, or set ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)

    # Debug mode state
    debug_mode = getattr(args, "verbose", False)

    # Spinner reference for stage updates
    active_spinner = [None]  # mutable container for closure

    def on_stage(stage_name: str):
        if active_spinner[0]:
            active_spinner[0].update(stage_name)

    # Setup orchestrator with real LLM
    prompts_dir = Path(__file__).parent.parent / "prompts"
    prompt_registry = PromptRegistry(prompts_dir)
    gateway = ClaudeGateway(api_key=api_key)

    # Setup content pack components from campaign record
    lore_retriever = None
    scene_cache = None
    session_mgr = None
    pack_ids = campaign.get("pack_ids", [])
    lore_manifest = campaign.get("lore_manifest", {})

    # Fall back to all installed packs if campaign has none declared
    if not pack_ids:
        packs = store.list_content_packs()
        if packs:
            pack_ids = [p["id"] for p in packs]

    if pack_ids:
        vector_store = create_vector_store()
        lore_retriever = LoreRetriever(store, vector_store, entity_manifest=lore_manifest)
        scene_cache = SceneLoreCacheManager(store)

    # Session manager (always active)
    session_mgr = SessionManager(store)
    active_session = session_mgr.start_session(args.campaign)

    orchestrator = Orchestrator(
        state_store=store,
        llm_gateway=gateway,
        prompt_registry=prompt_registry,
        on_stage=on_stage,
        lore_retriever=lore_retriever,
        scene_cache=scene_cache,
        session_manager=session_mgr,
        pack_ids=pack_ids
    )

    print(f"\n{'='*60}")
    print(f"Freeform RPG - Interactive Mode")
    print(f"Campaign: {campaign.get('name', args.campaign)}")
    if pack_ids:
        print(f"Content packs: {', '.join(pack_ids)}")
    print(f"{'='*60}")
    print("Type your actions, or 'quit' to exit.")
    print("Commands: /status, /clocks, /scene, /debug, /help\n")

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
    last_turn_no = events[-1]["turn_no"] if events else None

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            if session_mgr and active_session:
                session_mgr.end_session(active_session["id"])
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ['quit', 'exit', 'q', '/quit']:
            if session_mgr and active_session:
                session_mgr.end_session(active_session["id"])
            print("Goodbye!")
            break

        # Handle /debug toggle
        if user_input.lower() == '/debug':
            debug_mode = not debug_mode
            print(f"Debug mode: {'on' if debug_mode else 'off'}")
            continue

        # Handle other commands
        if user_input.startswith('/'):
            _handle_command(user_input, store, args.campaign, last_turn_no)
            continue

        # Run turn with spinner
        try:
            spinner = Spinner("Thinking")
            active_spinner[0] = spinner

            with spinner:
                result = orchestrator.run_turn(args.campaign, user_input)

            active_spinner[0] = None
            turn_count += 1
            last_turn_no = result.turn_no
            print(f"\n{result.final_text}\n")

            # Show location header on scene transition
            narrator_data = result.debug_info.get("narrator", {})
            scene_transition = narrator_data.get("scene_transition")
            if scene_transition:
                loc_name = scene_transition.get("location_name", "Unknown")
                loc_desc = scene_transition.get("description", "")
                print(f"[Location: {loc_name}]")
                if loc_desc:
                    print(f"{loc_desc}")
                print()

            # Show clock deltas (always visible when clocks change)
            clocks_line = _format_clock_deltas(result.clock_deltas)
            if clocks_line:
                print(f"  {clocks_line}")

            # Show dice rolls (always visible when they happen)
            rolls_line = _format_rolls(result.debug_info)
            if rolls_line:
                print(f"  {rolls_line}")

            # Extra blank line after status indicators
            if clocks_line or rolls_line:
                print()

            if result.clarification_needed:
                print(f"[{result.clarification_question}]")

            if debug_mode and result.debug_info:
                print(_format_debug_panel(result.debug_info))
                print()

        except Exception as e:
            active_spinner[0] = None
            print(f"Error: {e}")


def _handle_command(cmd, store, campaign_id, last_turn_no=None):
    """Handle REPL commands."""
    parts = cmd.lower().split()
    base_cmd = parts[0]

    if base_cmd == '/help':
        print("""
Commands:
  /status  - Show character status (harm, cred)
  /clocks  - Show all clocks
  /scene   - Show current scene
  /threads - Show active threads
  /debug   - Toggle debug mode (show pipeline internals)

Feedback:
  /good    - Mark last turn as good (thumbs up)
  /bad     - Mark last turn as bad (thumbs down)
  /flag    - Flag an issue with last turn
  /note    - Add a comment about last turn
  /eval    - Show evaluation summary

  /quit    - Exit the game
""")
    elif base_cmd == '/status' or base_cmd == '/clocks':
        clocks = store.get_all_clocks()
        print("\n=== Clocks ===")
        for c in clocks:
            bar = _progress_bar(c['value'], c['max'])
            print(f"  {c['name']}: {bar} {c['value']}/{c['max']}")
        print()

    elif base_cmd == '/scene':
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

    elif base_cmd == '/threads':
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

    # Feedback commands
    elif base_cmd == '/good':
        _log_feedback(store, campaign_id, last_turn_no, "thumbs_up")
        print("👍 Feedback recorded. Thanks!")

    elif base_cmd == '/bad':
        _log_feedback(store, campaign_id, last_turn_no, "thumbs_down")
        print("👎 Feedback recorded. We'll try to improve.")

    elif base_cmd == '/flag':
        issue = " ".join(parts[1:]) if len(parts) > 1 else input("What's the issue? ")
        _log_feedback(store, campaign_id, last_turn_no, "flag_issue", issue)
        print(f"🚩 Issue flagged: {issue}")

    elif base_cmd == '/note':
        note = " ".join(parts[1:]) if len(parts) > 1 else input("Your note: ")
        _log_feedback(store, campaign_id, last_turn_no, "comment", note)
        print(f"📝 Note recorded.")

    elif base_cmd == '/eval':
        _show_eval_summary(store, campaign_id)

    else:
        print(f"Unknown command: {cmd}")
        print("Type /help for available commands.")


def _log_feedback(store, campaign_id, turn_no, feedback_type, value=None):
    """Log player feedback."""
    from src.eval import EvaluationTracker, PlayerFeedback, FeedbackType

    if turn_no is None:
        print("No turn to give feedback on yet.")
        return

    tracker = EvaluationTracker(store)
    ft = FeedbackType(feedback_type)
    feedback = PlayerFeedback(turn_no=turn_no, feedback_type=ft, value=value)
    tracker.log_feedback(campaign_id, feedback)


def _show_eval_summary(store, campaign_id):
    """Show evaluation summary."""
    from src.eval import EvaluationTracker

    tracker = EvaluationTracker(store)

    print("\n=== Evaluation Summary ===")

    # Metrics summary
    metrics = tracker.get_metrics_summary(campaign_id)
    if metrics["turns"] > 0:
        print(f"\nTurns played: {metrics['turns']}")
        summary = metrics.get("summary", {})
        print(f"Avg latency: {summary.get('avg_latency_ms', 0):.0f}ms")
        print(f"Clarification rate: {summary.get('clarification_rate', 0):.0%}")
        print(f"Avg narrative length: {summary.get('avg_narrative_length', 0):.0f} chars")

    # Feedback summary
    feedback = tracker.get_feedback_summary(campaign_id)
    if feedback["total"] > 0:
        print(f"\nFeedback received: {feedback['total']}")
        sentiment = feedback.get("sentiment", {})
        if sentiment.get("ratio") is not None:
            print(f"Sentiment: {sentiment['positive']}👍 / {sentiment['negative']}👎 ({sentiment['ratio']:.0%} positive)")

    # Problem turns
    problems = tracker.get_problematic_turns(campaign_id)
    if problems:
        print(f"\nProblem turns: {len(problems)}")
        for p in problems[:3]:  # Show first 3
            print(f"  Turn {p['turn_no']}: {', '.join(p['issues'])}")

    print()


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


def eval_cmd(args):
    """Show evaluation report for campaign."""
    from src.eval import EvaluationTracker
    import json

    store = StateStore(args.db)
    tracker = EvaluationTracker(store)

    metrics = tracker.get_metrics_summary(args.campaign)
    feedback = tracker.get_feedback_summary(args.campaign)
    problems = tracker.get_problematic_turns(args.campaign)

    report = {
        "campaign_id": args.campaign,
        "metrics": metrics,
        "feedback": feedback,
        "problem_turns": problems
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("\n" + "=" * 60)
        print(f"Evaluation Report: {args.campaign}")
        print("=" * 60)

        if metrics["turns"] > 0:
            print(f"\n📊 Metrics ({metrics['turns']} turns):")
            summary = metrics.get("summary", {})
            print(f"  Avg latency: {summary.get('avg_latency_ms', 0):.0f}ms")
            print(f"  Clarification rate: {summary.get('clarification_rate', 0):.0%}")
            print(f"  Avg narrative length: {summary.get('avg_narrative_length', 0):.0f} chars")

            rolls = summary.get("roll_distribution", {})
            if rolls:
                print(f"  Roll outcomes: {rolls}")
        else:
            print("\n📊 No metrics recorded yet.")

        if feedback["total"] > 0:
            print(f"\n💬 Feedback ({feedback['total']} items):")
            sentiment = feedback.get("sentiment", {})
            if sentiment.get("ratio") is not None:
                print(f"  👍 {sentiment['positive']} / 👎 {sentiment['negative']} ({sentiment['ratio']:.0%} positive)")

            by_type = feedback.get("by_type", {})
            if by_type.get("flag_issue"):
                print(f"  🚩 Flagged issues: {len(by_type['flag_issue'])}")
            if by_type.get("comment"):
                print(f"  📝 Comments: {len(by_type['comment'])}")
        else:
            print("\n💬 No feedback recorded yet.")

        if problems:
            print(f"\n⚠️  Problem turns ({len(problems)}):")
            for p in problems[:5]:
                print(f"  Turn {p['turn_no']}: {', '.join(p['issues'])}")
            if len(problems) > 5:
                print(f"  ... and {len(problems) - 5} more")
        else:
            print("\n✅ No problem turns detected.")

        print()


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


def pack_test_cmd(args):
    """Test a content pack: analyze, generate scenario, run retrieval probes."""
    from src.ingest.pack_test import PackTester

    tester = PackTester(args.pack_dir)
    report = tester.test(
        generate_scenario=not args.no_scenario,
        scenario_dir=args.scenario_dir,
    )
    print(report.format())


def install_pack_cmd(args):
    """Install (index) a content pack into the database."""
    store = StateStore(args.db)
    store.ensure_schema()

    pack_path = Path(args.path)
    loader = PackLoader()
    chunker = Chunker()
    vector_store = create_vector_store()
    indexer = LoreIndexer(store, vector_store)

    try:
        manifest, files = loader.load_pack(pack_path)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    chunks = chunker.chunk_files(files, manifest.id)
    stats = indexer.index_pack(manifest, chunks)

    print(f"\nInstalled content pack: {manifest.name}")
    print(f"  ID: {manifest.id}")
    print(f"  Version: {manifest.version}")
    print(f"  Layer: {manifest.layer}")
    print(f"  Files: {len(files)}")
    print(f"  Chunks indexed: {stats.chunks_indexed}")
    print(f"  FTS5 indexed: {stats.fts_indexed}")
    print(f"  Vector indexed: {stats.vector_indexed}")


def list_packs_cmd(args):
    """List installed content packs."""
    store = StateStore(args.db)
    store.ensure_schema()

    packs = store.list_content_packs()
    if not packs:
        print("No content packs installed.")
        print("Use 'install-pack <path>' to install one.")
        return

    print(f"\nInstalled Content Packs ({len(packs)}):")
    print("-" * 50)
    for pack in packs:
        print(f"  {pack['id']}: {pack['name']} v{pack['version']}")
        print(f"    Layer: {pack['layer']}, Chunks: {pack['chunk_count']}")
        if pack['description']:
            print(f"    {pack['description'][:60]}")
    print()


# =============================================================================
# Ingest Pipeline Commands
# =============================================================================

def _make_ingest_config(args):
    """Build IngestConfig from CLI args."""
    from src.ingest.models import IngestConfig

    pdf_path = getattr(args, "input", "") or ""
    # Derive pack_id and pack_name from PDF filename when not provided
    pdf_stem = Path(pdf_path).stem if pdf_path else "unknown"
    pack_id = getattr(args, "pack_id", None) or pdf_stem.lower().replace(" ", "_").replace("-", "_")
    pack_name = getattr(args, "pack_name", None) or pdf_stem.replace("_", " ").replace("-", " ").title()

    return IngestConfig(
        pdf_path=pdf_path,
        output_dir=getattr(args, "output", "") or "",
        pack_id=pack_id,
        pack_name=pack_name,
        pack_version=getattr(args, "pack_version", None) or "1.0",
        pack_layer=getattr(args, "pack_layer", None) or "sourcebook",
        pack_author=getattr(args, "pack_author", None) or "",
        pack_description=getattr(args, "pack_description", None) or "",
        use_ocr=getattr(args, "ocr", False),
        extract_images=getattr(args, "extract_images", False),
        skip_systems=getattr(args, "skip_systems", False),
        draft_mode=getattr(args, "draft", False),
        system_hint=getattr(args, "system_hint", "") or "",
        work_dir=getattr(args, "output", "") or "",
    )


def _make_gateways(args):
    """Create LLM gateways for ingest pipeline."""
    api_key = check_auth_or_prompt()
    if not api_key:
        print("Cannot run ingest without an API key.")
        print("Run 'login' to set one up, or set ANTHROPIC_API_KEY.")
        sys.exit(1)

    sonnet = ClaudeGateway(api_key=api_key)
    haiku = ClaudeGateway(api_key=api_key, model="claude-3-5-haiku-20241022")
    prompts_dir = Path(__file__).parent.parent / "prompts"
    registry = PromptRegistry(prompts_dir)
    return sonnet, haiku, registry


def pack_ingest_cmd(args):
    """Full PDF-to-content-pack pipeline."""
    # No args → interactive mode
    if getattr(args, "input", None) is None:
        from src.cli.ingest_flow import ingest_flow
        ingest_flow(db_path=args.db)
        return
    if getattr(args, "output", None) is None:
        print("Error: --output is required in non-interactive mode.")
        sys.exit(1)

    from src.ingest.pipeline import IngestPipeline
    from src.cli.ingest_flow import InstrumentedPipeline

    config = _make_ingest_config(args)
    sonnet, haiku, registry = _make_gateways(args)

    # Get system hint from args or config
    system_hint = getattr(args, "system_hint", None) or config.system_hint or None

    pipeline = IngestPipeline(
        config=config,
        sonnet_gateway=sonnet,
        haiku_gateway=haiku,
        prompt_registry=registry,
        system_hint=system_hint,
    )
    instrumented = InstrumentedPipeline(pipeline)
    summary = instrumented.run(
        resume=not getattr(args, "no_resume", False),
        from_stage=getattr(args, "from_stage", None),
    )

    print(f"\nPipeline complete!")
    print(f"  Pack directory: {summary['pack_dir']}")
    print(f"  Valid: {summary['pack_valid']}")
    if summary.get("validation_errors"):
        print(f"  Errors: {len(summary['validation_errors'])}")
        for err in summary["validation_errors"][:5]:
            print(f"    - {err}")
    if summary.get("timings"):
        total_ms = sum(summary["timings"].values())
        print(f"  Total time: {total_ms / 1000:.1f}s")


def ingest_extract_cmd(args):
    """Stage 1: PDF text extraction."""
    from src.ingest.extract import PDFExtractor

    extractor = PDFExtractor()
    result = extractor.extract(
        pdf_path=args.input,
        output_dir=args.output,
        use_ocr=getattr(args, "ocr", False),
        pages=getattr(args, "pages", None),
        extract_images=getattr(args, "extract_images", False),
    )
    print(f"Extracted {len(result.pages)} pages to {args.output}")
    print(f"  Total pages in PDF: {result.total_pages}")
    print(f"  OCR used: {result.metadata.get('ocr_used', False)}")


def ingest_structure_cmd(args):
    """Stage 2: Document structure detection."""
    from src.ingest.structure import StructureDetector
    from src.ingest.extract import PDFExtractor
    from src.ingest.utils import read_stage_meta

    # Load extraction result from stage 1 output
    extraction = _load_extraction(args.input)

    sonnet, haiku, registry = _make_gateways(args)
    detector = StructureDetector(llm_gateway=haiku, prompt_registry=registry)
    structure = detector.detect(
        extraction=extraction,
        output_dir=args.output,
        pdf_path=getattr(args, "pdf", None),
    )
    print(f"Detected {len(structure.sections)} top-level sections")
    print(f"  Title: {structure.title}")
    print(f"  Method: {structure.metadata.get('detection_method', 'unknown')}")


def ingest_segment_cmd(args):
    """Stage 3: Content segmentation."""
    from src.ingest.segment import ContentSegmenter

    structure = _load_structure(args.input)

    sonnet, haiku, registry = _make_gateways(args)
    segmenter = ContentSegmenter(
        llm_gateway=haiku, prompt_registry=registry,
    )
    manifest = segmenter.segment(structure=structure, output_dir=args.output)
    print(f"Created {len(manifest.segments)} segments")
    print(f"  Total words: {manifest.total_words}")


def ingest_classify_cmd(args):
    """Stage 4: Content classification."""
    from src.ingest.classify import ContentClassifier

    manifest = _load_segment_manifest(args.input)

    sonnet, haiku, registry = _make_gateways(args)
    classifier = ContentClassifier(llm_gateway=haiku, prompt_registry=registry)
    manifest = classifier.classify(manifest=manifest, output_dir=args.output)

    lore = sum(1 for s in manifest.segments if s.route and s.route.value == "lore")
    systems = sum(1 for s in manifest.segments if s.route and s.route.value == "systems")
    both = sum(1 for s in manifest.segments if s.route and s.route.value == "both")
    print(f"Classified {len(manifest.segments)} segments")
    print(f"  Lore: {lore}, Systems: {systems}, Both: {both}")


def ingest_enrich_cmd(args):
    """Stage 5: Lore enrichment."""
    from src.ingest.enrich import LoreEnricher

    manifest = _load_segment_manifest(args.input)

    sonnet, haiku, registry = _make_gateways(args)
    enricher = LoreEnricher(
        llm_gateway=sonnet, prompt_registry=registry, tag_gateway=haiku,
    )
    enriched_files, registry_data = enricher.enrich(
        manifest=manifest, output_dir=args.output,
    )
    print(f"Enriched {len(enriched_files)} files")
    print(f"  Entities found: {len(registry_data.entities)}")


def ingest_assemble_cmd(args):
    """Stage 6: Content pack assembly."""
    from src.ingest.assemble import PackAssembler

    config = _make_ingest_config(args)
    enriched_files = _load_enriched_manifest(args.input)
    entity_registry = _load_entity_registry(args.input)

    assembler = PackAssembler()
    pack_dir = assembler.assemble(
        enriched_files=enriched_files,
        config=config,
        output_dir=args.output,
        entity_registry=entity_registry,
    )
    print(f"Assembled pack at: {pack_dir}")


def ingest_audit_cmd(args):
    """Post-ingest audit of pipeline output."""
    from src.ingest.audit import IngestAuditor

    auditor = IngestAuditor(args.input)
    report = auditor.audit(samples=args.samples)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(auditor.format_report(report))


def ingest_validate_cmd(args):
    """Stage 7: Pack validation."""
    from src.ingest.validate import PackValidator

    validator = PackValidator()
    report = validator.validate(
        pack_dir=args.input,
        output_dir=getattr(args, "output", None),
    )

    status = "PASSED" if report.valid else "FAILED"
    print(f"Validation: {status}")
    if report.errors:
        print(f"  Errors ({len(report.errors)}):")
        for err in report.errors:
            print(f"    - {err}")
    if report.warnings:
        print(f"  Warnings ({len(report.warnings)}):")
        for w in report.warnings:
            print(f"    - {w}")
    if report.stats.get("installation"):
        inst = report.stats["installation"]
        print(f"  Files loaded: {inst.get('files_loaded', 0)}")
        print(f"  Chunks created: {inst.get('chunks_created', 0)}")


def ingest_systems_extract_cmd(args):
    """Stage S1: Systems extraction."""
    from src.ingest.systems_extract import SystemsExtractor

    manifest = _load_segment_manifest(args.input)

    sonnet, haiku, registry = _make_gateways(args)
    extractor = SystemsExtractor(llm_gateway=haiku, prompt_registry=registry)
    result = extractor.extract(manifest=manifest, output_dir=args.output)
    print(f"Ran {len(result.extractions)} sub-extractors")
    print(f"  Keys: {', '.join(result.extractions.keys())}")


def ingest_systems_assemble_cmd(args):
    """Stage S2: Systems assembly."""
    from src.ingest.systems_assemble import SystemsAssembler
    from src.ingest.models import SystemsExtractionManifest

    extraction = _load_systems_extraction(args.input)

    assembler = SystemsAssembler()
    outputs = assembler.assemble(extraction=extraction, output_dir=args.output)
    print(f"Generated {len(outputs)} config files:")
    for name, path in outputs.items():
        print(f"  {name}: {path}")


def ingest_systems_validate_cmd(args):
    """Stage S3: Systems validation."""
    from src.ingest.systems_validate import SystemsValidator

    validator = SystemsValidator()
    report = validator.validate(
        configs_dir=args.input,
        output_dir=getattr(args, "output", None),
    )

    status = "PASSED" if report.valid else "FAILED"
    print(f"Systems validation: {status}")
    if report.errors:
        for err in report.errors:
            print(f"  ERROR: {err}")
    if report.warnings:
        for w in report.warnings:
            print(f"  WARNING: {w}")


def promote_draft_cmd(args):
    """Promote a draft pack to content_packs/."""
    import shutil

    draft_path = Path(args.draft_path)
    if not draft_path.exists():
        print(f"Error: Draft not found at {draft_path}")
        sys.exit(1)

    # Check for draft markers
    if not (draft_path / "REVIEW_NEEDED.md").exists():
        print(f"Warning: {draft_path} doesn't appear to be a draft pack (no REVIEW_NEEDED.md)")
        response = input("Promote anyway? [y/N] ").strip().lower()
        if response != "y":
            print("Cancelled.")
            return

    # Determine target directory
    target_dir = Path(args.target) if args.target else Path("content_packs")
    pack_name = draft_path.name
    target_path = target_dir / pack_name

    if target_path.exists():
        if not args.force:
            print(f"Error: {target_path} already exists. Use --force to overwrite.")
            sys.exit(1)
        shutil.rmtree(target_path)

    # Copy draft to target, excluding draft markers
    target_path.mkdir(parents=True)

    excluded_files = {"REVIEW_NEEDED.md", "DRAFT_README.md", "EXTRACTION_REPORT.md"}

    for item in draft_path.iterdir():
        if item.name in excluded_files:
            continue
        if item.is_dir():
            shutil.copytree(item, target_path / item.name)
        else:
            shutil.copy2(item, target_path / item.name)

    print(f"Promoted draft to: {target_path}")
    print(f"\nTo install the pack:")
    print(f"  freeform-rpg --db {args.db} install-pack {target_path}")


def list_systems_cmd(args):
    """List available system configs."""
    from src.ingest.systems_config import get_available_systems, SYSTEMS_DIR

    systems = get_available_systems()

    print(f"\nAvailable System Configs ({SYSTEMS_DIR}):")
    print("-" * 40)

    if not systems:
        print("  (none found)")
    else:
        for system_id in systems:
            print(f"  {system_id}")

    print("\nUse --system-hint <id> with pack-ingest to apply system-specific patterns.")
    print()


# Helpers for loading intermediate pipeline outputs

def _load_extraction(input_dir):
    """Load ExtractionResult from a stage 1 output directory."""
    from src.ingest.models import ExtractionResult, PageEntry
    from src.ingest.utils import read_manifest

    input_dir = Path(input_dir)
    page_map = read_manifest(input_dir / "page_map.json")
    meta = read_manifest(input_dir / "stage_meta.json") if (input_dir / "stage_meta.json").exists() else {}

    pages = []
    pages_dir = input_dir / "pages"
    if pages_dir.exists():
        for page_file in sorted(pages_dir.glob("page_*.md")):
            page_num = int(page_file.stem.split("_")[1])
            text = page_file.read_text(encoding="utf-8")
            info = page_map.get(str(page_num), {})
            pages.append(PageEntry(
                page_num=page_num,
                text=text,
                char_count=info.get("char_count", len(text)),
                has_images=info.get("has_images", False),
                ocr_used=info.get("ocr_used", False),
            ))

    return ExtractionResult(
        pdf_path=meta.get("pdf_path", ""),
        total_pages=meta.get("total_pages", len(pages)),
        pages=pages,
        output_dir=str(input_dir),
    )


def _load_structure(input_dir):
    """Load DocumentStructure from a stage 2 output directory."""
    from src.ingest.models import ChapterIntent, DocumentStructure, SectionNode
    from src.ingest.utils import read_manifest

    input_dir = Path(input_dir)
    data = read_manifest(input_dir / "structure.json")

    def parse_node(d, default_level=1):
        intent = None
        if d.get("intent"):
            try:
                intent = ChapterIntent(d["intent"])
            except ValueError:
                pass
        children = [parse_node(c, 2) for c in d.get("children", [])]
        return SectionNode(
            title=d.get("title", "Untitled"),
            level=d.get("level", default_level),
            page_start=d.get("page_start", 1),
            page_end=d.get("page_end", 1),
            children=children,
            content=d.get("content", ""),
            intent=intent,
        )

    # Load chapter content from files
    sections = [parse_node(s) for s in data.get("sections", [])]
    chapters_dir = input_dir / "chapters"
    if chapters_dir.exists():
        for i, section in enumerate(sections):
            # Try to load chapter content from file
            for chapter_file in chapters_dir.glob(f"{i + 1:02d}_*.md"):
                section.content = chapter_file.read_text(encoding="utf-8")
                break

    return DocumentStructure(
        title=data.get("title", "Untitled"),
        sections=sections,
        metadata=data.get("metadata", {}),
    )


def _load_segment_manifest(input_dir):
    """Load SegmentManifest from a stage 3/4 output directory."""
    from src.ingest.models import ChapterIntent, ContentType, Route, SegmentEntry, SegmentManifest
    from src.ingest.utils import read_manifest

    input_dir = Path(input_dir)
    data = read_manifest(input_dir / "segment_manifest.json")

    segments = []
    segments_dir = input_dir / "segments"
    for s in data.get("segments", []):
        # Load content from segment file
        content = ""
        if segments_dir.exists():
            for seg_file in segments_dir.glob(f"{s['id']}_*.md"):
                raw = seg_file.read_text(encoding="utf-8")
                # Strip leading H1 title
                lines = raw.split("\n")
                if lines and lines[0].startswith("# "):
                    content = "\n".join(lines[1:]).strip()
                else:
                    content = raw.strip()
                break

        content_type = None
        if s.get("content_type"):
            try:
                content_type = ContentType(s["content_type"])
            except ValueError:
                pass

        route = None
        if s.get("route"):
            try:
                route = Route(s["route"])
            except ValueError:
                pass

        chapter_intent = None
        if s.get("chapter_intent"):
            try:
                chapter_intent = ChapterIntent(s["chapter_intent"])
            except ValueError:
                pass

        segments.append(SegmentEntry(
            id=s["id"],
            title=s.get("title", ""),
            content=content,
            source_section=s.get("source_section", ""),
            page_start=s.get("page_start", 0),
            page_end=s.get("page_end", 0),
            word_count=s.get("word_count", 0),
            content_type=content_type,
            route=route,
            classification_confidence=s.get("classification_confidence", 0.0),
            tags=s.get("tags", []),
            chapter_intent=chapter_intent,
        ))

    return SegmentManifest(
        segments=segments,
        total_words=data.get("total_words", 0),
        metadata=data.get("metadata", {}),
    )


def _load_entity_registry(input_dir):
    """Load EntityRegistry from an enrich output directory, or None if absent."""
    from src.ingest.models import EntityEntry, EntityRegistry
    from src.ingest.utils import read_manifest

    input_dir = Path(input_dir)
    registry_path = input_dir / "entity_registry.json"
    if not registry_path.exists():
        return None

    registry = EntityRegistry()
    reg_data = read_manifest(registry_path)
    for e in reg_data.get("entities", []):
        registry.add(EntityEntry(
            id=e.get("id", ""),
            name=e.get("name", ""),
            entity_type=e.get("entity_type", "general"),
            description=e.get("description", ""),
            aliases=e.get("aliases", []),
            related_entities=e.get("related_entities", []),
            source_segments=e.get("source_segments", []),
        ))
    return registry


def _load_enriched_manifest(input_dir):
    """Load enriched files list from an enrich output directory."""
    from src.ingest.utils import read_manifest

    input_dir = Path(input_dir)
    # Read entity registry for reference
    enriched_dir = input_dir / "enriched"
    if not enriched_dir.exists():
        print(f"Error: No enriched directory found at {enriched_dir}")
        sys.exit(1)

    files = []
    for type_dir in enriched_dir.iterdir():
        if type_dir.is_dir():
            for md_file in sorted(type_dir.glob("*.md")):
                from src.ingest.utils import read_markdown_with_frontmatter
                fm, body = read_markdown_with_frontmatter(md_file)
                files.append({
                    "path": str(md_file),
                    "title": fm.get("title", md_file.stem),
                    "file_type": fm.get("type", "general"),
                    "entity_id": fm.get("entity_id", md_file.stem),
                    "frontmatter": fm,
                })
    return files


def _load_systems_extraction(input_dir):
    """Load SystemsExtractionManifest from a systems extract output."""
    from src.ingest.models import SystemsExtractionManifest
    from src.ingest.utils import read_manifest

    import yaml

    input_dir = Path(input_dir)
    manifest_data = read_manifest(input_dir / "extraction_manifest.json")

    extractions = {}
    for key in manifest_data.get("extractors_run", []):
        yaml_path = input_dir / f"{key}.yaml"
        if yaml_path.exists():
            extractions[key] = yaml.safe_load(yaml_path.read_text())

    return SystemsExtractionManifest(
        extractions=extractions,
        source_segments=manifest_data.get("source_segments", []),
    )


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

    sub = parser.add_subparsers(dest="command")

    # login
    login_parser = sub.add_parser("login", help="Set up API key")
    login_parser.set_defaults(func=login_cmd)

    # logout
    logout_parser = sub.add_parser("logout", help="Remove stored API key")
    logout_parser.set_defaults(func=logout_cmd)

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

    # install-pack
    install_pack_parser = sub.add_parser("install-pack", help="Install a content pack")
    install_pack_parser.add_argument("path", help="Path to content pack directory")
    install_pack_parser.set_defaults(func=install_pack_cmd)

    # list-packs
    list_packs_parser = sub.add_parser("list-packs", help="List installed content packs")
    list_packs_parser.set_defaults(func=list_packs_cmd)

    # pack-test
    pack_test_parser = sub.add_parser("pack-test", help="Test a content pack")
    pack_test_parser.add_argument("pack_dir", help="Path to assembled pack directory")
    pack_test_parser.add_argument("--no-scenario", action="store_true", help="Skip scenario generation")
    pack_test_parser.add_argument("--scenario-dir", default="scenarios", help="Where to save test scenario")
    pack_test_parser.set_defaults(func=pack_test_cmd)

    # vibe-check
    vibe_check_parser = sub.add_parser(
        "vibe-check",
        help="Test content pack quality with scene prompts (no scenario setup)"
    )
    vibe_check_parser.add_argument("--pack", required=True, help="Path to content pack directory")
    vibe_check_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=True,
        help="Show retrieved lore chunks (on by default)"
    )
    vibe_check_parser.add_argument(
        "--no-verbose",
        action="store_false",
        dest="verbose",
        help="Hide retrieved lore chunks"
    )
    vibe_check_parser.set_defaults(func=vibe_check_cmd)

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
    play_parser.add_argument("--verbose", "-v", action="store_true", help="Show debug info after each turn")
    play_parser.set_defaults(func=play_cmd)

    # eval (evaluation report)
    eval_parser = sub.add_parser("eval", help="Show evaluation report")
    eval_parser.add_argument("--json", action="store_true", help="Output JSON")
    eval_parser.set_defaults(func=eval_cmd)

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

    # =================================================================
    # Ingest Pipeline Commands
    # =================================================================

    # pack-ingest (full pipeline)
    ingest_parser = sub.add_parser("pack-ingest", help="Full PDF-to-content-pack pipeline")
    ingest_parser.add_argument("input", nargs="?", default=None, help="Path to PDF file")
    ingest_parser.add_argument("--output", "-o", default=None, help="Output directory")
    ingest_parser.add_argument("--pack-id", help="Content pack ID")
    ingest_parser.add_argument("--pack-name", help="Content pack name")
    ingest_parser.add_argument("--pack-version", default="1.0", help="Pack version")
    ingest_parser.add_argument("--pack-layer", default="sourcebook", help="Pack layer")
    ingest_parser.add_argument("--pack-author", default="", help="Pack author")
    ingest_parser.add_argument("--pack-description", default="", help="Pack description")
    ingest_parser.add_argument("--ocr", action="store_true", help="Use OCR for image-heavy pages")
    ingest_parser.add_argument("--extract-images", action="store_true", help="Extract images")
    ingest_parser.add_argument("--skip-systems", action="store_true", help="Skip systems extraction")
    ingest_parser.add_argument("--no-resume", action="store_true", help="Don't resume from checkpoints")
    ingest_parser.add_argument(
        "--system-hint",
        help="System ID for extraction config (e.g., world_of_darkness). Use 'list-systems' to see available.",
    )
    ingest_parser.add_argument(
        "--draft",
        action="store_true",
        help="Output to draft/ with review markers instead of content_packs/",
    )
    ingest_parser.add_argument(
        "--from-stage",
        choices=["extract", "structure", "segment", "classify",
                 "enrich", "assemble", "validate", "systems"],
        help="Re-run from this stage onwards (clears it + downstream, resumes upstream)",
    )
    ingest_parser.set_defaults(func=pack_ingest_cmd)

    # ingest-extract (stage 1)
    extract_parser = sub.add_parser("ingest-extract", help="Stage 1: PDF text extraction")
    extract_parser.add_argument("input", help="Path to PDF file")
    extract_parser.add_argument("--output", "-o", required=True, help="Output directory")
    extract_parser.add_argument("--ocr", action="store_true", help="Use OCR fallback")
    extract_parser.add_argument("--pages", help="Page range (e.g. '1-5,8')")
    extract_parser.add_argument("--extract-images", action="store_true", help="Extract images")
    extract_parser.set_defaults(func=ingest_extract_cmd)

    # ingest-structure (stage 2)
    structure_parser = sub.add_parser("ingest-structure", help="Stage 2: Document structure detection")
    structure_parser.add_argument("input", help="Stage 1 output directory")
    structure_parser.add_argument("--output", "-o", required=True, help="Output directory")
    structure_parser.add_argument("--pdf", help="Original PDF path (for font analysis)")
    structure_parser.set_defaults(func=ingest_structure_cmd)

    # ingest-segment (stage 3)
    segment_parser = sub.add_parser("ingest-segment", help="Stage 3: Content segmentation")
    segment_parser.add_argument("input", help="Stage 2 output directory")
    segment_parser.add_argument("--output", "-o", required=True, help="Output directory")
    segment_parser.set_defaults(func=ingest_segment_cmd)

    # ingest-classify (stage 4)
    classify_parser = sub.add_parser("ingest-classify", help="Stage 4: Content classification")
    classify_parser.add_argument("input", help="Stage 3 output directory")
    classify_parser.add_argument("--output", "-o", required=True, help="Output directory")
    classify_parser.set_defaults(func=ingest_classify_cmd)

    # ingest-enrich (stage 5)
    enrich_parser = sub.add_parser("ingest-enrich", help="Stage 5: Lore enrichment")
    enrich_parser.add_argument("input", help="Stage 4 output directory")
    enrich_parser.add_argument("--output", "-o", required=True, help="Output directory")
    enrich_parser.set_defaults(func=ingest_enrich_cmd)

    # ingest-assemble (stage 6)
    assemble_parser = sub.add_parser("ingest-assemble", help="Stage 6: Content pack assembly")
    assemble_parser.add_argument("input", help="Stage 5 output directory")
    assemble_parser.add_argument("--output", "-o", required=True, help="Output directory")
    assemble_parser.add_argument("--pack-id", default="", help="Pack ID")
    assemble_parser.add_argument("--pack-name", default="", help="Pack name")
    assemble_parser.add_argument("--pack-version", default="1.0", help="Pack version")
    assemble_parser.add_argument("--pack-layer", default="sourcebook", help="Pack layer")
    assemble_parser.add_argument("--pack-author", default="", help="Pack author")
    assemble_parser.add_argument("--pack-description", default="", help="Pack description")
    assemble_parser.set_defaults(func=ingest_assemble_cmd)

    # ingest-validate (stage 7)
    validate_parser = sub.add_parser("ingest-validate", help="Stage 7: Pack validation")
    validate_parser.add_argument("input", help="Content pack directory")
    validate_parser.add_argument("--output", "-o", help="Output directory for report")
    validate_parser.set_defaults(func=ingest_validate_cmd)

    # ingest-systems-extract (stage S1)
    sys_extract_parser = sub.add_parser("ingest-systems-extract", help="Stage S1: Systems extraction")
    sys_extract_parser.add_argument("input", help="Stage 4 output directory")
    sys_extract_parser.add_argument("--output", "-o", required=True, help="Output directory")
    sys_extract_parser.set_defaults(func=ingest_systems_extract_cmd)

    # ingest-systems-assemble (stage S2)
    sys_assemble_parser = sub.add_parser("ingest-systems-assemble", help="Stage S2: Systems assembly")
    sys_assemble_parser.add_argument("input", help="Stage S1 output directory")
    sys_assemble_parser.add_argument("--output", "-o", required=True, help="Output directory")
    sys_assemble_parser.set_defaults(func=ingest_systems_assemble_cmd)

    # ingest-systems-validate (stage S3)
    sys_validate_parser = sub.add_parser("ingest-systems-validate", help="Stage S3: Systems validation")
    sys_validate_parser.add_argument("input", help="Stage S2 output directory")
    sys_validate_parser.add_argument("--output", "-o", help="Output directory for report")
    sys_validate_parser.set_defaults(func=ingest_systems_validate_cmd)

    # Audit tool
    audit_parser = sub.add_parser("ingest-audit", help="Audit pipeline output quality")
    audit_parser.add_argument("input", help="Pipeline work directory")
    audit_parser.add_argument("--samples", type=int, default=5, help="Pages to spot-check (default 5)")
    audit_parser.add_argument("--json", action="store_true", help="Output as JSON")
    audit_parser.set_defaults(func=ingest_audit_cmd)

    # promote-draft
    promote_parser = sub.add_parser("promote-draft", help="Promote a draft pack to content_packs/")
    promote_parser.add_argument("draft_path", help="Path to draft pack directory")
    promote_parser.add_argument("--target", "-t", help="Target directory (default: content_packs/)")
    promote_parser.add_argument("--force", "-f", action="store_true", help="Overwrite existing pack")
    promote_parser.set_defaults(func=promote_draft_cmd)

    # list-systems
    list_systems_parser = sub.add_parser("list-systems", help="List available system configs")
    list_systems_parser.set_defaults(func=list_systems_cmd)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        from src.cli.guided import guided_flow
        guided_flow(db_path=args.db)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
