"""
Integration tests verifying v0 pipeline is unchanged when no content packs are loaded.

The entire content pack / lore system is optional. When no packs are installed
and no lore components are passed to the Orchestrator, all v0 behavior must
be preserved exactly.
"""

import pytest
from pathlib import Path

from src.db.state_store import StateStore
from src.core import Orchestrator, run_turn
from src.llm.gateway import MockGateway
from src.llm.prompt_registry import PromptRegistry
from src.context.builder import ContextBuilder, ContextOptions
from src.setup import SetupPipeline, run_setup
from tests.fixtures.state import setup_minimal_game_state


class TestNoPacks:
    """v0 behavior preserved when no packs loaded."""

    def test_orchestrator_defaults_no_lore(self, state_store, prompt_registry):
        """Orchestrator without lore params has None for all lore components."""
        orch = Orchestrator(
            state_store=state_store,
            llm_gateway=MockGateway(),
            prompt_registry=prompt_registry,
        )

        assert orch.lore_retriever is None
        assert orch.scene_cache is None
        assert orch.session_manager is None
        assert orch.pack_ids == []

    def test_turn_without_packs(self, state_store, prompt_registry):
        """Full turn executes without lore components."""
        setup_minimal_game_state(state_store)

        orch = Orchestrator(
            state_store=state_store,
            llm_gateway=MockGateway(),
            prompt_registry=prompt_registry,
        )

        result = orch.run_turn("test_campaign", "I look around the room")

        assert result.turn_no == 1
        assert len(result.final_text) > 0
        assert not result.clarification_needed

    def test_context_packet_lore_empty(self, state_store):
        """Context packet has empty lore_context without packs."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        context = builder.build_context("test_campaign", "look around")

        assert context["lore_context"] == {}

    def test_multiple_turns_no_packs(self, state_store, prompt_registry):
        """Multiple turns work without packs — same as v0."""
        setup_minimal_game_state(state_store)

        orch = Orchestrator(
            state_store=state_store,
            llm_gateway=MockGateway(),
            prompt_registry=prompt_registry,
        )

        t1 = orch.run_turn("test_campaign", "I examine the area")
        t2 = orch.run_turn("test_campaign", "I talk to the NPC")
        t3 = orch.run_turn("test_campaign", "I leave")

        assert t1.turn_no == 1
        assert t2.turn_no == 2
        assert t3.turn_no == 3

    def test_run_turn_convenience_no_packs(self, state_store):
        """The run_turn convenience function works without packs."""
        setup_minimal_game_state(state_store)

        result = run_turn(
            state_store=state_store,
            campaign_id="test_campaign",
            player_input="I look around",
        )

        assert isinstance(result, dict)
        assert "turn_no" in result
        assert "final_text" in result

    def test_full_setup_then_play_no_packs(self, state_store, prompt_registry):
        """Setup → play flow works without any content packs."""
        pipeline = SetupPipeline(state_store)
        setup_result = pipeline.run_setup(
            template_id="default",
            calibration_preset="noir_standard",
            character_responses={"name": "No-Pack Player"},
        )

        orch = Orchestrator(
            state_store=state_store,
            llm_gateway=MockGateway(),
            prompt_registry=prompt_registry,
        )

        result = orch.run_turn(setup_result.campaign_id, "I check my surroundings")

        assert result.turn_no == 1
        assert len(result.final_text) > 0

    def test_context_options_include_lore_irrelevant(self, state_store):
        """include_lore option has no effect when no lore is passed."""
        setup_minimal_game_state(state_store)
        builder = ContextBuilder(state_store)

        options_on = ContextOptions(include_lore=True)
        options_off = ContextOptions(include_lore=False)

        ctx_on = builder.build_context("test_campaign", "test", options_on)
        ctx_off = builder.build_context("test_campaign", "test", options_off)

        # Both should have empty lore_context since no lore was provided
        assert ctx_on["lore_context"] == {}
        assert ctx_off["lore_context"] == {}
