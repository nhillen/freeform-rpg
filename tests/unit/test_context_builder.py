"""
Tests for the Context Builder.

Tests context packet construction and perception filtering.
"""

import pytest
from src.context.builder import ContextBuilder, ContextOptions
from tests.fixtures.state import setup_minimal_game_state, setup_investigation_state


class TestContextBuilding:
    """Tests for basic context packet construction."""

    def test_build_context_minimal(self, state_store):
        """Can build context from minimal state."""
        setup_minimal_game_state(state_store, "test_campaign")
        builder = ContextBuilder(state_store)

        context = builder.build_context("test_campaign", "test input")

        assert "scene" in context
        assert "present_entities" in context
        assert "entities" in context
        assert "clocks" in context
        assert "calibration" in context

    def test_build_context_includes_scene(self, state_store):
        """Context includes current scene information."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        context = builder.build_context("test_campaign", "test")

        assert context["scene"]["location_id"] == "test_location"
        assert "time" in context["scene"]

    def test_build_context_includes_present_entities(self, state_store):
        """Context includes entities present in scene."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        context = builder.build_context("test_campaign", "test")

        assert "player" in context["present_entities"]
        assert "test_npc" in context["present_entities"]

    def test_build_context_includes_clocks(self, state_store):
        """Context includes all clocks."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        context = builder.build_context("test_campaign", "test")

        clock_names = {c["name"] for c in context["clocks"]}
        assert "Heat" in clock_names
        assert "Time" in clock_names
        assert "Harm" in clock_names

    def test_build_context_includes_calibration(self, state_store):
        """Context includes calibration settings."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        context = builder.build_context("test_campaign", "test")

        assert "tone" in context["calibration"]
        assert "risk" in context["calibration"]

    def test_build_context_includes_active_threads(self, state_store):
        """Context includes active threads."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        context = builder.build_context("test_campaign", "test")

        assert len(context["threads"]) >= 1
        assert context["threads"][0]["status"] == "active"


class TestPerceptionFiltering:
    """Tests for perception-based filtering."""

    def test_only_known_facts_by_default(self, state_store):
        """By default, only known facts are included."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        context = builder.build_context("test_campaign", "test")

        # Should only have the known fact, not the hidden one
        visibilities = {f["visibility"] for f in context["facts"]}
        assert "world" not in visibilities

    def test_world_facts_with_option(self, state_store):
        """Can include world facts with option."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        options = ContextOptions(include_world_facts=True)
        context = builder.build_context("test_campaign", "test", options)

        # With the option, we might see world facts too
        # (depends on whether entities with world facts are present)
        assert "facts" in context

    def test_obscured_entities_filtered(self, state_store):
        """Obscured entities are filtered out by default."""
        setup_minimal_game_state(state_store)
        # Add an obscured entity to the scene
        state_store.create_entity("hidden", "npc", "Hidden NPC")
        state_store.set_scene(
            location_id="test_location",
            present_entity_ids=["player", "test_npc", "hidden"],
            obscured_entities=["hidden"]
        )

        builder = ContextBuilder(state_store)
        context = builder.build_context("test_campaign", "test")

        # Hidden entity should not be in visible list
        assert "hidden" not in context["present_entities"]

    def test_obscured_entities_with_option(self, state_store):
        """Can include obscured entities with option."""
        setup_minimal_game_state(state_store)
        state_store.create_entity("hidden", "npc", "Hidden NPC")
        state_store.set_scene(
            location_id="test_location",
            present_entity_ids=["player", "test_npc", "hidden"],
            obscured_entities=["hidden"]
        )

        builder = ContextBuilder(state_store)
        options = ContextOptions(include_obscured=True)
        context = builder.build_context("test_campaign", "test", options)

        # With option, hidden entity should be included
        assert "hidden" in context["present_entities"]


class TestEntityPerception:
    """Tests for the get_entity_perception method."""

    def test_perceivable_entity(self, state_store):
        """Entity in scene is perceivable."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        perception = builder.get_entity_perception("test_npc")

        assert perception["perceivable"] is True
        assert perception["clarity"] == "clear"
        assert perception["reason"] is None

    def test_obscured_entity(self, state_store):
        """Obscured entity is perceivable but not clear."""
        setup_minimal_game_state(state_store)
        state_store.create_entity("hidden", "npc", "Hidden NPC")
        state_store.set_scene(
            location_id="test_location",
            present_entity_ids=["player", "test_npc", "hidden"],
            obscured_entities=["hidden"]
        )

        builder = ContextBuilder(state_store)
        perception = builder.get_entity_perception("hidden")

        assert perception["perceivable"] is True
        assert perception["clarity"] == "obscured"

    def test_not_present_entity(self, state_store):
        """Entity not in scene is not perceivable."""
        setup_minimal_game_state(state_store)
        # Create entity but don't add to scene
        state_store.create_entity("elsewhere", "npc", "Elsewhere NPC")

        builder = ContextBuilder(state_store)
        perception = builder.get_entity_perception("elsewhere")

        assert perception["perceivable"] is False
        assert perception["reason"] == "not_present"

    def test_unknown_entity(self, state_store):
        """Entity that doesn't exist is not perceivable."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        perception = builder.get_entity_perception("nonexistent")

        assert perception["perceivable"] is False
        assert perception["reason"] == "not_known"


class TestNPCCapabilities:
    """Tests for NPC capability extraction in context."""

    def test_npc_capabilities_in_context(self, state_store):
        """Context includes NPC capabilities when NPCs have capability attrs."""
        setup_minimal_game_state(state_store, "test_campaign")
        # Update the test_npc with capability attrs
        state_store.update_entity("test_npc", attrs={
            "role": "contact",
            "description": "A helpful contact for testing",
            "threat_level": "low",
            "capabilities": ["information_brokering"],
            "equipment": ["commlink"],
            "limitations": ["non_combatant"]
        })

        builder = ContextBuilder(state_store)
        context = builder.build_context("test_campaign", "test")

        assert "npc_capabilities" in context
        assert len(context["npc_capabilities"]) == 1
        npc_cap = context["npc_capabilities"][0]
        assert npc_cap["entity_id"] == "test_npc"
        assert npc_cap["threat_level"] == "low"
        assert "information_brokering" in npc_cap["capabilities"]

    def test_no_capabilities_no_entry(self, state_store):
        """NPCs without capability attrs are not in npc_capabilities."""
        setup_minimal_game_state(state_store, "test_campaign")
        builder = ContextBuilder(state_store)
        context = builder.build_context("test_campaign", "test")

        assert "npc_capabilities" in context
        # Default test NPC has no capability attrs
        assert len(context["npc_capabilities"]) == 0


class TestActiveSituations:
    """Tests for active situations in context."""

    def test_active_situations_in_context(self, state_store):
        """Context includes active situation facts."""
        setup_minimal_game_state(state_store, "test_campaign")
        # Create a situation fact
        state_store.create_fact(
            fact_id="sit_exposed",
            subject_id="player",
            predicate="situation",
            obj={
                "condition": "exposed",
                "active": True,
                "source_action": "sneak",
                "severity": "soft",
                "clears_on": ["hide_success"],
                "narrative_hint": "Player is exposed"
            },
            visibility="known",
            tags=["situation", "active"]
        )

        builder = ContextBuilder(state_store)
        context = builder.build_context("test_campaign", "test")

        assert "active_situations" in context
        assert len(context["active_situations"]) == 1
        assert context["active_situations"][0]["condition"] == "exposed"

    def test_inactive_situation_excluded(self, state_store):
        """Inactive situation facts are not in context."""
        setup_minimal_game_state(state_store, "test_campaign")
        state_store.create_fact(
            fact_id="sit_cleared",
            subject_id="player",
            predicate="situation",
            obj={
                "condition": "exposed",
                "active": False,
                "source_action": "sneak",
                "severity": "soft",
                "clears_on": ["hide_success"],
                "narrative_hint": "Was exposed, now cleared"
            },
            visibility="known",
            tags=["situation"]
        )

        builder = ContextBuilder(state_store)
        context = builder.build_context("test_campaign", "test")

        assert "active_situations" in context
        assert len(context["active_situations"]) == 0

    def test_no_situations_empty_list(self, state_store):
        """No situation facts results in empty list."""
        setup_minimal_game_state(state_store, "test_campaign")
        builder = ContextBuilder(state_store)
        context = builder.build_context("test_campaign", "test")

        assert "active_situations" in context
        assert len(context["active_situations"]) == 0


class TestFailureStreakContext:
    """Tests for failure streak computation in context."""

    def test_failure_streak_in_context(self, state_store):
        """Context includes failure_streak field."""
        setup_minimal_game_state(state_store, "test_campaign")
        builder = ContextBuilder(state_store)
        context = builder.build_context("test_campaign", "test")

        assert "failure_streak" in context
        assert context["failure_streak"]["count"] == 0
        assert context["failure_streak"]["actions"] == []

    def test_failure_streak_default_no_events(self, state_store):
        """Streak is 0 when there are no events."""
        setup_minimal_game_state(state_store, "test_campaign")
        builder = ContextBuilder(state_store)
        context = builder.build_context("test_campaign", "test")

        assert context["failure_streak"]["count"] == 0


class TestContextOptions:
    """Tests for context building options."""

    def test_max_entities_option(self, state_store):
        """Can limit number of entities in context."""
        setup_minimal_game_state(state_store)
        # Add more entities
        for i in range(10):
            state_store.create_entity(f"npc_{i}", "npc", f"NPC {i}")

        state_store.set_scene(
            location_id="test_location",
            present_entity_ids=["player"] + [f"npc_{i}" for i in range(10)]
        )

        builder = ContextBuilder(state_store)
        options = ContextOptions(max_entities=5)
        context = builder.build_context("test_campaign", "test", options)

        # Should respect the limit
        assert len(context["entities"]) <= 5

    def test_max_facts_option(self, state_store):
        """Can limit number of facts in context."""
        setup_minimal_game_state(state_store)
        # Add more facts
        for i in range(20):
            state_store.create_fact(
                f"fact_{i}", "player", "knows", f"fact {i}",
                visibility="known"
            )

        builder = ContextBuilder(state_store)
        options = ContextOptions(max_facts=10)
        context = builder.build_context("test_campaign", "test", options)

        assert len(context["facts"]) <= 10
