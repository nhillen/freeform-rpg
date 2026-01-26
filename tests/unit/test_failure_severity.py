"""
Tests for failure severity system.

End-to-end tests for severity tiers, situation facts, failure streaks,
and threat resolution.
"""

import pytest
from src.core.resolver import Resolver, ResolverOutput
from tests.fixtures.contexts import minimal_context, combat_context


class TestSeverityTiers:
    """Tests for _compute_severity_tier()."""

    def test_tier0_no_risk_no_threat(self, state_store):
        """No risk flags and no threats = tier 0."""
        resolver = Resolver(state_store)
        ctx = minimal_context()
        tier = resolver._compute_severity_tier([], ctx)
        assert tier == 0

    def test_tier0_empty_risk_flags(self, state_store):
        """Empty risk flags = tier 0."""
        resolver = Resolver(state_store)
        ctx = minimal_context()
        tier = resolver._compute_severity_tier([], ctx)
        assert tier == 0

    def test_tier1_risk_flags_present(self, state_store):
        """Risk flags present but no active threat = tier 1."""
        resolver = Resolver(state_store)
        ctx = minimal_context()
        tier = resolver._compute_severity_tier(["dangerous"], ctx)
        assert tier == 1

    def test_tier1_pursuit_flag(self, state_store):
        """Pursuit risk flag = tier 1."""
        resolver = Resolver(state_store)
        ctx = minimal_context()
        tier = resolver._compute_severity_tier(["pursuit"], ctx)
        assert tier == 1

    def test_tier2_pending_threats(self, state_store):
        """Pending threats = tier 2 regardless of risk flags."""
        resolver = Resolver(state_store)
        ctx = minimal_context()
        ctx["pending_threats"] = [
            {"fact_id": "t1", "description": "agent closing in", "turn_declared": 1, "severity": "hard"}
        ]
        tier = resolver._compute_severity_tier([], ctx)
        assert tier == 2

    def test_tier2_high_threat_npc(self, state_store):
        """High threat NPC in scene = tier 2."""
        resolver = Resolver(state_store)
        ctx = minimal_context()
        ctx["npc_capabilities"] = [{
            "entity_id": "corpo_agent",
            "name": "Agent Chen",
            "threat_level": "high",
            "capabilities": ["armed_combat"],
            "equipment": ["sidearm"],
            "limitations": [],
            "escalation_profile": {}
        }]
        tier = resolver._compute_severity_tier([], ctx)
        assert tier == 2

    def test_tier2_hard_situation_active(self, state_store):
        """Active hard situation = tier 2."""
        resolver = Resolver(state_store)
        ctx = minimal_context()
        ctx["active_situations"] = [{
            "fact_id": "sit1",
            "condition": "exposed",
            "severity": "hard",
            "narrative_hint": "detected"
        }]
        tier = resolver._compute_severity_tier([], ctx)
        assert tier == 2

    def test_tier0_irrelevant_risk_flags(self, state_store):
        """Non-risky flags don't increase tier."""
        resolver = Resolver(state_store)
        ctx = minimal_context()
        tier = resolver._compute_severity_tier(["some_random_flag"], ctx)
        assert tier == 0

    def test_tier2_overrides_tier1(self, state_store):
        """Active threat overrides risk flags — always tier 2."""
        resolver = Resolver(state_store)
        ctx = minimal_context()
        ctx["pending_threats"] = [
            {"fact_id": "t1", "description": "threat", "turn_declared": 1, "severity": "soft"}
        ]
        tier = resolver._compute_severity_tier(["dangerous"], ctx)
        assert tier == 2


class TestSituationFacts:
    """Tests for situation fact creation and clearing."""

    def test_failure_creates_situation_at_tier1(self, state_store):
        """Failed sneak at tier 1 creates exposed situation fact (soft)."""
        resolver = Resolver(state_store)
        ctx = minimal_context()
        ctx["present_entities"].append("guard")
        ctx["entities"].append({
            "id": "guard", "type": "npc", "name": "Guard",
            "attrs": {}, "tags": []
        })

        validator_output = {
            "allowed_actions": [
                {"action": "sneak", "target_id": "guard", "details": "sneaking past"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": ["dangerous"]
        }
        planner_output = {}
        options = {"force_roll": 4}  # Force failure

        result = resolver.resolve(ctx, validator_output, planner_output, options)

        # Should have situation_created event
        sit_events = [e for e in result.engine_events if e["type"] == "situation_created"]
        assert len(sit_events) == 1
        assert sit_events[0]["details"]["condition"] == "exposed"
        assert sit_events[0]["details"]["severity"] == "soft"

        # Should have situation fact in diff
        sit_facts = [
            f for f in result.state_diff["facts_add"]
            if f.get("predicate") == "situation"
        ]
        assert len(sit_facts) == 1
        assert sit_facts[0]["object"]["condition"] == "exposed"
        assert sit_facts[0]["object"]["active"] is True

    def test_failure_creates_hard_situation_at_tier2(self, state_store):
        """Failed sneak at tier 2 creates exposed situation (hard)."""
        resolver = Resolver(state_store)
        ctx = minimal_context()
        ctx["present_entities"].append("agent")
        ctx["entities"].append({
            "id": "agent", "type": "npc", "name": "Agent",
            "attrs": {}, "tags": []
        })
        ctx["npc_capabilities"] = [{
            "entity_id": "agent",
            "name": "Agent",
            "threat_level": "high",
            "capabilities": [],
            "equipment": [],
            "limitations": [],
            "escalation_profile": {}
        }]

        validator_output = {
            "allowed_actions": [
                {"action": "sneak", "target_id": "agent", "details": "sneaking past"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": ["hostile_present"]
        }
        planner_output = {}
        options = {"force_roll": 4}

        result = resolver.resolve(ctx, validator_output, planner_output, options)

        sit_events = [e for e in result.engine_events if e["type"] == "situation_created"]
        assert len(sit_events) == 1
        assert sit_events[0]["details"]["condition"] == "exposed"
        assert sit_events[0]["details"]["severity"] == "hard"

    def test_no_situation_at_tier0(self, state_store):
        """Failed action at tier 0 creates no situation fact."""
        resolver = Resolver(state_store)
        ctx = minimal_context()
        ctx["present_entities"].append("target")
        ctx["entities"].append({
            "id": "target", "type": "npc", "name": "Target",
            "attrs": {}, "tags": []
        })

        validator_output = {
            "allowed_actions": [
                {"action": "hack", "target_id": "target", "details": "hacking"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": []
        }
        planner_output = {}
        options = {"force_roll": 4}

        result = resolver.resolve(ctx, validator_output, planner_output, options)

        sit_events = [e for e in result.engine_events if e["type"] == "situation_created"]
        assert len(sit_events) == 0

    def test_success_clears_matching_situation(self, state_store):
        """Successful hide clears exposed situation."""
        resolver = Resolver(state_store)
        ctx = combat_context()
        ctx["active_situations"] = [{
            "fact_id": "sit_exposed_1",
            "condition": "exposed",
            "severity": "soft",
            "narrative_hint": "player is exposed",
            "source_action": "sneak",
            "clears_on": ["hide_success", "flee_success", "scene_change"]
        }]

        validator_output = {
            "allowed_actions": [
                {"action": "hide", "target_id": "combat_location", "details": "hiding behind cover"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": []
        }
        planner_output = {}
        options = {"force_roll": 10}  # Success

        result = resolver.resolve(ctx, validator_output, planner_output, options)

        cleared = [e for e in result.engine_events if e["type"] == "situation_cleared"]
        assert len(cleared) == 1
        assert cleared[0]["details"]["condition"] == "exposed"
        assert cleared[0]["details"]["fact_id"] == "sit_exposed_1"

    def test_success_does_not_clear_unrelated_situation(self, state_store):
        """Successful hide does not clear 'detected' situation."""
        resolver = Resolver(state_store)
        ctx = combat_context()
        ctx["active_situations"] = [{
            "fact_id": "sit_detected_1",
            "condition": "detected",
            "severity": "soft",
            "narrative_hint": "player identity known",
            "source_action": "hack",
            "clears_on": ["scene_change", "deceive_success"]
        }]

        validator_output = {
            "allowed_actions": [
                {"action": "hide", "target_id": "combat_location", "details": "hiding"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": []
        }
        planner_output = {}
        options = {"force_roll": 10}

        result = resolver.resolve(ctx, validator_output, planner_output, options)

        cleared = [e for e in result.engine_events if e["type"] == "situation_cleared"]
        assert len(cleared) == 0

    def test_duplicate_situation_not_created(self, state_store):
        """Don't create duplicate situation if same condition already active."""
        resolver = Resolver(state_store)
        ctx = minimal_context()
        ctx["present_entities"].append("guard")
        ctx["entities"].append({
            "id": "guard", "type": "npc", "name": "Guard",
            "attrs": {}, "tags": []
        })
        ctx["active_situations"] = [{
            "fact_id": "existing_sit",
            "condition": "exposed",
            "severity": "soft",
            "narrative_hint": "already exposed",
            "source_action": "sneak",
            "clears_on": ["hide_success", "flee_success", "scene_change"]
        }]

        validator_output = {
            "allowed_actions": [
                {"action": "sneak", "target_id": "guard", "details": "sneaking again"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": ["dangerous"]
        }
        planner_output = {}
        options = {"force_roll": 4}

        result = resolver.resolve(ctx, validator_output, planner_output, options)

        # Should not create new situation fact (already exists at same severity)
        new_sits = [
            f for f in result.state_diff["facts_add"]
            if f.get("predicate") == "situation"
        ]
        assert len(new_sits) == 0

    def test_situation_upgrades_soft_to_hard(self, state_store):
        """Failing at tier 2 upgrades existing soft situation to hard."""
        resolver = Resolver(state_store)
        ctx = minimal_context()
        ctx["present_entities"].append("agent")
        ctx["entities"].append({
            "id": "agent", "type": "npc", "name": "Agent",
            "attrs": {}, "tags": []
        })
        ctx["npc_capabilities"] = [{
            "entity_id": "agent",
            "name": "Agent",
            "threat_level": "high",
            "capabilities": [],
            "equipment": [],
            "limitations": [],
            "escalation_profile": {}
        }]
        ctx["active_situations"] = [{
            "fact_id": "existing_sit",
            "condition": "exposed",
            "severity": "soft",
            "narrative_hint": "exposed",
            "source_action": "sneak",
            "clears_on": ["hide_success", "flee_success", "scene_change"]
        }]

        validator_output = {
            "allowed_actions": [
                {"action": "sneak", "target_id": "agent", "details": "sneaking again"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": ["hostile_present"]
        }
        planner_output = {}
        options = {"force_roll": 4}

        result = resolver.resolve(ctx, validator_output, planner_output, options)

        # Should have an upgrade event
        sit_events = [e for e in result.engine_events if e["type"] == "situation_created"]
        assert len(sit_events) == 1
        assert sit_events[0]["details"]["severity"] == "hard"
        assert sit_events[0]["details"].get("upgraded_from") == "soft"

        # Should update existing fact (not create new)
        new_sits = [f for f in result.state_diff["facts_add"] if f.get("predicate") == "situation"]
        assert len(new_sits) == 0
        updates = [u for u in result.state_diff["facts_update"] if u["id"] == "existing_sit"]
        assert len(updates) == 1
        assert updates[0]["object"]["severity"] == "hard"


class TestTier2FailureEffects:
    """Tests for tier 2 failure effects (harm + extra heat)."""

    def test_tier2_physical_failure_adds_harm(self, state_store):
        """Physical failure at tier 2 adds harm to clock diff."""
        resolver = Resolver(state_store)
        ctx = combat_context()
        ctx["pending_threats"] = [
            {"fact_id": "t1", "description": "threat", "turn_declared": 1, "severity": "hard"}
        ]

        validator_output = {
            "allowed_actions": [
                {"action": "sneak", "target_id": "hostile_npc", "details": "sneaking"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": ["hostile_present"]
        }
        planner_output = {}
        options = {"force_roll": 4}

        result = resolver.resolve(ctx, validator_output, planner_output, options)

        clock_changes = {c["id"]: c["delta"] for c in result.state_diff["clocks"]}
        assert clock_changes.get("harm", 0) >= 1

    def test_tier2_stealth_failure_adds_extra_heat(self, state_store):
        """Stealth failure at tier 2 adds extra heat."""
        resolver = Resolver(state_store)
        ctx = combat_context()
        ctx["pending_threats"] = [
            {"fact_id": "t1", "description": "threat", "turn_declared": 1, "severity": "hard"}
        ]

        validator_output = {
            "allowed_actions": [
                {"action": "sneak", "target_id": "hostile_npc", "details": "sneaking"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": ["hostile_present"]
        }
        planner_output = {}
        options = {"force_roll": 4}

        result = resolver.resolve(ctx, validator_output, planner_output, options)

        # Should have at least one heat entry from the extra stealth penalty
        heat_entries = [c for c in result.state_diff["clocks"] if c["id"] == "heat"]
        assert len(heat_entries) >= 1


class TestConditionMapping:
    """Tests for action-to-condition mapping."""

    def test_sneak_maps_to_exposed(self, state_store):
        """Sneak failure maps to exposed condition."""
        resolver = Resolver(state_store)
        assert resolver._map_action_to_condition("sneak") == "exposed"

    def test_hide_maps_to_exposed(self, state_store):
        """Hide failure maps to exposed condition."""
        resolver = Resolver(state_store)
        assert resolver._map_action_to_condition("hide") == "exposed"

    def test_hack_maps_to_detected(self, state_store):
        """Hack failure maps to detected condition."""
        resolver = Resolver(state_store)
        assert resolver._map_action_to_condition("hack") == "detected"

    def test_flee_maps_to_cornered(self, state_store):
        """Flee failure maps to cornered condition."""
        resolver = Resolver(state_store)
        assert resolver._map_action_to_condition("flee") == "cornered"

    def test_fight_maps_to_injured(self, state_store):
        """Fight failure maps to injured condition."""
        resolver = Resolver(state_store)
        assert resolver._map_action_to_condition("fight") == "injured"

    def test_unmapped_action_returns_none(self, state_store):
        """Unmapped action returns None."""
        resolver = Resolver(state_store)
        assert resolver._map_action_to_condition("talk") is None
        assert resolver._map_action_to_condition("examine") is None

    def test_clear_conditions_for_exposed(self, state_store):
        """Exposed clears on hide_success, flee_success, scene_change."""
        resolver = Resolver(state_store)
        clears = resolver._get_clear_conditions("exposed")
        assert "hide_success" in clears
        assert "flee_success" in clears
        assert "scene_change" in clears


class TestFailureStreak:
    """Tests for failure streak checking and threat resolution."""

    def _make_threat_context(self):
        """Create a context with an active high-threat NPC."""
        ctx = combat_context()
        ctx["npc_capabilities"] = [{
            "entity_id": "hostile_npc",
            "name": "Agent Chen",
            "threat_level": "high",
            "capabilities": ["armed_combat", "tactical_training"],
            "equipment": ["sidearm"],
            "limitations": ["operates_solo"],
            "escalation_profile": {
                "soft": "Surveillance — follows, tracks",
                "hard": "Direct confrontation — corners target, draws weapon"
            }
        }]
        ctx["failure_streak"] = {"count": 0, "actions": [], "during_threat": True}
        return ctx

    def test_no_warning_at_count_0(self, state_store):
        """No warning when streak count is 0 and first failure."""
        resolver = Resolver(state_store)
        ctx = self._make_threat_context()
        ctx["failure_streak"] = {"count": 0, "actions": [], "during_threat": True}

        validator_output = {
            "allowed_actions": [
                {"action": "sneak", "target_id": "hostile_npc", "details": "sneaking"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": ["hostile_present"]
        }
        options = {"force_roll": 4}

        result = resolver.resolve(ctx, validator_output, {}, options)

        warnings = [e for e in result.engine_events if e["type"] == "failure_streak_warning"]
        assert len(warnings) == 0

    def test_warning_at_threshold_minus_1(self, state_store):
        """Warning emitted when streak reaches threshold - 1."""
        resolver = Resolver(state_store)
        ctx = self._make_threat_context()
        ctx["failure_streak"] = {"count": 1, "actions": ["sneak"], "during_threat": True}

        validator_output = {
            "allowed_actions": [
                {"action": "sneak", "target_id": "hostile_npc", "details": "sneaking"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": ["hostile_present"]
        }
        options = {"force_roll": 4}

        result = resolver.resolve(ctx, validator_output, {}, options)

        warnings = [e for e in result.engine_events if e["type"] == "failure_streak_warning"]
        assert len(warnings) == 1
        assert warnings[0]["details"]["next_failure_critical"] is True

    def test_threat_resolution_at_threshold(self, state_store):
        """Threat resolves against player at streak threshold."""
        resolver = Resolver(state_store)
        ctx = self._make_threat_context()
        ctx["failure_streak"] = {"count": 2, "actions": ["sneak", "sneak"], "during_threat": True}

        validator_output = {
            "allowed_actions": [
                {"action": "sneak", "target_id": "hostile_npc", "details": "sneaking"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": ["hostile_present"]
        }
        options = {"force_roll": 4}

        result = resolver.resolve(ctx, validator_output, {}, options)

        resolution = [e for e in result.engine_events if e["type"] == "threat_resolved_against_player"]
        assert len(resolution) == 1
        assert resolution[0]["details"]["binding"] is True
        assert resolution[0]["details"]["threat_entity_id"] == "hostile_npc"
        assert resolution[0]["details"]["harm_delta"] == 2
        assert "binding" in resolution[0]["tags"]

    def test_threat_resolution_applies_harm(self, state_store):
        """Threat resolution applies harm clock delta."""
        resolver = Resolver(state_store)
        ctx = self._make_threat_context()
        ctx["failure_streak"] = {"count": 2, "actions": ["sneak", "sneak"], "during_threat": True}

        validator_output = {
            "allowed_actions": [
                {"action": "sneak", "target_id": "hostile_npc", "details": "sneaking"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": ["hostile_present"]
        }
        options = {"force_roll": 4}

        result = resolver.resolve(ctx, validator_output, {}, options)

        # Should have harm from threat resolution (source: threat_resolution)
        harm_entries = [c for c in result.state_diff["clocks"]
                        if c["id"] == "harm" and c.get("source") == "threat_resolution"]
        assert len(harm_entries) == 1
        assert harm_entries[0]["delta"] == 2

    def test_threat_resolution_creates_cornered_situation(self, state_store):
        """Threat resolution creates a cornered situation fact."""
        resolver = Resolver(state_store)
        ctx = self._make_threat_context()
        ctx["failure_streak"] = {"count": 2, "actions": ["sneak", "sneak"], "during_threat": True}

        validator_output = {
            "allowed_actions": [
                {"action": "sneak", "target_id": "hostile_npc", "details": "sneaking"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": ["hostile_present"]
        }
        options = {"force_roll": 4}

        result = resolver.resolve(ctx, validator_output, {}, options)

        cornered_facts = [
            f for f in result.state_diff["facts_add"]
            if f.get("predicate") == "situation" and f["object"]["condition"] == "cornered"
        ]
        assert len(cornered_facts) >= 1

    def test_success_breaks_streak_no_resolution(self, state_store):
        """Success prevents threat resolution even with high prior count."""
        resolver = Resolver(state_store)
        ctx = self._make_threat_context()
        ctx["failure_streak"] = {"count": 2, "actions": ["sneak", "sneak"], "during_threat": True}

        validator_output = {
            "allowed_actions": [
                {"action": "sneak", "target_id": "hostile_npc", "details": "sneaking"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": ["hostile_present"]
        }
        options = {"force_roll": 10}  # Success breaks streak

        result = resolver.resolve(ctx, validator_output, {}, options)

        resolution = [e for e in result.engine_events if e["type"] == "threat_resolved_against_player"]
        assert len(resolution) == 0

    def test_no_resolution_without_active_threat(self, state_store):
        """No threat resolution when there's no active threat even at threshold."""
        resolver = Resolver(state_store)
        ctx = minimal_context()
        ctx["present_entities"].append("target")
        ctx["entities"].append({
            "id": "target", "type": "npc", "name": "Target",
            "attrs": {}, "tags": []
        })
        ctx["failure_streak"] = {"count": 2, "actions": ["hack", "hack"], "during_threat": False}

        validator_output = {
            "allowed_actions": [
                {"action": "hack", "target_id": "target", "details": "hacking"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": []
        }
        options = {"force_roll": 4}

        result = resolver.resolve(ctx, validator_output, {}, options)

        resolution = [e for e in result.engine_events if e["type"] == "threat_resolved_against_player"]
        assert len(resolution) == 0

    def test_escalation_profile_used_in_resolution(self, state_store):
        """Threat resolution uses NPC's escalation_profile.hard for description."""
        resolver = Resolver(state_store)
        ctx = self._make_threat_context()
        ctx["failure_streak"] = {"count": 2, "actions": ["sneak", "sneak"], "during_threat": True}

        validator_output = {
            "allowed_actions": [
                {"action": "sneak", "target_id": "hostile_npc", "details": "sneaking"}
            ],
            "blocked_actions": [],
            "costs": {},
            "risk_flags": ["hostile_present"]
        }
        options = {"force_roll": 4}

        result = resolver.resolve(ctx, validator_output, {}, options)

        resolution = [e for e in result.engine_events if e["type"] == "threat_resolved_against_player"]
        assert "confrontation" in resolution[0]["details"]["consequence_description"].lower()
