"""Tests for state snapshot and sandbox replay functionality."""

import pytest
import tempfile
from pathlib import Path

from src.db.state_store import StateStore
from src.eval.snapshots import (
    StateSnapshot,
    SnapshotManager,
    SandboxEnvironment,
    create_snapshot_before_turn,
    run_turn_in_sandbox,
    compare_turn_outputs,
)


@pytest.fixture
def state_store():
    """Create a temporary state store."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = StateStore(db_path)
    store.ensure_schema()
    return store


@pytest.fixture
def populated_store(state_store):
    """State store with sample data."""
    # Create campaign
    state_store.create_campaign(
        campaign_id="test_campaign",
        name="Test Campaign",
        calibration={"tone": {"gritty_vs_cinematic": 0.7}},
    )

    # Create entities
    state_store.create_entity(
        entity_id="player",
        entity_type="player",
        name="Test Player",
        attrs={},
        tags=[],
    )
    state_store.create_entity(
        entity_id="npc_1",
        entity_type="npc",
        name="Viktor",
        attrs={"role": "fixer"},
        tags=["ally"],
    )

    # Create clocks
    state_store.create_clock(
        clock_id="clock_heat",
        name="Heat",
        value=0,
        max_value=6,
        triggers=[],
        tags=[],
    )
    state_store.create_clock(
        clock_id="clock_time",
        name="Time",
        value=12,
        max_value=12,
        triggers=[],
        tags=[],
    )

    # Create scene (use 'current' as the standard scene ID)
    state_store.set_scene(
        location_id="bar",
        present_entity_ids=["player", "npc_1"],
        time={"hour": 20},
        constraints=[],
        scene_id="current",
    )

    # Create a fact
    state_store.create_fact(
        fact_id="fact_1",
        subject_id="npc_1",
        predicate="has_job",
        obj={"type": "retrieval"},
        visibility="known",
        confidence=1.0,
        tags=[],
    )

    return state_store


class TestStateSnapshot:
    """Tests for StateSnapshot dataclass."""

    def test_snapshot_to_dict(self):
        """Snapshot converts to dict properly."""
        snapshot = StateSnapshot(
            snapshot_id="snap_1",
            campaign_id="camp_1",
            turn_no=5,
            created_at="2024-01-01T00:00:00",
            entities=[{"id": "e1", "name": "Test"}],
            clocks=[{"id": "c1", "value": 3}],
        )

        d = snapshot.to_dict()

        assert d["snapshot_id"] == "snap_1"
        assert d["turn_no"] == 5
        assert len(d["state"]["entities"]) == 1
        assert len(d["state"]["clocks"]) == 1

    def test_snapshot_from_dict(self):
        """Snapshot can be reconstructed from dict."""
        data = {
            "snapshot_id": "snap_2",
            "campaign_id": "camp_2",
            "turn_no": 10,
            "created_at": "2024-01-02T00:00:00",
            "state": {
                "entities": [{"id": "e2"}],
                "facts": [{"id": "f1"}],
                "clocks": [],
                "scene": {"id": "s1"},
                "threads": [],
                "inventory": [],
                "relationships": [],
                "campaign": {},
            }
        }

        snapshot = StateSnapshot.from_dict(data)

        assert snapshot.snapshot_id == "snap_2"
        assert snapshot.turn_no == 10
        assert len(snapshot.entities) == 1
        assert len(snapshot.facts) == 1


class TestSnapshotManager:
    """Tests for SnapshotManager."""

    def test_capture_snapshot(self, populated_store):
        """Can capture current state."""
        manager = SnapshotManager(populated_store)

        snapshot = manager.capture_snapshot("test_campaign")

        assert snapshot.campaign_id == "test_campaign"
        assert len(snapshot.entities) == 2
        assert len(snapshot.clocks) == 2
        assert snapshot.scene.get("id") == "current"
        assert len(snapshot.facts) == 1

    def test_save_and_load_snapshot(self, populated_store):
        """Can save and reload a snapshot."""
        manager = SnapshotManager(populated_store)

        # Capture and save
        original = manager.capture_snapshot("test_campaign", turn_no=3)
        manager.save_snapshot(original)

        # Load
        loaded = manager.load_snapshot(original.snapshot_id)

        assert loaded is not None
        assert loaded.snapshot_id == original.snapshot_id
        assert loaded.turn_no == 3
        assert len(loaded.entities) == len(original.entities)

    def test_list_snapshots(self, populated_store):
        """Can list all snapshots for a campaign."""
        manager = SnapshotManager(populated_store)

        # Create multiple snapshots
        snap1 = manager.capture_snapshot("test_campaign", turn_no=1)
        manager.save_snapshot(snap1)
        snap2 = manager.capture_snapshot("test_campaign", turn_no=2)
        manager.save_snapshot(snap2)

        # List
        snapshots = manager.list_snapshots("test_campaign")

        assert len(snapshots) == 2
        assert snapshots[0]["turn_no"] == 1
        assert snapshots[1]["turn_no"] == 2

    def test_get_snapshot_for_turn(self, populated_store):
        """Can get snapshot at or before a specific turn."""
        manager = SnapshotManager(populated_store)

        # Save snapshot at turn 3
        snap = manager.capture_snapshot("test_campaign", turn_no=3)
        manager.save_snapshot(snap)

        # Get snapshot for turn 5 (should return turn 3 snapshot)
        result = manager.get_snapshot_for_turn("test_campaign", 5)

        assert result is not None
        assert result.turn_no == 3


class TestSandboxEnvironment:
    """Tests for sandbox isolation."""

    def test_sandbox_creates_isolated_db(self, populated_store):
        """Sandbox creates a separate database."""
        manager = SnapshotManager(populated_store)
        snapshot = manager.capture_snapshot("test_campaign")

        with SandboxEnvironment(populated_store, snapshot) as sandbox_store:
            # Sandbox should have its own database
            assert sandbox_store.db_path != populated_store.db_path

            # Data should be restored
            player = sandbox_store.get_entity("player")
            assert player is not None
            assert player["name"] == "Test Player"

    def test_sandbox_changes_dont_affect_source(self, populated_store):
        """Changes in sandbox don't affect original store."""
        manager = SnapshotManager(populated_store)
        snapshot = manager.capture_snapshot("test_campaign")

        original_heat = populated_store.get_clock_by_name("Heat")["value"]

        with SandboxEnvironment(populated_store, snapshot) as sandbox_store:
            # Modify clock in sandbox
            sandbox_store.adjust_clock("Heat", 3)
            sandbox_heat = sandbox_store.get_clock_by_name("Heat")["value"]
            assert sandbox_heat == original_heat + 3

        # Original should be unchanged
        final_heat = populated_store.get_clock_by_name("Heat")["value"]
        assert final_heat == original_heat

    def test_sandbox_restores_scene(self, populated_store):
        """Sandbox correctly restores scene data."""
        manager = SnapshotManager(populated_store)
        snapshot = manager.capture_snapshot("test_campaign")

        with SandboxEnvironment(populated_store, snapshot) as sandbox_store:
            scene = sandbox_store.get_scene()
            assert scene is not None
            assert scene["location_id"] == "bar"
            assert "player" in scene["present_entity_ids"]

    def test_sandbox_restores_clocks(self, populated_store):
        """Sandbox correctly restores clock values."""
        manager = SnapshotManager(populated_store)
        snapshot = manager.capture_snapshot("test_campaign")

        with SandboxEnvironment(populated_store, snapshot) as sandbox_store:
            clocks = sandbox_store.get_all_clocks()
            clock_names = {c["name"] for c in clocks}
            assert "Heat" in clock_names
            assert "Time" in clock_names


class TestReplayFunctions:
    """Tests for replay convenience functions."""

    def test_create_snapshot_before_turn(self, populated_store):
        """create_snapshot_before_turn returns a valid snapshot."""
        snapshot = create_snapshot_before_turn(
            populated_store, "test_campaign", turn_no=1
        )

        assert snapshot is not None
        assert snapshot.campaign_id == "test_campaign"

    def test_run_turn_in_sandbox(self, populated_store):
        """Can run a turn in sandbox environment."""
        manager = SnapshotManager(populated_store)
        snapshot = manager.capture_snapshot("test_campaign")

        result = run_turn_in_sandbox(
            populated_store,
            snapshot,
            player_input="I look around",
            prompt_versions={"narrator": "v0"},
        )

        assert "final_text" in result
        assert result.get("turn_no") is not None


class TestCompareOutputs:
    """Tests for A/B comparison functionality."""

    def test_compare_requires_event(self, populated_store):
        """compare_turn_outputs handles missing event."""
        result = compare_turn_outputs(
            populated_store,
            "test_campaign",
            turn_no=99,  # Non-existent
            variant_a_versions={"narrator": "v0"},
            variant_b_versions={"narrator": "v1"},
        )

        assert "error" in result

    def test_compare_with_event(self, populated_store):
        """compare_turn_outputs works with existing event."""
        # First, create an event
        from src.db.state_store import new_event_id, json_dumps

        populated_store.append_event({
            "id": new_event_id(),
            "campaign_id": "test_campaign",
            "turn_no": 1,
            "player_input": "I examine Viktor",
            "context_packet_json": "{}",
            "pass_outputs_json": "{}",
            "engine_events_json": "[]",
            "state_diff_json": "{}",
            "final_text": "Viktor nods at you.",
            "prompt_versions_json": "{}",
        })

        result = compare_turn_outputs(
            populated_store,
            "test_campaign",
            turn_no=1,
            variant_a_versions={"narrator": "v0"},
            variant_b_versions={"narrator": "v0"},
        )

        assert "variant_a" in result
        assert "variant_b" in result
        assert result["player_input"] == "I examine Viktor"
