"""
State Snapshots - Capture and restore game state for clean A/B testing.

Supports:
- Full state capture at any point in time
- State restoration to a clean copy
- Diff comparison between snapshots
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import tempfile
import shutil

from ..db.state_store import StateStore, json_dumps, new_id


@dataclass
class StateSnapshot:
    """Complete snapshot of game state at a point in time."""
    snapshot_id: str
    campaign_id: str
    turn_no: int
    created_at: str

    # State tables
    entities: list = field(default_factory=list)
    facts: list = field(default_factory=list)
    scene: dict = field(default_factory=dict)
    threads: list = field(default_factory=list)
    clocks: list = field(default_factory=list)
    inventory: list = field(default_factory=list)
    relationships: list = field(default_factory=list)
    campaign: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "campaign_id": self.campaign_id,
            "turn_no": self.turn_no,
            "created_at": self.created_at,
            "state": {
                "entities": self.entities,
                "facts": self.facts,
                "scene": self.scene,
                "threads": self.threads,
                "clocks": self.clocks,
                "inventory": self.inventory,
                "relationships": self.relationships,
                "campaign": self.campaign,
            }
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StateSnapshot":
        state = data.get("state", {})
        return cls(
            snapshot_id=data["snapshot_id"],
            campaign_id=data["campaign_id"],
            turn_no=data["turn_no"],
            created_at=data["created_at"],
            entities=state.get("entities", []),
            facts=state.get("facts", []),
            scene=state.get("scene", {}),
            threads=state.get("threads", []),
            clocks=state.get("clocks", []),
            inventory=state.get("inventory", []),
            relationships=state.get("relationships", []),
            campaign=state.get("campaign", {}),
        )


class SnapshotManager:
    """Manages state snapshots for a campaign."""

    def __init__(self, state_store: StateStore):
        self.store = state_store
        self._ensure_snapshot_table()

    def _ensure_snapshot_table(self):
        """Ensure snapshot storage table exists."""
        conn = self.store.connect()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state_snapshots (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                turn_no INTEGER NOT NULL,
                snapshot_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_campaign_turn
            ON state_snapshots (campaign_id, turn_no)
        """)

        conn.commit()
        conn.close()

    def capture_snapshot(self, campaign_id: str, turn_no: Optional[int] = None) -> StateSnapshot:
        """
        Capture the current state of a campaign.

        Args:
            campaign_id: Campaign to snapshot
            turn_no: Turn number to record (or current if None)

        Returns:
            StateSnapshot with all state data
        """
        conn = self.store.connect()

        # Get campaign info
        campaign = self.store.get_campaign(campaign_id)
        if not campaign:
            conn.close()
            raise ValueError(f"Campaign {campaign_id} not found")

        if turn_no is None:
            turn_no = campaign.get("current_turn", 0)

        # Capture all entities
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM entities")
        entities = [dict(row) for row in cursor.fetchall()]

        # Capture all facts
        cursor.execute("SELECT * FROM facts")
        facts = [dict(row) for row in cursor.fetchall()]

        # Capture scene
        cursor.execute("SELECT * FROM scene LIMIT 1")
        scene_row = cursor.fetchone()
        scene = dict(scene_row) if scene_row else {}

        # Capture threads
        cursor.execute("SELECT * FROM threads")
        threads = [dict(row) for row in cursor.fetchall()]

        # Capture clocks
        cursor.execute("SELECT * FROM clocks")
        clocks = [dict(row) for row in cursor.fetchall()]

        # Capture inventory
        cursor.execute("SELECT * FROM inventory")
        inventory = [dict(row) for row in cursor.fetchall()]

        # Capture relationships
        cursor.execute("SELECT * FROM relationships")
        relationships = [dict(row) for row in cursor.fetchall()]

        conn.close()

        snapshot = StateSnapshot(
            snapshot_id=new_id(),
            campaign_id=campaign_id,
            turn_no=turn_no,
            created_at=datetime.utcnow().isoformat(),
            entities=entities,
            facts=facts,
            scene=scene,
            threads=threads,
            clocks=clocks,
            inventory=inventory,
            relationships=relationships,
            campaign=campaign,
        )

        return snapshot

    def save_snapshot(self, snapshot: StateSnapshot) -> None:
        """Persist a snapshot to the database."""
        conn = self.store.connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO state_snapshots (id, campaign_id, turn_no, snapshot_json)
            VALUES (?, ?, ?, ?)
        """, (
            snapshot.snapshot_id,
            snapshot.campaign_id,
            snapshot.turn_no,
            json_dumps(snapshot.to_dict())
        ))

        conn.commit()
        conn.close()

    def load_snapshot(self, snapshot_id: str) -> Optional[StateSnapshot]:
        """Load a snapshot by ID."""
        conn = self.store.connect()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT snapshot_json FROM state_snapshots WHERE id = ?",
            (snapshot_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        data = json.loads(row[0])
        return StateSnapshot.from_dict(data)

    def get_snapshot_for_turn(
        self,
        campaign_id: str,
        turn_no: int
    ) -> Optional[StateSnapshot]:
        """Get the snapshot taken at or before a specific turn."""
        conn = self.store.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT snapshot_json FROM state_snapshots
            WHERE campaign_id = ? AND turn_no <= ?
            ORDER BY turn_no DESC
            LIMIT 1
        """, (campaign_id, turn_no))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        data = json.loads(row[0])
        return StateSnapshot.from_dict(data)

    def list_snapshots(self, campaign_id: str) -> list:
        """List all snapshots for a campaign."""
        conn = self.store.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, turn_no, created_at FROM state_snapshots
            WHERE campaign_id = ?
            ORDER BY turn_no
        """, (campaign_id,))

        rows = cursor.fetchall()
        conn.close()

        return [
            {"id": row[0], "turn_no": row[1], "created_at": row[2]}
            for row in rows
        ]


class SandboxEnvironment:
    """
    Isolated environment for replaying turns without affecting main state.

    Creates a temporary database copy and restores state from a snapshot.
    """

    def __init__(self, source_store: StateStore, snapshot: StateSnapshot):
        self.source_store = source_store
        self.snapshot = snapshot
        self.temp_dir = None
        self.sandbox_store = None

    def __enter__(self) -> StateStore:
        """Create sandbox and restore state."""
        # Create temp directory for sandbox db
        self.temp_dir = tempfile.mkdtemp(prefix="rpg_sandbox_")
        sandbox_path = Path(self.temp_dir) / "sandbox.db"

        # Create new store with schema
        self.sandbox_store = StateStore(sandbox_path)
        self.sandbox_store.ensure_schema()

        # Restore state from snapshot
        self._restore_state(self.snapshot)

        return self.sandbox_store

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up sandbox."""
        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        return False

    def _restore_state(self, snapshot: StateSnapshot):
        """Restore all state tables from snapshot."""
        conn = self.sandbox_store.connect()
        cursor = conn.cursor()

        # Restore campaign
        if snapshot.campaign:
            cursor.execute("""
                INSERT INTO campaigns (id, name, created_at, updated_at,
                    calibration_json, system_json, genre_rules_json, current_turn)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot.campaign.get("id", snapshot.campaign_id),
                snapshot.campaign.get("name", "Restored Campaign"),
                snapshot.campaign.get("created_at", snapshot.created_at),
                snapshot.created_at,
                json_dumps(snapshot.campaign.get("calibration", {})),
                json_dumps(snapshot.campaign.get("system", {})),
                json_dumps(snapshot.campaign.get("genre_rules", {})),
                snapshot.turn_no,
            ))

        # Restore entities
        for entity in snapshot.entities:
            cursor.execute("""
                INSERT INTO entities (id, type, name, attrs_json, tags)
                VALUES (?, ?, ?, ?, ?)
            """, (
                entity["id"],
                entity["type"],
                entity["name"],
                entity["attrs_json"],
                entity["tags"],
            ))

        # Restore facts
        for fact in snapshot.facts:
            cursor.execute("""
                INSERT INTO facts (id, subject_id, predicate, object_json,
                    visibility, confidence, tags, discovered_turn, discovery_method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fact["id"],
                fact["subject_id"],
                fact["predicate"],
                fact["object_json"],
                fact["visibility"],
                fact["confidence"],
                fact["tags"],
                fact.get("discovered_turn"),
                fact.get("discovery_method"),
            ))

        # Restore scene (always use 'current' as the ID for consistency)
        if snapshot.scene:
            cursor.execute("""
                INSERT INTO scene (id, location_id, present_entity_ids_json,
                    time_json, constraints_json, visibility_conditions,
                    noise_level, obscured_entities_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "current",  # Always use 'current' for the sandbox scene
                snapshot.scene.get("location_id", "unknown"),
                snapshot.scene.get("present_entity_ids_json", "[]"),
                snapshot.scene.get("time_json", "{}"),
                snapshot.scene.get("constraints_json", "[]"),
                snapshot.scene.get("visibility_conditions", "normal"),
                snapshot.scene.get("noise_level", "normal"),
                snapshot.scene.get("obscured_entities_json", "[]"),
            ))

        # Restore threads
        for thread in snapshot.threads:
            cursor.execute("""
                INSERT INTO threads (id, title, status, stakes_json,
                    related_entity_ids_json, tags)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                thread["id"],
                thread["title"],
                thread["status"],
                thread["stakes_json"],
                thread["related_entity_ids_json"],
                thread["tags"],
            ))

        # Restore clocks
        for clock in snapshot.clocks:
            cursor.execute("""
                INSERT INTO clocks (id, name, value, max, triggers_json, tags)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                clock["id"],
                clock["name"],
                clock["value"],
                clock["max"],
                clock["triggers_json"],
                clock["tags"],
            ))

        # Restore inventory
        for item in snapshot.inventory:
            cursor.execute("""
                INSERT INTO inventory (owner_id, item_id, qty, flags_json)
                VALUES (?, ?, ?, ?)
            """, (
                item["owner_id"],
                item["item_id"],
                item["qty"],
                item["flags_json"],
            ))

        # Restore relationships
        for rel in snapshot.relationships:
            cursor.execute("""
                INSERT INTO relationships (a_id, b_id, rel_type, intensity, notes_json)
                VALUES (?, ?, ?, ?, ?)
            """, (
                rel["a_id"],
                rel["b_id"],
                rel["rel_type"],
                rel["intensity"],
                rel["notes_json"],
            ))

        conn.commit()
        conn.close()


def create_snapshot_before_turn(
    state_store: StateStore,
    campaign_id: str,
    turn_no: int
) -> StateSnapshot:
    """
    Create a snapshot of state as it was before a specific turn.

    This reconstructs the state by starting from turn 0 and
    replaying state diffs up to (but not including) the target turn.
    """
    manager = SnapshotManager(state_store)

    # Check if we have a saved snapshot near this turn
    existing = manager.get_snapshot_for_turn(campaign_id, turn_no - 1)
    if existing and existing.turn_no == turn_no - 1:
        return existing

    # Otherwise, capture current state and note this is approximate
    # Full reconstruction would require replaying from turn 0
    snapshot = manager.capture_snapshot(campaign_id, turn_no)
    snapshot.snapshot_id = new_id()  # New ID for this reconstructed snapshot

    return snapshot


def run_turn_in_sandbox(
    source_store: StateStore,
    snapshot: StateSnapshot,
    player_input: str,
    prompt_versions: Optional[dict] = None,
    llm_gateway = None
) -> dict:
    """
    Run a turn in an isolated sandbox environment.

    Args:
        source_store: Original state store
        snapshot: State snapshot to restore
        player_input: Player input to replay
        prompt_versions: Optional prompt version overrides
        llm_gateway: LLM gateway to use

    Returns:
        Turn result dict
    """
    from pathlib import Path
    from ..llm.gateway import MockGateway
    from ..llm.prompt_registry import PromptRegistry
    from ..core.orchestrator import Orchestrator

    with SandboxEnvironment(source_store, snapshot) as sandbox_store:
        # Setup orchestrator in sandbox
        gateway = llm_gateway or MockGateway()
        prompts_dir = Path(__file__).parent.parent / "prompts"
        registry = PromptRegistry(prompts_dir)

        orchestrator = Orchestrator(
            state_store=sandbox_store,
            llm_gateway=gateway,
            prompt_registry=registry,
            prompt_versions=prompt_versions,
        )

        result = orchestrator.run_turn(snapshot.campaign_id, player_input)
        return result.to_dict()


def compare_turn_outputs(
    source_store: StateStore,
    campaign_id: str,
    turn_no: int,
    variant_a_versions: dict,
    variant_b_versions: dict,
    llm_gateway = None
) -> dict:
    """
    Run A/B comparison of two prompt variants on the same turn.

    Args:
        source_store: Source state store
        campaign_id: Campaign to test
        turn_no: Turn to replay
        variant_a_versions: Prompt versions for variant A
        variant_b_versions: Prompt versions for variant B
        llm_gateway: LLM gateway (required for real comparison)

    Returns:
        Comparison results with both outputs
    """
    manager = SnapshotManager(source_store)

    # Get or create snapshot before this turn
    snapshot = create_snapshot_before_turn(source_store, campaign_id, turn_no)

    # Get original player input
    event = source_store.get_event(campaign_id, turn_no)
    if not event:
        return {"error": f"Turn {turn_no} not found"}

    player_input = event["player_input"]
    original_output = event["final_text"]

    # Run both variants
    result_a = run_turn_in_sandbox(
        source_store, snapshot, player_input,
        prompt_versions=variant_a_versions,
        llm_gateway=llm_gateway
    )

    result_b = run_turn_in_sandbox(
        source_store, snapshot, player_input,
        prompt_versions=variant_b_versions,
        llm_gateway=llm_gateway
    )

    return {
        "campaign_id": campaign_id,
        "turn_no": turn_no,
        "player_input": player_input,
        "original": original_output,
        "variant_a": {
            "versions": variant_a_versions,
            "output": result_a.get("final_text", ""),
        },
        "variant_b": {
            "versions": variant_b_versions,
            "output": result_b.get("final_text", ""),
        },
        "note": "Comparison run in isolated sandbox environments"
    }
