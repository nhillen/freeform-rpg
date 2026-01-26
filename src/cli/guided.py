"""
Guided CLI flow for first-run and returning players.

Detects state (API key, database, campaigns) and walks the user
through setup → play without requiring subcommands.
"""

import argparse
import sys

from src.config import get_api_key, interactive_login
from src.db.state_store import StateStore
from src.setup import ScenarioLoader


VERSION = "0.1.0"


def _print_banner():
    print()
    print("┌" + "─" * 58 + "┐")
    print("│" + f" Freeform RPG Engine v{VERSION} ".center(58) + "│")
    print("│" + " AI-driven narrative with real consequences ".center(58) + "│")
    print("└" + "─" * 58 + "┘")
    print()


def _ensure_api_key() -> str | None:
    """Check for API key, prompt login if missing. Returns key or None."""
    api_key = get_api_key()
    if api_key:
        return api_key

    print("  No API key found.")
    print()
    try:
        response = input("  Would you like to set one up now? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    if response in ("", "y", "yes"):
        if interactive_login():
            return get_api_key()

    return None


def _introduce_character(store: StateStore) -> None:
    """Show the player character and let the user rename them."""
    pcs = store.get_entities_by_type("pc")
    if not pcs:
        return

    pc = pcs[0]
    attrs = pc.get("attrs", {})

    print("  ── Your Character ──")
    print()
    print(f"    Name: {pc['name']}")
    if attrs.get("background"):
        print(f"    Background: {attrs['background']}")
    if attrs.get("skills"):
        skills = attrs["skills"]
        if isinstance(skills, list):
            skills = ", ".join(skills)
        print(f"    Skills: {skills}")
    if attrs.get("weakness"):
        print(f"    Weakness: {attrs['weakness']}")
    print()

    try:
        new_name = input(f"  Enter a name (or press Enter to keep \"{pc['name']}\"): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if new_name and new_name != pc["name"]:
        store.update_entity(pc["id"], name=new_name)
        print(f"  Renamed to {new_name}.")
    print()


def _pick_scenario(store: StateStore) -> dict | None:
    """Show scenario picker and load the chosen scenario. Returns campaign info or None."""
    loader = ScenarioLoader(store)
    scenarios = loader.list_scenarios()

    if not scenarios:
        print("  No scenarios found in scenarios/ directory.")
        print("  Add a .yaml scenario file and try again.")
        return None

    print("  Available scenarios:")
    print()
    for i, s in enumerate(scenarios, 1):
        print(f"    {i}. {s['name']}")
        if s.get("description"):
            desc = s["description"]
            if len(desc) > 70:
                desc = desc[:67] + "..."
            print(f"       {desc}")
    print()

    try:
        choice = input("  Pick a scenario [1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    if not choice:
        idx = 0
    else:
        try:
            idx = int(choice) - 1
        except ValueError:
            print(f"  Invalid choice: {choice}")
            return None

    if idx < 0 or idx >= len(scenarios):
        print(f"  Invalid choice: {choice}")
        return None

    scenario = scenarios[idx]
    print()
    print(f"  Loading \"{scenario['name']}\"...")
    print()

    result = loader.load_scenario(scenario["id"])

    # Character intro before showing opening text
    _introduce_character(store)

    if result.get("opening_text"):
        print(f"  {result['opening_text']}")

    print()
    return result


def _select_game(campaigns: list[dict], store: StateStore) -> str | None:
    """Show game selection menu. Returns campaign_id or None."""
    print("  Saved games:")
    print()
    for i, c in enumerate(campaigns, 1):
        turn_info = f"turn {c['current_turn']}" if c.get("current_turn") else "new"
        print(f"    {i}. {c['name']}  ({turn_info})")
    print()
    new_idx = len(campaigns) + 1
    print(f"    {new_idx}. Start a new game")
    print()

    try:
        choice = input("  Choose [1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    if not choice:
        idx = 0
    else:
        try:
            idx = int(choice) - 1
        except ValueError:
            print(f"  Invalid choice: {choice}")
            return None

    # "Start a new game" option
    if idx == len(campaigns):
        result = _pick_scenario(store)
        if not result:
            return None
        return result["campaign_id"]

    if idx < 0 or idx >= len(campaigns):
        print(f"  Invalid choice: {choice}")
        return None

    return campaigns[idx]["id"]


def guided_flow(db_path: str = "game.db"):
    """Main guided flow entry point."""
    _print_banner()

    # Step 1: API key
    api_key = _ensure_api_key()
    if not api_key:
        print("  Cannot play without an API key.")
        print("  Run 'freeform-rpg login' or set ANTHROPIC_API_KEY.")
        sys.exit(1)

    # Step 2: Database (auto-create silently)
    store = StateStore(db_path)
    store.ensure_schema()

    # Step 3: Campaign selection
    campaigns = store.list_campaigns()

    if not campaigns:
        print("  No saved games. Let's start a new one.")
        print()
        result = _pick_scenario(store)
        if not result:
            sys.exit(1)
        campaign_id = result["campaign_id"]
    else:
        campaign_id = _select_game(campaigns, store)
        if not campaign_id:
            sys.exit(1)

    # Step 4: Launch play REPL
    # Build an args namespace that play_cmd expects
    from src.cli.main import play_cmd

    args = argparse.Namespace(db=db_path, campaign=campaign_id)
    play_cmd(args)
