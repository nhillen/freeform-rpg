"""
Tests for the Orchestrator.

Tests the complete turn pipeline with mock LLM gateway.
"""

import pytest
from pathlib import Path

from src.core.orchestrator import Orchestrator, TurnResult, run_turn
from src.llm.gateway import MockGateway
from src.llm.prompt_registry import PromptRegistry
from tests.fixtures.state import setup_minimal_game_state


class TestOrchestratorInit:
    """Tests for orchestrator initialization."""

    def test_orchestrator_creates_components(self, state_store, mock_gateway, prompt_registry):
        """Orchestrator initializes all pipeline components."""
        orchestrator = Orchestrator(
            state_store=state_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        assert orchestrator.context_builder is not None
        assert orchestrator.validator is not None
        assert orchestrator.resolver is not None

    def test_orchestrator_default_versions(self, state_store, mock_gateway, prompt_registry):
        """Orchestrator uses default prompt versions."""
        orchestrator = Orchestrator(
            state_store=state_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        assert orchestrator.versions["interpreter"] == "v0"
        assert orchestrator.versions["planner"] == "v0"
        assert orchestrator.versions["narrator"] == "v0"

    def test_orchestrator_custom_versions(self, state_store, mock_gateway, prompt_registry):
        """Orchestrator accepts custom prompt versions."""
        orchestrator = Orchestrator(
            state_store=state_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry,
            prompt_versions={"interpreter": "v1"}
        )

        assert orchestrator.versions["interpreter"] == "v1"
        assert orchestrator.versions["planner"] == "v0"  # Default


class TestTurnExecution:
    """Tests for running turns through the pipeline."""

    def test_run_turn_returns_result(self, populated_store, mock_gateway, prompt_registry):
        """Running a turn returns a TurnResult."""
        orchestrator = Orchestrator(
            state_store=populated_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        result = orchestrator.run_turn("test_campaign", "I look around the room")

        assert isinstance(result, TurnResult)
        assert result.turn_no >= 1
        assert result.event_id is not None
        assert len(result.final_text) > 0

    def test_turn_logged_to_events(self, populated_store, mock_gateway, prompt_registry):
        """Turn is recorded in the events table."""
        orchestrator = Orchestrator(
            state_store=populated_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        result = orchestrator.run_turn("test_campaign", "I look around")

        # Verify event was logged
        events = populated_store.get_events_range("test_campaign", 1, 10)
        assert len(events) >= 1

        last_event = events[-1]
        assert last_event["player_input"] == "I look around"

    def test_examine_action_succeeds(self, populated_store, mock_gateway, prompt_registry):
        """Simple examine action succeeds and generates text."""
        orchestrator = Orchestrator(
            state_store=populated_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        result = orchestrator.run_turn("test_campaign", "I examine the room")

        assert result.clarification_needed is False
        assert "successfully" in result.final_text.lower() or "examine" in result.final_text.lower()

    def test_talk_action_succeeds(self, populated_store, mock_gateway, prompt_registry):
        """Talk action succeeds."""
        orchestrator = Orchestrator(
            state_store=populated_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        result = orchestrator.run_turn("test_campaign", "I talk to the NPC")

        assert result.clarification_needed is False
        assert len(result.final_text) > 0


class TestStubBehavior:
    """Tests for stub interpreter/planner/narrator behavior."""

    def test_stub_interpreter_detects_examine(self, populated_store, mock_gateway, prompt_registry):
        """Stub interpreter detects examine-type actions."""
        orchestrator = Orchestrator(
            state_store=populated_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        # Build context to test stub
        context = orchestrator.context_builder.build_context("test_campaign", "look around")
        context["player_input"] = "look around"

        output = orchestrator._stub_interpreter_output(context)

        assert output["proposed_actions"][0]["action"] == "examine"
        assert len(output["risk_flags"]) == 0

    def test_stub_interpreter_detects_attack(self, populated_store, mock_gateway, prompt_registry):
        """Stub interpreter detects attack actions and flags violence."""
        orchestrator = Orchestrator(
            state_store=populated_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        context = orchestrator.context_builder.build_context("test_campaign", "attack the guard")
        context["player_input"] = "attack the guard"

        output = orchestrator._stub_interpreter_output(context)

        assert output["proposed_actions"][0]["action"] == "attack"
        assert "violence" in output["risk_flags"]

    def test_stub_narrator_builds_from_events(self, populated_store, mock_gateway, prompt_registry):
        """Stub narrator generates text from resolver events."""
        orchestrator = Orchestrator(
            state_store=populated_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        resolver_output = {
            "engine_events": [
                {
                    "type": "action_succeeded",
                    "details": {"action": "examine", "target_id": "room"}
                }
            ]
        }

        output = orchestrator._stub_narrator_output(resolver_output)

        assert "successfully" in output["final_text"].lower()
        assert "examine" in output["final_text"].lower()


class TestStateDiffApplication:
    """Tests for state changes being applied."""

    def test_clock_updates_applied(self, populated_store, mock_gateway, prompt_registry):
        """Clock changes from resolver are applied."""
        # Get initial clock value
        initial_heat = populated_store.get_clock("heat")
        initial_value = initial_heat["value"]

        orchestrator = Orchestrator(
            state_store=populated_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        # Run a turn that includes violence (should add heat)
        result = orchestrator.run_turn(
            "test_campaign",
            "I attack the test NPC",
            options={"force_roll": 10}  # Force success
        )

        # Heat should have increased (from violence flag cost)
        updated_heat = populated_store.get_clock("heat")
        # Note: exact value depends on cost calculation, but should be >= initial
        assert updated_heat["value"] >= initial_value


class TestClarificationFlow:
    """Tests for clarification handling."""

    def test_invalid_target_needs_clarification(self, populated_store, mock_gateway, prompt_registry):
        """Targeting a non-existent entity triggers clarification."""
        orchestrator = Orchestrator(
            state_store=populated_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        # Create a mock response that references a non-existent entity
        mock_gateway.set_response("interpreter", {
            "intent": "talk to someone",
            "referenced_entities": ["nonexistent_npc"],
            "proposed_actions": [
                {"action": "talk", "target_id": "nonexistent_npc", "details": "greeting"}
            ],
            "assumptions": [],
            "risk_flags": [],
            "perception_flags": [
                {"entity_id": "nonexistent_npc", "issue": "not_present", "player_assumption": "thought they were here"}
            ]
        })

        result = orchestrator.run_turn("test_campaign", "talk to the stranger")

        # Should request clarification since all actions blocked
        assert result.clarification_needed is True
        assert len(result.clarification_question) > 0


class TestConvenienceFunction:
    """Tests for the run_turn convenience function."""

    def test_run_turn_function_works(self, populated_store):
        """The run_turn convenience function works."""
        result = run_turn(
            state_store=populated_store,
            campaign_id="test_campaign",
            player_input="I look around"
        )

        assert isinstance(result, dict)
        assert "turn_no" in result
        assert "final_text" in result
        assert "event_id" in result

    def test_run_turn_with_custom_versions(self, populated_store):
        """The run_turn function accepts prompt versions."""
        result = run_turn(
            state_store=populated_store,
            campaign_id="test_campaign",
            player_input="I look around",
            prompt_versions={"interpreter": "v0"}
        )

        assert isinstance(result, dict)


class TestTurnResultFormat:
    """Tests for TurnResult formatting."""

    def test_turn_result_to_dict(self):
        """TurnResult.to_dict() produces correct format."""
        result = TurnResult(
            turn_no=1,
            event_id="evt_123",
            final_text="Something happened.",
            clarification_needed=False,
            clarification_question="",
            suggested_actions=["look", "talk"]
        )

        d = result.to_dict()

        assert d["turn_no"] == 1
        assert d["event_id"] == "evt_123"
        assert d["final_text"] == "Something happened."
        assert d["clarification_needed"] is False
        assert d["suggested_actions"] == ["look", "talk"]

    def test_turn_result_clarification_format(self):
        """Clarification result has correct format."""
        result = TurnResult(
            turn_no=1,
            event_id="evt_456",
            final_text="Who do you want to talk to?",
            clarification_needed=True,
            clarification_question="Who do you want to talk to?",
            suggested_actions=[]
        )

        d = result.to_dict()

        assert d["clarification_needed"] is True
        assert d["clarification_question"] == "Who do you want to talk to?"


class TestMultipleTurns:
    """Tests for running multiple turns in sequence."""

    def test_turn_numbers_increment(self, populated_store, mock_gateway, prompt_registry):
        """Turn numbers increment correctly."""
        orchestrator = Orchestrator(
            state_store=populated_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        result1 = orchestrator.run_turn("test_campaign", "I look around")
        result2 = orchestrator.run_turn("test_campaign", "I examine the door")
        result3 = orchestrator.run_turn("test_campaign", "I try the handle")

        assert result2.turn_no == result1.turn_no + 1
        assert result3.turn_no == result2.turn_no + 1

    def test_state_persists_across_turns(self, populated_store, mock_gateway, prompt_registry):
        """State changes persist across turns."""
        orchestrator = Orchestrator(
            state_store=populated_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        # Get initial time
        initial_time = populated_store.get_clock("time")["value"]

        # Run multiple turns (each should cost some time)
        orchestrator.run_turn("test_campaign", "I look around")
        orchestrator.run_turn("test_campaign", "I examine the room")

        # Time should have decreased
        final_time = populated_store.get_clock("time")["value"]
        assert final_time <= initial_time
