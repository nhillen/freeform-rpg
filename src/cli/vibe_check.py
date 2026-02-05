"""
Vibe Check Mode - Quick content pack testing without scenario setup.

This mode lets you test how your ingested content affects gameplay:
1. Give a scene prompt ("murder mystery at Cult of Ecstasy nightclub")
2. See how the narrator uses your lore
3. Multiple exchanges to test flow
4. All logged normally for review

Uses the production Orchestrator.run_turn() for realistic testing.
"""

import sys
from pathlib import Path
from typing import Optional

from src.config import check_auth_or_prompt
from src.content.chunker import Chunker
from src.content.indexer import LoreIndexer
from src.content.pack_loader import PackLoader
from src.content.retriever import LoreRetriever
from src.content.scene_cache import SceneLoreCacheManager
from src.content.session_manager import SessionManager
from src.content.vector_store import create_vector_store
from src.core.orchestrator import Orchestrator
from src.db.state_store import StateStore
from src.llm.gateway import ClaudeGateway
from src.llm.prompt_registry import PromptRegistry


def _format_lore_panel(scene_cache, campaign_id: str, scene_id: str) -> str:
    """Format retrieved lore as a readable panel."""
    if not scene_cache:
        return ""

    lore = scene_cache.get(campaign_id, scene_id)
    if not lore:
        return ""

    lines = ["─── lore retrieved ───"]

    total_tokens = 0
    chunk_count = 0

    # Location lore
    location_chunks = lore.get("location_chunks", [])
    for chunk in location_chunks:
        chunk_type = chunk.get("type", "lore")
        title = chunk.get("title", "Untitled")
        tokens = chunk.get("token_count", len(chunk.get("content", "")) // 4)
        lines.append(f"  [{chunk_type}] {title} ({tokens} tokens)")
        total_tokens += tokens
        chunk_count += 1

    # Thread lore
    thread_chunks = lore.get("thread_chunks", [])
    for chunk in thread_chunks:
        chunk_type = chunk.get("type", "lore")
        title = chunk.get("title", "Untitled")
        tokens = chunk.get("token_count", len(chunk.get("content", "")) // 4)
        lines.append(f"  [{chunk_type}] {title} ({tokens} tokens)")
        total_tokens += tokens
        chunk_count += 1

    # NPC briefings
    npc_briefings = lore.get("npc_briefings", {})
    for npc_id, briefing in npc_briefings.items():
        chunks = briefing.get("chunks", [])
        for chunk in chunks:
            chunk_type = chunk.get("type", "npc")
            title = chunk.get("title", npc_id)
            tokens = chunk.get("token_count", len(chunk.get("content", "")) // 4)
            lines.append(f"  [{chunk_type}] {title} ({tokens} tokens)")
            total_tokens += tokens
            chunk_count += 1

    if chunk_count > 0:
        lines.append(f"  Total: {total_tokens} tokens from {chunk_count} chunks")
    else:
        lines.append("  (no lore chunks retrieved)")

    lines.append("──────────────────────")
    return "\n".join(lines)


def vibe_check_cmd(args):
    """Run vibe check mode for content pack testing."""
    from src.cli.spinner import Spinner

    pack_path = Path(args.pack)
    if not pack_path.exists():
        print(f"Error: Pack not found at {pack_path}")
        sys.exit(1)

    # Check for API key
    api_key = check_auth_or_prompt()
    if not api_key:
        print("\n  Cannot run vibe-check without an API key.")
        print("  Run 'login' to set one up, or set ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)

    # Setup database (in-memory by default for isolation)
    db_path = getattr(args, "db", ":memory:")
    if db_path == "game.db":
        # Override default - vibe-check uses :memory: unless explicitly set
        db_path = ":memory:"

    print(f"\n{'='*60}")
    print("Vibe Check Mode - Content Pack Testing")
    print(f"{'='*60}")
    print(f"Pack: {pack_path}")
    print(f"Database: {db_path}")
    print()

    # Initialize database
    store = StateStore(db_path)
    store.ensure_schema()

    # Load and install the content pack
    print("Loading content pack...")
    loader = PackLoader()
    chunker = Chunker()
    vector_store = create_vector_store()
    indexer = LoreIndexer(store, vector_store)

    try:
        manifest, files = loader.load_pack(pack_path)
    except ValueError as e:
        print(f"Error loading pack: {e}")
        sys.exit(1)

    chunks = chunker.chunk_files(files, manifest.id)
    stats = indexer.index_pack(manifest, chunks)

    print(f"  Installed: {manifest.name} v{manifest.version}")
    print(f"  Chunks indexed: {stats.chunks_indexed}")
    print()

    # Create minimal bootstrap state
    campaign_id = "vibe_check"

    # Create campaign
    store.create_campaign(
        campaign_id=campaign_id,
        name="Vibe Check Session",
        pack_ids=[manifest.id]
    )

    # Create minimal player entity
    store.create_entity(
        entity_id="player",
        entity_type="pc",
        name="Protagonist",
        attrs={"description": "The protagonist"},
        tags=["pc", "player"]
    )

    # Create placeholder scene
    store.create_entity(
        entity_id="vibe_check_scene",
        entity_type="location",
        name="Vibe Check Scene",
        attrs={"description": "A scene for testing content pack vibes"},
        tags=["location"]
    )

    store.set_scene(
        location_id="vibe_check_scene",
        present_entity_ids=["player"],
        time={"hour": 20, "minute": 0, "period": "night"}
    )

    # Setup LLM and orchestrator
    prompts_dir = Path(__file__).parent.parent / "prompts"
    prompt_registry = PromptRegistry(prompts_dir)
    gateway = ClaudeGateway(api_key=api_key)

    # Setup content pack components
    lore_retriever = LoreRetriever(store, vector_store, entity_manifest={})
    scene_cache = SceneLoreCacheManager(store)
    session_mgr = SessionManager(store)
    active_session = session_mgr.start_session(campaign_id)

    # Verbose mode (on by default for vibe-check)
    verbose = getattr(args, "verbose", True)

    # Spinner reference for stage updates
    active_spinner = [None]

    def on_stage(stage_name: str):
        if active_spinner[0]:
            active_spinner[0].update(stage_name)

    orchestrator = Orchestrator(
        state_store=store,
        llm_gateway=gateway,
        prompt_registry=prompt_registry,
        on_stage=on_stage,
        lore_retriever=lore_retriever,
        scene_cache=scene_cache,
        session_manager=session_mgr,
        pack_ids=[manifest.id]
    )

    print("Ready! Give a scene prompt to start.")
    print("Example: 'Set a scene in a Cult of Ecstasy nightclub where someone just died'")
    print()
    print("Commands: /lore (show retrieved lore), /quit (exit)")
    print()

    # Track current scene for lore display
    current_scene_id = "vibe_check_scene"
    is_first_turn = True

    while True:
        try:
            if is_first_turn:
                prompt_text = "Scene prompt"
            else:
                prompt_text = ">"

            user_input = input(f"{prompt_text}: ").strip()
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

        if user_input.lower() == '/lore':
            lore_panel = _format_lore_panel(scene_cache, campaign_id, current_scene_id)
            if lore_panel:
                print(lore_panel)
            else:
                print("No lore retrieved yet.")
            continue

        if user_input.lower() == '/verbose':
            verbose = not verbose
            print(f"Verbose mode: {'on' if verbose else 'off'}")
            continue

        # Run turn through production orchestrator
        try:
            spinner = Spinner("Thinking")
            active_spinner[0] = spinner

            with spinner:
                result = orchestrator.run_turn(campaign_id, user_input)

            active_spinner[0] = None
            is_first_turn = False

            print(f"\n{result.final_text}\n")

            # Update current scene for lore tracking
            scene = store.get_scene()
            if scene:
                current_scene_id = scene.get("location_id", current_scene_id)

            # Show lore panel in verbose mode
            if verbose:
                lore_panel = _format_lore_panel(scene_cache, campaign_id, current_scene_id)
                if lore_panel:
                    print(lore_panel)
                    print()

        except Exception as e:
            active_spinner[0] = None
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
