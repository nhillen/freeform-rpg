"""
Tests for the Resolver.

Tests action resolution, dice rolls, and state diff generation.
"""

import pytest
from src.core.resolver import Resolver, ResolverOutput, RollResult
from tests.fixtures.contexts import minimal_context, combat_context


class TestDiceRolls:
    """Tests for the dice roll system."""

    def test_roll_produces_valid_result(self, state_store):
        """Roll produces a valid RollResult."""
        resolver = Resolver(state_store)
        result = resolver._roll()

        assert result.dice == "2d6"
        assert len(result.raw_values) == 2
        assert all(1 <= v <= 6 for v in result.raw_values)
        assert result.total == sum(result.raw_values)
        assert result.outcome in ["failure", "mixed", "success", "critical"]

    def test_forced_roll_respects_value(self, state_store):
        """Forced roll returns the specified total."""
        resolver = Resolver(state_store)

        result = resolver._roll(forced_total=7)
        assert result.total == 7
        assert result.outcome == "mixed"

        result = resolver._roll(forced_total=10)
        assert result.total == 10
        assert result.outcome == "success"

        result = resolver._roll(forced_total=12)
        assert result.total == 12
        assert result.outcome == "critical"

        result = resolver._roll(forced_total=4)
        assert result.total == 4
        assert result.outcome == "failure"

    def test_roll_bands_correct(self, state_store):
        """Roll outcomes map correctly to bands."""
        resolver = Resolver(state_store)

        # Failure: 2-6
        for total in [2, 3, 4, 5, 6]:
            result = resolver._roll(forced_total=total)
            assert result.outcome == "failure"

        # Mixed: 7-9
        for total in [7, 8, 9]:
            result = resolver._roll(forced_total=total)
            assert result.outcome == "mixed"

        # Success: 10-11
        for total in [10, 11]:
            result = resolver._roll(forced_total=total)
            assert result.outcome == "success"

        # Critical: 12
        result = resolver._roll(forced_total=12)
        assert result.outcome == "critical"

    def test_margin_calculated_correctly(self, state_store):
        """Roll margin is calculated correctly."""
        resolver = Resolver(state_store)

        # Failure margin: how far below 7
        result = resolver._roll(forced_total=4)
        assert result.margin == 3  # 7 - 4

        # Mixed has no margin
        result = resolver._roll(forced_total=8)
        assert result.margin == 0

        # Success margin: how far above 10
        result = resolver._roll(forced_total=11)
        assert result.margin == 1


class TestNeedsRoll:
    """Tests for determining if actions need rolls."""

    def test_safe_actions_no_roll(self, state_store, minimal_context):
        """Safe actions don't require rolls."""
        resolver = Resolver(state_store)

        safe_actions = ["look", "examine", "observe", "listen", "wait",
                        "think", "remember", "talk", "ask", "say"]

        for action in safe_actions:
            assert resolver._needs_roll(action, minimal_context) is False

    def test_risky_actions_need_roll(self, state_store, minimal_context):
        """Risky actions require rolls."""
        resolver = Resolver(state_store)

        risky_actions = ["attack", "fight", "combat", "steal", "hack",
                         "sneak", "climb", "persuade", "intimidate"]

        for action in risky_actions:
            assert resolver._needs_roll(action, minimal_context) is True

    def test_safe_action_with_risk_flags_needs_roll(self, state_store, minimal_context):
        """Safe action with risk flags (e.g., pursuit) requires a roll."""
        resolver = Resolver(state_store)

        # move is normally safe
        assert resolver._needs_roll("move", minimal_context) is False

        # But with pursuit risk flag, it requires a roll
        assert resolver._needs_roll("move", minimal_context, risk_flags=["pursuit"]) is True
        assert resolver._needs_roll("move", minimal_context, risk_flags=["dangerous"]) is True
        assert resolver._needs_roll("move", minimal_context, risk_flags=["hostile_present"]) is True

    def test_safe_action_with_irrelevant_flags_no_roll(self, state_store, minimal_context):
        """Safe action with non-risky flags still doesn't need a roll."""
        resolver = Resolver(state_store)

        # Unrecognized flag should not trigger a roll
        assert resolver._needs_roll("move", minimal_context, risk_flags=["some_other_flag"]) is False

    def test_risk_flags_from_validator_plumbed_through(self, state_store, minimal_context):
        """Risk flags from validator output are plumbed through to _needs_roll."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "move", "target_id": "test_location", "details": "running for the exit"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": ["pursuit", "dangerous"]
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)

        # move + pursuit flags should trigger a roll
        assert len(result.rolls) == 1


class TestCostApplication:
    """Tests for applying costs to state diff."""

    def test_costs_applied_to_clocks(self, state_store, minimal_context):
        """Costs from validator are applied to clock diffs."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [],
            "blocked_actions": [],
            "costs": {"heat": 2, "time": 1, "harm": 0}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)

        # Find clock changes
        clock_changes = {c["id"]: c["delta"] for c in result.state_diff["clocks"]}

        assert clock_changes.get("heat") == 2
        # Time is decremented (negative delta)
        assert clock_changes.get("time") == -1

    def test_zero_costs_not_added(self, state_store, minimal_context):
        """Zero-value costs don't create clock entries."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [],
            "blocked_actions": [],
            "costs": {"heat": 0, "time": 0, "harm": 0, "cred": 0, "rep": 0}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)

        # No clock changes for zero costs
        assert len(result.state_diff["clocks"]) == 0


class TestActionResolution:
    """Tests for resolving individual actions."""

    def test_successful_action_generates_success_event(self, state_store, minimal_context):
        """Successful action generates action_succeeded event."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "examine", "target_id": "test_location", "details": "looking around"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)

        assert len(result.engine_events) == 1
        assert result.engine_events[0]["type"] == "action_succeeded"
        assert result.engine_events[0]["details"]["action"] == "examine"

    def test_safe_action_auto_succeeds(self, state_store, minimal_context):
        """Safe actions automatically succeed without roll."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "look", "target_id": "test_location", "details": "observing"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)

        # No rolls for safe action
        assert len(result.rolls) == 0
        assert result.engine_events[0]["type"] == "action_succeeded"

    def test_risky_action_with_forced_success(self, state_store, combat_context):
        """Risky action with forced roll succeeds."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "attack", "target_id": "hostile_npc", "details": "punch"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}
        options = {"force_roll": 10}  # Force success

        result = resolver.resolve(combat_context, validator_output, planner_output, options)

        assert len(result.rolls) == 1
        assert result.rolls[0].outcome == "success"
        assert result.engine_events[0]["type"] == "action_succeeded"

    def test_risky_action_with_forced_failure(self, state_store, combat_context):
        """Risky action with forced roll fails."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "attack", "target_id": "hostile_npc", "details": "punch"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}
        options = {"force_roll": 4}  # Force failure

        result = resolver.resolve(combat_context, validator_output, planner_output, options)

        assert len(result.rolls) == 1
        assert result.rolls[0].outcome == "failure"
        assert result.engine_events[0]["type"] == "action_failed"

    def test_risky_action_with_mixed_result(self, state_store, combat_context):
        """Risky action with mixed result generates partial event."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "attack", "target_id": "hostile_npc", "details": "punch"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}
        options = {"force_roll": 8}  # Force mixed

        result = resolver.resolve(combat_context, validator_output, planner_output, options)

        assert len(result.rolls) == 1
        assert result.rolls[0].outcome == "mixed"
        assert result.engine_events[0]["type"] == "action_partial"
        assert "complication" in result.engine_events[0]["details"]

    def test_critical_success_marked(self, state_store, combat_context):
        """Critical success (12) is marked in event."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "attack", "target_id": "hostile_npc", "details": "punch"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}
        options = {"force_roll": 12}

        result = resolver.resolve(combat_context, validator_output, planner_output, options)

        assert result.rolls[0].outcome == "critical"
        assert result.engine_events[0]["details"]["critical"] is True


class TestFailureConsequences:
    """Tests for failure effects based on risk settings."""

    def test_failure_in_forgiving_mode(self, state_store, minimal_context):
        """Forgiving mode gives minor consequences."""
        minimal_context["calibration"]["risk"]["failure_mode"] = "forgiving"
        minimal_context["present_entities"].append("target")
        minimal_context["entities"].append({
            "id": "target", "type": "npc", "name": "Target",
            "attrs": {}, "tags": []
        })

        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "hack", "target_id": "target", "details": "breaking in"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}
        options = {"force_roll": 4}  # Force failure

        result = resolver.resolve(minimal_context, validator_output, planner_output, options)

        # Forgiving mode: just time lost
        clock_changes = [c for c in result.state_diff["clocks"]]
        time_changes = [c for c in clock_changes if c["id"] == "time"]
        assert len(time_changes) > 0
        assert time_changes[0]["delta"] == -1

    def test_failure_in_punishing_mode(self, state_store, minimal_context):
        """Punishing mode gives severe consequences."""
        minimal_context["calibration"]["risk"]["failure_mode"] = "punishing"
        minimal_context["present_entities"].append("target")
        minimal_context["entities"].append({
            "id": "target", "type": "npc", "name": "Target",
            "attrs": {}, "tags": []
        })

        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "attack", "target_id": "target", "details": "attacking"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}
        options = {"force_roll": 4}  # Force failure

        result = resolver.resolve(minimal_context, validator_output, planner_output, options)

        # Punishing mode for combat: harm and heat
        clock_changes = {c["id"]: c["delta"] for c in result.state_diff["clocks"]}
        assert clock_changes.get("harm", 0) >= 2
        assert clock_changes.get("heat", 0) >= 1

    def test_combat_failure_causes_harm(self, state_store, combat_context):
        """Combat failure in consequential mode causes harm."""
        combat_context["calibration"] = {
            "risk": {"failure_mode": "consequential"}
        }

        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "attack", "target_id": "hostile_npc", "details": "fighting"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}
        options = {"force_roll": 5}  # Force failure

        result = resolver.resolve(combat_context, validator_output, planner_output, options)

        clock_changes = {c["id"]: c["delta"] for c in result.state_diff["clocks"]}
        assert clock_changes.get("harm", 0) == 1


class TestTensionMoves:
    """Tests for processing planner tension moves."""

    def test_heat_tension_move(self, state_store, minimal_context):
        """Tension move mentioning heat advances heat clock."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {
            "tension_move": "Someone noticed - heat is rising"
        }

        result = resolver.resolve(minimal_context, validator_output, planner_output)

        clock_changes = {c["id"]: c["delta"] for c in result.state_diff["clocks"]}
        assert clock_changes.get("heat") == 1

        # Check for event
        tension_events = [e for e in result.engine_events if "tension" in e.get("tags", [])]
        assert len(tension_events) == 1

    def test_time_tension_move(self, state_store, minimal_context):
        """Tension move mentioning deadline advances time clock."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {
            "tension_move": "The deadline approaches"
        }

        result = resolver.resolve(minimal_context, validator_output, planner_output)

        clock_changes = {c["id"]: c["delta"] for c in result.state_diff["clocks"]}
        assert clock_changes.get("time") == -1

    def test_generic_tension_move(self, state_store, minimal_context):
        """Generic tension move generates NPC action event."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {
            "tension_move": "An enemy operative appears"
        }

        result = resolver.resolve(minimal_context, validator_output, planner_output)

        npc_events = [e for e in result.engine_events if e["type"] == "npc_action"]
        assert len(npc_events) == 1
        assert "enemy operative" in npc_events[0]["details"]["description"].lower()


class TestSuccessEffects:
    """Tests for success effects on state."""

    def test_investigate_success_adds_fact(self, state_store, minimal_context):
        """Successful investigation adds a discovered fact."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "investigate", "target_id": "test_location", "details": "searching"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}
        options = {"force_roll": 10}

        result = resolver.resolve(minimal_context, validator_output, planner_output, options)

        # Check for added fact
        assert len(result.state_diff["facts_add"]) > 0
        added_fact = result.state_diff["facts_add"][0]
        assert added_fact["visibility"] == "known"
        assert "player_discovery" in added_fact["tags"]


class TestOutputFormat:
    """Tests for resolver output format."""

    def test_output_has_required_fields(self, state_store, minimal_context):
        """ResolverOutput has all required fields."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)

        assert isinstance(result, ResolverOutput)
        assert hasattr(result, "engine_events")
        assert hasattr(result, "state_diff")
        assert hasattr(result, "rolls")

    def test_to_dict_format(self, state_store, minimal_context):
        """to_dict produces correctly formatted output."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "look", "target_id": "test_location", "details": "looking"}
            ],
            "blocked_actions": [],
            "costs": {"time": 1}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)
        output_dict = result.to_dict()

        assert "engine_events" in output_dict
        assert "state_diff" in output_dict
        assert "rolls" in output_dict

    def test_state_diff_has_all_sections(self, state_store, minimal_context):
        """State diff has all required sections."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)

        assert "clocks" in result.state_diff
        assert "facts_add" in result.state_diff
        assert "facts_update" in result.state_diff
        assert "inventory_changes" in result.state_diff
        assert "scene_update" in result.state_diff
        assert "threads_update" in result.state_diff


class TestMultipleActions:
    """Tests for resolving multiple actions."""

    def test_multiple_actions_all_resolved(self, state_store, minimal_context):
        """Multiple allowed actions are all resolved."""
        minimal_context["present_entities"].append("npc")
        minimal_context["entities"].append({
            "id": "npc", "type": "npc", "name": "NPC",
            "attrs": {}, "tags": []
        })

        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "look", "target_id": "test_location", "details": "looking"},
                {"action": "talk", "target_id": "npc", "details": "greeting"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)

        # Both actions should generate success events
        success_events = [e for e in result.engine_events if e["type"] == "action_succeeded"]
        assert len(success_events) == 2

    def test_multiple_risky_actions_get_separate_rolls(self, state_store, combat_context):
        """Each risky action gets its own roll."""
        combat_context["present_entities"].append("target2")
        combat_context["entities"].append({
            "id": "target2", "type": "npc", "name": "Target 2",
            "attrs": {}, "tags": ["hostile"]
        })

        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "attack", "target_id": "hostile_npc", "details": "punch"},
                {"action": "attack", "target_id": "target2", "details": "kick"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolver.resolve(combat_context, validator_output, planner_output)

        # Each risky action gets its own roll
        assert len(result.rolls) == 2


class TestOutcomeStates:
    """Tests for outcome_state and failure_state in engine events."""

    def test_success_event_has_outcome_state(self, state_store, minimal_context):
        """Successful action event includes outcome_state."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "examine", "target_id": "test_location", "details": "looking around"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)

        assert result.engine_events[0]["type"] == "action_succeeded"
        assert "outcome_state" in result.engine_events[0]["details"]

    def test_sneak_success_outcome_state(self, state_store, combat_context):
        """Sneak success has appropriate outcome state."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "sneak", "target_id": "hostile_npc", "details": "sneaking past"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}
        options = {"force_roll": 10}

        result = resolver.resolve(combat_context, validator_output, planner_output, options)

        state = result.engine_events[0]["details"]["outcome_state"]
        assert "undetected" in state.lower()

    def test_failure_event_has_failure_state(self, state_store, combat_context):
        """Failed action event includes failure_state."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "sneak", "target_id": "hostile_npc", "details": "sneaking past"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}
        options = {"force_roll": 4}

        result = resolver.resolve(combat_context, validator_output, planner_output, options)

        assert result.engine_events[0]["type"] == "action_failed"
        assert "failure_state" in result.engine_events[0]["details"]
        assert "detected" in result.engine_events[0]["details"]["failure_state"].lower()

    def test_mixed_event_has_mixed_state(self, state_store, combat_context):
        """Mixed result event includes mixed_state."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "attack", "target_id": "hostile_npc", "details": "punch"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}
        options = {"force_roll": 8}

        result = resolver.resolve(combat_context, validator_output, planner_output, options)

        assert result.engine_events[0]["type"] == "action_partial"
        assert "mixed_state" in result.engine_events[0]["details"]

    def test_critical_outcome_state_has_exceptional(self, state_store, combat_context):
        """Critical success outcome_state mentions exceptional result."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "hack", "target_id": "hostile_npc", "details": "hacking"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}
        options = {"force_roll": 12}

        result = resolver.resolve(combat_context, validator_output, planner_output, options)

        state = result.engine_events[0]["details"]["outcome_state"]
        assert "exceptionally" in state.lower()


class TestClockSourceTags:
    """Tests for source tags on clock entries in state_diff."""

    def test_cost_entries_tagged_as_cost(self, state_store, minimal_context):
        """Clock entries from cost application are tagged with source='cost'."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [],
            "blocked_actions": [],
            "costs": {"heat": 1, "time": 1}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)

        for entry in result.state_diff["clocks"]:
            assert entry.get("source") == "cost"

    def test_complication_entries_tagged(self, state_store, combat_context):
        """Clock entries from mixed results are tagged with source='complication'."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "attack", "target_id": "hostile_npc", "details": "punch"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}
        options = {"force_roll": 8}  # Mixed result

        result = resolver.resolve(combat_context, validator_output, planner_output, options)

        complication_entries = [c for c in result.state_diff["clocks"] if c.get("source") == "complication"]
        assert len(complication_entries) > 0

    def test_failure_entries_tagged(self, state_store, combat_context):
        """Clock entries from failures are tagged with source='failure'."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "attack", "target_id": "hostile_npc", "details": "punch"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}
        options = {"force_roll": 4}  # Failure

        result = resolver.resolve(combat_context, validator_output, planner_output, options)

        failure_entries = [c for c in result.state_diff["clocks"] if c.get("source") == "failure"]
        assert len(failure_entries) > 0

    def test_tension_entries_tagged(self, state_store, minimal_context):
        """Clock entries from tension moves are tagged with source='tension'."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {
            "tension_move": "Someone noticed - heat is rising"
        }

        result = resolver.resolve(minimal_context, validator_output, planner_output)

        tension_entries = [c for c in result.state_diff["clocks"] if c.get("source") == "tension"]
        assert len(tension_entries) > 0


class TestDurationTracking:
    """Tests for fictional duration estimation in resolver output."""

    def test_total_estimated_minutes_on_output(self, state_store, minimal_context):
        """ResolverOutput includes total_estimated_minutes."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "examine", "target_id": "test_location", "details": "looking around"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)
        # examine defaults to 1 minute in cyberpunk preset
        assert result.total_estimated_minutes == 1

    def test_total_estimated_minutes_in_to_dict(self, state_store, minimal_context):
        """to_dict includes total_estimated_minutes."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "investigate", "target_id": "test_location", "details": "searching"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)
        output_dict = result.to_dict()
        assert "total_estimated_minutes" in output_dict
        assert output_dict["total_estimated_minutes"] == 20  # investigate default

    def test_llm_estimate_takes_priority(self, state_store, minimal_context):
        """LLM-provided estimated_minutes takes priority over duration_map."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "examine", "target_id": "test_location", "details": "looking", "estimated_minutes": 8}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)
        assert result.total_estimated_minutes == 8

    def test_invalid_estimate_falls_back_to_map(self, state_store, minimal_context):
        """Out-of-range estimated_minutes falls back to duration_map."""
        resolver = Resolver(state_store)

        # 0 is out of range (min 1)
        validator_output = {
            "allowed_actions": [
                {"action": "examine", "target_id": "test_location", "details": "looking", "estimated_minutes": 0}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)
        assert result.total_estimated_minutes == 1  # examine default

    def test_over_max_estimate_falls_back(self, state_store, minimal_context):
        """estimated_minutes > 120 falls back to duration_map."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "examine", "target_id": "test_location", "details": "looking", "estimated_minutes": 200}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)
        assert result.total_estimated_minutes == 1  # examine default

    def test_multiple_actions_sum_durations(self, state_store, minimal_context):
        """Multiple actions have their durations summed."""
        minimal_context["present_entities"].append("npc")
        minimal_context["entities"].append({
            "id": "npc", "type": "npc", "name": "NPC",
            "attrs": {}, "tags": []
        })

        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "examine", "target_id": "test_location", "details": "looking"},
                {"action": "talk", "target_id": "npc", "details": "greeting"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)
        # examine (1) + talk (10) = 11
        assert result.total_estimated_minutes == 11

    def test_engine_events_include_estimated_minutes(self, state_store, minimal_context):
        """Engine events include estimated_minutes in details."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "examine", "target_id": "test_location", "details": "looking around"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)

        assert result.engine_events[0]["type"] == "action_succeeded"
        assert "estimated_minutes" in result.engine_events[0]["details"]
        assert result.engine_events[0]["details"]["estimated_minutes"] == 1

    def test_failed_action_includes_estimated_minutes(self, state_store, combat_context):
        """Failed action events include estimated_minutes."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [
                {"action": "attack", "target_id": "hostile_npc", "details": "punch"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}
        options = {"force_roll": 4}

        result = resolver.resolve(combat_context, validator_output, planner_output, options)

        assert result.engine_events[0]["type"] == "action_failed"
        assert "estimated_minutes" in result.engine_events[0]["details"]
        assert result.engine_events[0]["details"]["estimated_minutes"] == 3  # attack default

    def test_no_actions_zero_duration(self, state_store, minimal_context):
        """No allowed actions results in zero total_estimated_minutes."""
        resolver = Resolver(state_store)

        validator_output = {
            "allowed_actions": [],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolver.resolve(minimal_context, validator_output, planner_output)
        assert result.total_estimated_minutes == 0


class TestConvenienceFunction:
    """Tests for the resolve() convenience function."""

    def test_resolve_function_works(self, state_store, minimal_context):
        """The resolve() convenience function works correctly."""
        from src.core.resolver import resolve

        validator_output = {
            "allowed_actions": [
                {"action": "look", "target_id": "test_location", "details": "looking"}
            ],
            "blocked_actions": [],
            "costs": {}
        }
        planner_output = {}

        result = resolve(state_store, minimal_context, validator_output, planner_output)

        assert isinstance(result, dict)
        assert "engine_events" in result
        assert "state_diff" in result
        assert "rolls" in result
