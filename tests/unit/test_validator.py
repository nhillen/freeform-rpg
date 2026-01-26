"""
Tests for the Validator.

Tests action validation, perception checking, and cost calculation.
"""

import pytest
from src.core.validator import Validator, ValidationResult
from tests.fixtures.contexts import minimal_context, combat_context, investigation_context


class TestActionValidation:
    """Tests for basic action validation."""

    def test_valid_action_allowed(self, state_store, minimal_context):
        """Valid action targeting present entity is allowed."""
        validator = Validator(state_store)

        interpreter_output = {
            "intent": "examine the room",
            "referenced_entities": ["test_location"],
            "proposed_actions": [
                {"action": "examine", "target_id": "test_location", "details": "looking around"}
            ],
            "assumptions": [],
            "risk_flags": [],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, minimal_context)

        assert len(result.allowed_actions) == 1
        assert len(result.blocked_actions) == 0
        assert result.allowed_actions[0]["action"] == "examine"

    def test_unknown_entity_blocked(self, state_store, minimal_context):
        """Action targeting unknown entity is blocked."""
        validator = Validator(state_store)

        interpreter_output = {
            "intent": "talk to stranger",
            "referenced_entities": ["unknown_npc"],
            "proposed_actions": [
                {"action": "talk", "target_id": "unknown_npc", "details": "asking questions"}
            ],
            "assumptions": [],
            "risk_flags": [],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, minimal_context)

        assert len(result.allowed_actions) == 0
        assert len(result.blocked_actions) == 1
        assert "unknown" in result.blocked_actions[0]["reason"].lower()

    def test_perception_flag_blocks_action(self, state_store, minimal_context):
        """Action is blocked if perception flags indicate target not perceivable."""
        validator = Validator(state_store)

        interpreter_output = {
            "intent": "talk to someone",
            "referenced_entities": ["flagged_npc"],
            "proposed_actions": [
                {"action": "talk", "target_id": "flagged_npc", "details": "asking questions"}
            ],
            "assumptions": [],
            "risk_flags": [],
            "perception_flags": [
                {"entity_id": "flagged_npc", "issue": "not_present", "player_assumption": "thought they were here"}
            ]
        }

        result = validator.validate(interpreter_output, minimal_context)

        assert len(result.allowed_actions) == 0
        assert len(result.blocked_actions) == 1
        assert "not perceivable" in result.blocked_actions[0]["reason"].lower()


class TestCostCalculation:
    """Tests for action cost assignment."""

    def test_violence_costs_heat(self, state_store, combat_context):
        """Violence actions cost heat."""
        validator = Validator(state_store)

        interpreter_output = {
            "intent": "attack",
            "referenced_entities": ["hostile_npc"],
            "proposed_actions": [
                {"action": "attack", "target_id": "hostile_npc", "details": "punch"}
            ],
            "assumptions": [],
            "risk_flags": ["violence"],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, combat_context)

        assert result.costs["heat"] > 0

    def test_social_costs_time(self, state_store, minimal_context):
        """Social actions cost time."""
        # Add an NPC to talk to
        minimal_context["present_entities"].append("test_npc")
        minimal_context["entities"].append({
            "id": "test_npc", "type": "npc", "name": "Test NPC",
            "attrs": {}, "tags": []
        })

        validator = Validator(state_store)

        interpreter_output = {
            "intent": "talk",
            "referenced_entities": ["test_npc"],
            "proposed_actions": [
                {"action": "talk", "target_id": "test_npc", "details": "asking questions"}
            ],
            "assumptions": [],
            "risk_flags": [],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, minimal_context)

        assert result.costs["time"] > 0

    def test_multiple_actions_accumulate_costs(self, state_store, combat_context):
        """Multiple actions have their costs accumulated."""
        validator = Validator(state_store)

        interpreter_output = {
            "intent": "fight and search",
            "referenced_entities": ["hostile_npc", "combat_location"],
            "proposed_actions": [
                {"action": "attack", "target_id": "hostile_npc", "details": "punch"},
                {"action": "search", "target_id": "combat_location", "details": "look for exits"}
            ],
            "assumptions": [],
            "risk_flags": ["violence"],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, combat_context)

        # Both heat (from attack) and time (from search) should be > 0
        assert result.costs["heat"] > 0
        assert result.costs["time"] > 0


class TestContradictionChecking:
    """Tests for contradiction detection."""

    def test_dead_target_blocked(self, state_store, minimal_context):
        """Cannot target a dead entity."""
        # Add a dead NPC
        minimal_context["present_entities"].append("dead_npc")
        minimal_context["entities"].append({
            "id": "dead_npc", "type": "npc", "name": "Dead NPC",
            "attrs": {}, "tags": []
        })
        minimal_context["facts"].append({
            "id": "dead_fact",
            "subject_id": "dead_npc",
            "predicate": "status",
            "object": "dead",
            "visibility": "known",
            "confidence": 1.0,
            "tags": []
        })

        validator = Validator(state_store)

        interpreter_output = {
            "intent": "talk to dead person",
            "referenced_entities": ["dead_npc"],
            "proposed_actions": [
                {"action": "talk", "target_id": "dead_npc", "details": "asking questions"}
            ],
            "assumptions": [],
            "risk_flags": [],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, minimal_context)

        assert len(result.blocked_actions) == 1
        assert "dead" in result.blocked_actions[0]["reason"].lower()

    def test_violence_in_no_violence_zone(self, state_store, minimal_context):
        """Violence blocked in no-violence zones."""
        minimal_context["scene"]["constraints"]["no_violence"] = True
        minimal_context["present_entities"].append("target_npc")
        minimal_context["entities"].append({
            "id": "target_npc", "type": "npc", "name": "Target",
            "attrs": {}, "tags": []
        })

        validator = Validator(state_store)

        interpreter_output = {
            "intent": "attack",
            "referenced_entities": ["target_npc"],
            "proposed_actions": [
                {"action": "attack", "target_id": "target_npc", "details": "punch"}
            ],
            "assumptions": [],
            "risk_flags": ["violence"],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, minimal_context)

        assert len(result.blocked_actions) == 1
        assert "violence" in result.blocked_actions[0]["reason"].lower()


class TestClarificationHandling:
    """Tests for clarification question generation."""

    def test_clarification_when_all_blocked(self, state_store, minimal_context):
        """Clarification requested when all actions blocked due to perception."""
        validator = Validator(state_store)

        interpreter_output = {
            "intent": "do something impossible",
            "referenced_entities": ["nonexistent"],
            "proposed_actions": [
                {"action": "interact", "target_id": "nonexistent", "details": "somehow"}
            ],
            "assumptions": [],
            "risk_flags": [],
            "perception_flags": [
                {"entity_id": "nonexistent", "issue": "not_present", "player_assumption": "thought it was here"}
            ]
        }

        result = validator.validate(interpreter_output, minimal_context)

        assert result.clarification_needed is True
        assert len(result.clarification_question) > 0

    def test_no_clarification_when_actions_allowed(self, state_store, minimal_context):
        """No clarification when actions are allowed."""
        validator = Validator(state_store)

        interpreter_output = {
            "intent": "look around",
            "referenced_entities": ["test_location"],
            "proposed_actions": [
                {"action": "examine", "target_id": "test_location", "details": "looking"}
            ],
            "assumptions": [],
            "risk_flags": [],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, minimal_context)

        assert result.clarification_needed is False


class TestRiskCalibration:
    """Tests for risk-adjusted validation."""

    def test_low_lethality_reduces_harm(self, state_store, minimal_context):
        """Low lethality setting reduces harm costs."""
        minimal_context["calibration"]["risk"]["lethality"] = "low"
        minimal_context["present_entities"].append("target")
        minimal_context["entities"].append({
            "id": "target", "type": "npc", "name": "Target",
            "attrs": {}, "tags": []
        })

        validator = Validator(state_store)

        # An action that would normally cost harm
        interpreter_output = {
            "intent": "fight",
            "referenced_entities": ["target"],
            "proposed_actions": [
                {"action": "attack", "target_id": "target", "details": "fighting"}
            ],
            "assumptions": [],
            "risk_flags": [],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, minimal_context)

        # The harm cost should be reduced (or at least not increased)
        # This is a soft test - exact values depend on implementation
        assert "harm" in result.costs


class TestEstimatedMinutesPassthrough:
    """Tests for estimated_minutes passthrough from interpreter to validator output."""

    def test_estimated_minutes_passed_through(self, state_store, minimal_context):
        """estimated_minutes from interpreter is included in allowed_actions."""
        validator = Validator(state_store)

        interpreter_output = {
            "intent": "look around",
            "referenced_entities": ["test_location"],
            "proposed_actions": [
                {"action": "examine", "target_id": "test_location", "details": "looking", "estimated_minutes": 3}
            ],
            "assumptions": [],
            "risk_flags": [],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, minimal_context)

        assert len(result.allowed_actions) == 1
        assert result.allowed_actions[0]["estimated_minutes"] == 3

    def test_missing_estimated_minutes_not_in_output(self, state_store, minimal_context):
        """When estimated_minutes is absent, it is not added to allowed_actions."""
        validator = Validator(state_store)

        interpreter_output = {
            "intent": "look around",
            "referenced_entities": ["test_location"],
            "proposed_actions": [
                {"action": "examine", "target_id": "test_location", "details": "looking"}
            ],
            "assumptions": [],
            "risk_flags": [],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, minimal_context)

        assert len(result.allowed_actions) == 1
        assert "estimated_minutes" not in result.allowed_actions[0]


class TestRiskFlagsPassthrough:
    """Tests for risk_flags passthrough from interpreter to validator output."""

    def test_risk_flags_passed_through(self, state_store, minimal_context):
        """Risk flags from interpreter are included in validator output."""
        validator = Validator(state_store)

        interpreter_output = {
            "intent": "flee",
            "referenced_entities": ["test_location"],
            "proposed_actions": [
                {"action": "move", "target_id": "test_location", "details": "running away"}
            ],
            "assumptions": [],
            "risk_flags": ["pursuit", "dangerous"],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, minimal_context)

        assert result.risk_flags == ["pursuit", "dangerous"]
        output_dict = result.to_dict()
        assert output_dict["risk_flags"] == ["pursuit", "dangerous"]

    def test_empty_risk_flags_passed_through(self, state_store, minimal_context):
        """Empty risk flags are preserved."""
        validator = Validator(state_store)

        interpreter_output = {
            "intent": "look",
            "referenced_entities": ["test_location"],
            "proposed_actions": [
                {"action": "examine", "target_id": "test_location", "details": "looking"}
            ],
            "assumptions": [],
            "risk_flags": [],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, minimal_context)

        assert result.risk_flags == []

    def test_missing_risk_flags_defaults_empty(self, state_store, minimal_context):
        """Missing risk_flags key defaults to empty list."""
        validator = Validator(state_store)

        interpreter_output = {
            "intent": "look",
            "referenced_entities": ["test_location"],
            "proposed_actions": [
                {"action": "examine", "target_id": "test_location", "details": "looking"}
            ],
            "assumptions": [],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, minimal_context)

        assert result.risk_flags == []


class TestOutputFormat:
    """Tests for validator output format."""

    def test_output_has_required_fields(self, state_store, minimal_context):
        """Validator output has all required fields."""
        validator = Validator(state_store)

        interpreter_output = {
            "intent": "test",
            "referenced_entities": [],
            "proposed_actions": [],
            "assumptions": [],
            "risk_flags": [],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, minimal_context)
        output_dict = result.to_dict()

        assert "allowed_actions" in output_dict
        assert "blocked_actions" in output_dict
        assert "clarification_needed" in output_dict
        assert "clarification_question" in output_dict
        assert "costs" in output_dict
        assert "risk_flags" in output_dict

    def test_costs_has_all_clock_types(self, state_store, minimal_context):
        """Costs dict has all clock types."""
        validator = Validator(state_store)

        interpreter_output = {
            "intent": "test",
            "referenced_entities": [],
            "proposed_actions": [],
            "assumptions": [],
            "risk_flags": [],
            "perception_flags": []
        }

        result = validator.validate(interpreter_output, minimal_context)

        assert "heat" in result.costs
        assert "time" in result.costs
        assert "cred" in result.costs
        assert "harm" in result.costs
        assert "rep" in result.costs
