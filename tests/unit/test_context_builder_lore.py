"""
Tests for lore context integration in the Context Builder.

Verifies:
  - lore_context is empty dict when no cache is available
  - lore_context is populated when provided
  - lore_context is skipped when include_lore=False
"""

import pytest
from src.context.builder import ContextBuilder, ContextOptions
from tests.fixtures.state import setup_minimal_game_state


class TestLoreContextInPacket:
    """Tests for lore_context field in context packet."""

    def test_lore_context_empty_by_default(self, state_store):
        """Context packet has empty lore_context when no lore is provided."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        context = builder.build_context("test_campaign", "look around")

        assert "lore_context" in context
        assert context["lore_context"] == {}

    def test_lore_context_populated_when_provided(self, state_store):
        """Context packet includes lore_context when passed to build_context."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        lore = {
            "atmosphere": [
                {
                    "chunk_id": "test:loc:atmosphere",
                    "title": "Atmosphere",
                    "content": "The neon lights flicker in the rain.",
                    "entity_refs": ["neon_dragon"],
                }
            ],
            "npc_briefings": {
                "viktor": [
                    {
                        "chunk_id": "test:npc:background",
                        "title": "Background",
                        "content": "Viktor is a fixer with deep connections.",
                        "entity_refs": ["viktor"],
                    }
                ]
            },
            "discoverable": [],
            "thread_connections": [],
        }

        context = builder.build_context(
            "test_campaign", "look around", lore_context=lore
        )

        assert context["lore_context"] == lore
        assert len(context["lore_context"]["atmosphere"]) == 1
        assert "viktor" in context["lore_context"]["npc_briefings"]

    def test_lore_context_skipped_when_include_lore_false(self, state_store):
        """lore_context is empty when include_lore=False even if lore provided."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        lore = {
            "atmosphere": [{"chunk_id": "test", "title": "A", "content": "B", "entity_refs": []}],
            "npc_briefings": {},
            "discoverable": [],
            "thread_connections": [],
        }

        options = ContextOptions(include_lore=False)
        context = builder.build_context(
            "test_campaign", "look around", options, lore_context=lore
        )

        assert context["lore_context"] == {}

    def test_lore_context_included_when_include_lore_true(self, state_store):
        """lore_context is included when include_lore=True (the default)."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        lore = {
            "atmosphere": [{"chunk_id": "x", "title": "Y", "content": "Z", "entity_refs": []}],
            "npc_briefings": {},
            "discoverable": [],
            "thread_connections": [],
        }

        options = ContextOptions(include_lore=True)
        context = builder.build_context(
            "test_campaign", "look around", options, lore_context=lore
        )

        assert context["lore_context"] == lore

    def test_lore_context_none_becomes_empty(self, state_store):
        """Passing None for lore_context produces empty dict."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        context = builder.build_context(
            "test_campaign", "look around", lore_context=None
        )

        assert context["lore_context"] == {}

    def test_other_context_fields_unaffected_by_lore(self, state_store):
        """Adding lore_context doesn't affect other context fields."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        # Build without lore
        context_no_lore = builder.build_context("test_campaign", "look around")

        # Build with lore
        lore = {
            "atmosphere": [{"chunk_id": "a", "title": "b", "content": "c", "entity_refs": []}],
            "npc_briefings": {},
            "discoverable": [],
            "thread_connections": [],
        }
        context_with_lore = builder.build_context(
            "test_campaign", "look around", lore_context=lore
        )

        # Core fields should be the same
        assert context_no_lore["scene"] == context_with_lore["scene"]
        assert context_no_lore["present_entities"] == context_with_lore["present_entities"]
        assert context_no_lore["clocks"] == context_with_lore["clocks"]
        assert context_no_lore["calibration"] == context_with_lore["calibration"]
