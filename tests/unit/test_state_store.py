"""
Tests for the StateStore class.

Tests all CRUD operations and state management functions.
"""

import pytest
from src.db.state_store import StateStore, new_id


class TestCampaignOperations:
    """Tests for campaign CRUD."""

    def test_create_campaign(self, state_store):
        """Can create a campaign with all fields."""
        campaign = state_store.create_campaign(
            campaign_id="test_campaign",
            name="Test Campaign",
            calibration={"tone": {"dark": 0.5}},
            system={"dice": "2d6"},
            genre_rules={"setting": "noir"}
        )

        assert campaign["id"] == "test_campaign"
        assert campaign["name"] == "Test Campaign"
        assert campaign["calibration"]["tone"]["dark"] == 0.5
        assert campaign["system"]["dice"] == "2d6"
        assert campaign["current_turn"] == 0

    def test_get_campaign(self, state_store):
        """Can retrieve a created campaign."""
        state_store.create_campaign("c1", "Campaign One")
        campaign = state_store.get_campaign("c1")

        assert campaign is not None
        assert campaign["name"] == "Campaign One"

    def test_get_nonexistent_campaign(self, state_store):
        """Returns None for nonexistent campaign."""
        assert state_store.get_campaign("nonexistent") is None

    def test_update_campaign(self, state_store):
        """Can update campaign fields."""
        state_store.create_campaign("c1", "Campaign One")
        state_store.update_campaign(
            "c1",
            calibration={"updated": True},
            current_turn=5
        )

        campaign = state_store.get_campaign("c1")
        assert campaign["calibration"]["updated"] is True
        assert campaign["current_turn"] == 5


class TestEntityOperations:
    """Tests for entity CRUD."""

    def test_create_entity(self, state_store):
        """Can create an entity."""
        entity = state_store.create_entity(
            entity_id="e1",
            entity_type="npc",
            name="Test NPC",
            attrs={"role": "villain"},
            tags=["hostile"]
        )

        assert entity["id"] == "e1"
        assert entity["type"] == "npc"
        assert entity["name"] == "Test NPC"
        assert entity["attrs"]["role"] == "villain"
        assert "hostile" in entity["tags"]

    def test_get_entity(self, state_store):
        """Can retrieve an entity."""
        state_store.create_entity("e1", "npc", "Test NPC")
        entity = state_store.get_entity("e1")

        assert entity is not None
        assert entity["name"] == "Test NPC"

    def test_get_entities_by_type(self, state_store):
        """Can get all entities of a type."""
        state_store.create_entity("npc1", "npc", "NPC One")
        state_store.create_entity("npc2", "npc", "NPC Two")
        state_store.create_entity("loc1", "location", "Location One")

        npcs = state_store.get_entities_by_type("npc")
        assert len(npcs) == 2

        locations = state_store.get_entities_by_type("location")
        assert len(locations) == 1

    def test_get_entities_by_ids(self, state_store):
        """Can get multiple entities by IDs."""
        state_store.create_entity("e1", "npc", "One")
        state_store.create_entity("e2", "npc", "Two")
        state_store.create_entity("e3", "npc", "Three")

        entities = state_store.get_entities_by_ids(["e1", "e3"])
        assert len(entities) == 2
        names = {e["name"] for e in entities}
        assert names == {"One", "Three"}

    def test_update_entity(self, state_store):
        """Can update entity fields."""
        state_store.create_entity("e1", "npc", "Old Name", attrs={"old": True})
        state_store.update_entity("e1", name="New Name", attrs={"new": True})

        entity = state_store.get_entity("e1")
        assert entity["name"] == "New Name"
        assert entity["attrs"]["new"] is True

    def test_delete_entity(self, state_store):
        """Can delete an entity."""
        state_store.create_entity("e1", "npc", "To Delete")
        state_store.delete_entity("e1")

        assert state_store.get_entity("e1") is None


class TestFactOperations:
    """Tests for fact CRUD."""

    def test_create_fact(self, state_store):
        """Can create a fact."""
        fact = state_store.create_fact(
            fact_id="f1",
            subject_id="npc1",
            predicate="status",
            obj="alive",
            visibility="known",
            confidence=1.0,
            tags=["status"]
        )

        assert fact["id"] == "f1"
        assert fact["subject_id"] == "npc1"
        assert fact["predicate"] == "status"
        assert fact["object"] == "alive"
        assert fact["visibility"] == "known"

    def test_get_facts_for_subject(self, state_store):
        """Can get all facts about a subject."""
        state_store.create_fact("f1", "npc1", "status", "alive")
        state_store.create_fact("f2", "npc1", "location", "bar")
        state_store.create_fact("f3", "npc2", "status", "dead")

        facts = state_store.get_facts_for_subject("npc1")
        assert len(facts) == 2

    def test_get_known_facts(self, state_store):
        """Can get only known facts."""
        state_store.create_fact("f1", "s1", "p1", "o1", visibility="known")
        state_store.create_fact("f2", "s2", "p2", "o2", visibility="world")
        state_store.create_fact("f3", "s3", "p3", "o3", visibility="known")

        known = state_store.get_known_facts()
        assert len(known) == 2

    def test_mark_fact_discovered(self, state_store):
        """Can mark a fact as discovered."""
        state_store.create_fact("f1", "s1", "p1", "o1", visibility="world")
        state_store.mark_fact_discovered("f1", turn_no=5, method="investigation")

        fact = state_store.get_fact("f1")
        assert fact["visibility"] == "known"
        assert fact["discovered_turn"] == 5
        assert fact["discovery_method"] == "investigation"


class TestClockOperations:
    """Tests for clock CRUD and triggers."""

    def test_create_clock(self, state_store):
        """Can create a clock."""
        clock = state_store.create_clock(
            clock_id="heat",
            name="Heat",
            value=2,
            max_value=8,
            triggers={"4": "Cops alerted", "8": "Raid"}
        )

        assert clock["id"] == "heat"
        assert clock["name"] == "Heat"
        assert clock["value"] == 2
        assert clock["max"] == 8
        assert "4" in clock["triggers"]

    def test_update_clock_value(self, state_store):
        """Can update clock value."""
        state_store.create_clock("heat", "Heat", 2, 8)
        state_store.update_clock("heat", value=5)

        clock = state_store.get_clock("heat")
        assert clock["value"] == 5

    def test_clock_value_clamped(self, state_store):
        """Clock value is clamped to valid range."""
        state_store.create_clock("heat", "Heat", 2, 8)

        state_store.update_clock("heat", value=100)
        clock = state_store.get_clock("heat")
        assert clock["value"] == 8  # Clamped to max

        state_store.update_clock("heat", value=-5)
        clock = state_store.get_clock("heat")
        assert clock["value"] == 0  # Clamped to min

    def test_adjust_clock(self, state_store):
        """Can adjust clock by delta."""
        state_store.create_clock("heat", "Heat", 2, 8)
        state_store.adjust_clock("heat", 3)

        clock = state_store.get_clock("heat")
        assert clock["value"] == 5

    def test_clock_triggers(self, state_store):
        """Triggers fire when threshold crossed."""
        state_store.create_clock(
            "heat", "Heat", 2, 8,
            triggers={"4": "Cops alerted", "6": "Active investigation"}
        )

        # Crossing threshold 4
        triggered = state_store.update_clock("heat", value=5)
        assert "Cops alerted" in triggered
        assert "Active investigation" not in triggered

    def test_clock_multiple_triggers(self, state_store):
        """Multiple triggers can fire at once."""
        state_store.create_clock(
            "heat", "Heat", 2, 8,
            triggers={"4": "Cops alerted", "6": "Active investigation"}
        )

        # Jump from 2 to 7, crossing both thresholds
        triggered = state_store.update_clock("heat", value=7)
        assert len(triggered) == 2
        assert "Cops alerted" in triggered
        assert "Active investigation" in triggered

    def test_get_clock_by_name(self, state_store):
        """Can get clock by name."""
        state_store.create_clock("c1", "Heat", 0, 8)
        clock = state_store.get_clock_by_name("Heat")
        assert clock["id"] == "c1"


class TestSceneOperations:
    """Tests for scene management."""

    def test_set_scene(self, state_store):
        """Can set the current scene."""
        scene = state_store.set_scene(
            location_id="bar",
            present_entity_ids=["player", "npc1"],
            time={"hour": 23},
            visibility_conditions="dim"
        )

        assert scene["location_id"] == "bar"
        assert "player" in scene["present_entity_ids"]
        assert scene["visibility_conditions"] == "dim"

    def test_get_scene(self, state_store):
        """Can get the current scene."""
        state_store.set_scene("bar", ["player"])
        scene = state_store.get_scene()

        assert scene is not None
        assert scene["location_id"] == "bar"

    def test_update_scene_entities(self, state_store):
        """Can update which entities are present."""
        state_store.set_scene("bar", ["player"])
        state_store.update_scene_entities(["player", "npc1", "npc2"])

        scene = state_store.get_scene()
        assert len(scene["present_entity_ids"]) == 3


class TestThreadOperations:
    """Tests for thread CRUD."""

    def test_create_thread(self, state_store):
        """Can create a thread."""
        thread = state_store.create_thread(
            thread_id="t1",
            title="Find the killer",
            status="active",
            stakes={"success": "Justice", "failure": "Escape"}
        )

        assert thread["id"] == "t1"
        assert thread["title"] == "Find the killer"
        assert thread["status"] == "active"

    def test_get_active_threads(self, state_store):
        """Can get only active threads."""
        state_store.create_thread("t1", "Active One", status="active")
        state_store.create_thread("t2", "Active Two", status="active")
        state_store.create_thread("t3", "Resolved", status="resolved")

        active = state_store.get_active_threads()
        assert len(active) == 2

    def test_update_thread_status(self, state_store):
        """Can update thread status."""
        state_store.create_thread("t1", "Test Thread", status="active")
        state_store.update_thread("t1", status="resolved")

        thread = state_store.get_thread("t1")
        assert thread["status"] == "resolved"


class TestInventoryOperations:
    """Tests for inventory management."""

    def test_add_inventory(self, state_store):
        """Can add items to inventory."""
        item = state_store.add_inventory("player", "knife", 1)

        assert item["owner_id"] == "player"
        assert item["item_id"] == "knife"
        assert item["qty"] == 1

    def test_add_inventory_stacks(self, state_store):
        """Adding same item increases quantity."""
        state_store.add_inventory("player", "ammo", 10)
        state_store.add_inventory("player", "ammo", 5)

        item = state_store.get_inventory_item("player", "ammo")
        assert item["qty"] == 15

    def test_get_inventory(self, state_store):
        """Can get all inventory for owner."""
        state_store.add_inventory("player", "knife", 1)
        state_store.add_inventory("player", "ammo", 10)
        state_store.add_inventory("npc", "gun", 1)

        player_inv = state_store.get_inventory("player")
        assert len(player_inv) == 2

    def test_remove_inventory(self, state_store):
        """Can remove items from inventory."""
        state_store.add_inventory("player", "ammo", 10)

        remains = state_store.remove_inventory("player", "ammo", 3)
        assert remains is True

        item = state_store.get_inventory_item("player", "ammo")
        assert item["qty"] == 7

    def test_remove_inventory_depletes(self, state_store):
        """Removing all items removes the entry."""
        state_store.add_inventory("player", "ammo", 5)

        remains = state_store.remove_inventory("player", "ammo", 5)
        assert remains is False

        item = state_store.get_inventory_item("player", "ammo")
        assert item is None


class TestRelationshipOperations:
    """Tests for relationship management."""

    def test_create_relationship(self, state_store):
        """Can create a relationship."""
        rel = state_store.create_relationship(
            a_id="player",
            b_id="npc1",
            rel_type="trust",
            intensity=2,
            notes={"history": "Saved their life"}
        )

        assert rel["a_id"] == "player"
        assert rel["b_id"] == "npc1"
        assert rel["rel_type"] == "trust"
        assert rel["intensity"] == 2

    def test_get_relationships_for_entity(self, state_store):
        """Can get all relationships for an entity."""
        state_store.create_relationship("player", "npc1", "trust", 2)
        state_store.create_relationship("player", "npc2", "fear", -1)
        state_store.create_relationship("npc3", "player", "owes", 1)

        rels = state_store.get_relationships_for_entity("player")
        assert len(rels) == 3

    def test_update_relationship_intensity(self, state_store):
        """Can adjust relationship intensity."""
        state_store.create_relationship("player", "npc1", "trust", 2)
        state_store.update_relationship_intensity("player", "npc1", "trust", 1)

        rel = state_store.get_relationship("player", "npc1", "trust")
        assert rel["intensity"] == 3


class TestStateDiff:
    """Tests for applying state diffs."""

    def test_apply_state_diff_clocks(self, state_store):
        """State diff can update clocks."""
        state_store.create_clock("heat", "Heat", 2, 8)
        state_store.create_clock("time", "Time", 8, 12)

        diff = {
            "clocks": [
                {"id": "heat", "delta": 2},
                {"id": "time", "delta": -1}
            ],
            "facts_add": [],
            "facts_update": [],
            "inventory_changes": [],
            "scene_update": {},
            "threads_update": []
        }

        state_store.apply_state_diff(diff, turn_no=1)

        heat = state_store.get_clock("heat")
        time = state_store.get_clock("time")
        assert heat["value"] == 4
        assert time["value"] == 7

    def test_apply_state_diff_facts(self, state_store):
        """State diff can add and update facts."""
        state_store.create_fact("f1", "npc1", "status", "unknown", visibility="world")

        diff = {
            "clocks": [],
            "facts_add": [
                {"subject_id": "npc2", "predicate": "location", "object": "bar", "visibility": "known"}
            ],
            "facts_update": [
                {"id": "f1", "object": "dead", "visibility": "known"}
            ],
            "inventory_changes": [],
            "scene_update": {},
            "threads_update": []
        }

        state_store.apply_state_diff(diff, turn_no=1)

        # Check new fact was added
        facts = state_store.get_facts_for_subject("npc2")
        assert len(facts) == 1
        assert facts[0]["object"] == "bar"

        # Check existing fact was updated
        f1 = state_store.get_fact("f1")
        assert f1["object"] == "dead"
        assert f1["visibility"] == "known"

    def test_apply_state_diff_inventory(self, state_store):
        """State diff can modify inventory."""
        state_store.add_inventory("player", "ammo", 10)

        diff = {
            "clocks": [],
            "facts_add": [],
            "facts_update": [],
            "inventory_changes": [
                {"owner_id": "player", "item_id": "ammo", "delta": -3},
                {"owner_id": "player", "item_id": "medkit", "delta": 1}
            ],
            "scene_update": {},
            "threads_update": []
        }

        state_store.apply_state_diff(diff, turn_no=1)

        ammo = state_store.get_inventory_item("player", "ammo")
        medkit = state_store.get_inventory_item("player", "medkit")
        assert ammo["qty"] == 7
        assert medkit["qty"] == 1

    def test_apply_state_diff_returns_triggers(self, state_store):
        """State diff returns triggered clock events."""
        state_store.create_clock("heat", "Heat", 3, 8, triggers={"4": "Alert!"})

        diff = {
            "clocks": [{"id": "heat", "delta": 2}],
            "facts_add": [],
            "facts_update": [],
            "inventory_changes": [],
            "scene_update": {},
            "threads_update": []
        }

        triggered = state_store.apply_state_diff(diff, turn_no=1)
        assert "Alert!" in triggered


class TestEventOperations:
    """Tests for event recording."""

    def test_append_and_get_event(self, state_store):
        """Can append and retrieve events."""
        event = {
            "id": new_id(),
            "campaign_id": "c1",
            "turn_no": 1,
            "player_input": "look around",
            "context_packet_json": "{}",
            "pass_outputs_json": "{}",
            "engine_events_json": "[]",
            "state_diff_json": "{}",
            "final_text": "You look around.",
            "prompt_versions_json": "{}"
        }

        state_store.append_event(event)
        retrieved = state_store.get_event("c1", 1)

        assert retrieved is not None
        assert retrieved["player_input"] == "look around"
        assert retrieved["final_text"] == "You look around."

    def test_get_events_range(self, state_store):
        """Can get a range of events."""
        for i in range(1, 6):
            state_store.append_event({
                "id": new_id(),
                "campaign_id": "c1",
                "turn_no": i,
                "player_input": f"turn {i}",
                "context_packet_json": "{}",
                "pass_outputs_json": "{}",
                "engine_events_json": "[]",
                "state_diff_json": "{}",
                "final_text": f"Turn {i} result",
                "prompt_versions_json": "{}"
            })

        events = state_store.get_events_range("c1", 2, 4)
        assert len(events) == 3
        assert events[0]["turn_no"] == 2
        assert events[-1]["turn_no"] == 4

    def test_get_next_turn_no(self, state_store):
        """Can determine next turn number."""
        assert state_store.get_next_turn_no("c1") == 1

        state_store.append_event({
            "id": new_id(),
            "campaign_id": "c1",
            "turn_no": 1,
            "player_input": "test",
            "context_packet_json": "{}",
            "pass_outputs_json": "{}",
            "engine_events_json": "[]",
            "state_diff_json": "{}",
            "final_text": "test",
            "prompt_versions_json": "{}"
        })

        assert state_store.get_next_turn_no("c1") == 2
