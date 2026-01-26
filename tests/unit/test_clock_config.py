"""
Tests for clock_config module.

Tests empty defaults (opt-in model), cyberpunk preset, custom overrides,
disabled clocks, direction handling, cost lookups, complication effects,
failure effects, and tension keywords.
"""

import pytest
from src.core.clock_config import (
    ClockConfig,
    load_clock_config,
    cyberpunk_noir_clock_rules,
)


class TestClockConfigDefaults:
    """Tests for default ClockConfig — empty, opt-in model."""

    def test_default_config_no_clocks(self):
        """Default config has no clocks enabled."""
        config = ClockConfig()
        assert config.clocks_enabled == []

    def test_default_config_enabled(self):
        """Default config has enabled=True (framework available, just no clocks defined)."""
        config = ClockConfig()
        assert config.enabled is True

    def test_default_config_empty_cost_map(self):
        """Default config has no cost map."""
        config = ClockConfig()
        assert config.cost_map == {}

    def test_default_config_empty_direction(self):
        """Default config has no direction rules."""
        config = ClockConfig()
        assert config.direction == {}

    def test_default_config_show_deltas(self):
        """Default config shows deltas."""
        config = ClockConfig()
        assert config.show_deltas is True

    def test_default_config_no_costs(self):
        """Default config returns no costs for any action."""
        config = ClockConfig()
        assert config.get_cost("combat") == {}
        assert config.get_cost("talk") == {}
        assert config.get_cost("anything") == {}

    def test_default_config_no_complication_effects(self):
        """Default config returns no complication effects."""
        config = ClockConfig()
        assert config.get_complication_effects("combat") == []

    def test_default_config_no_failure_effects(self):
        """Default config returns no failure effects."""
        config = ClockConfig()
        assert config.get_failure_clock_effects("combat", "consequential") == []

    def test_default_config_no_tension_match(self):
        """Default config matches no tension keywords."""
        config = ClockConfig()
        assert config.get_tension_clock("The heat is rising") is None


class TestCyberpunkNoirPreset:
    """Tests for the cyberpunk noir clock rules preset."""

    def test_preset_returns_dict(self):
        """Preset returns a dict suitable for system_json clock_rules."""
        rules = cyberpunk_noir_clock_rules()
        assert isinstance(rules, dict)
        assert rules["enabled"] is True

    def test_preset_has_all_clocks(self):
        """Preset defines all 5 cyberpunk clocks."""
        rules = cyberpunk_noir_clock_rules()
        assert rules["clocks_enabled"] == ["heat", "time", "cred", "harm", "rep"]

    def test_preset_time_decrements(self):
        """Preset has time as a decrementing clock."""
        rules = cyberpunk_noir_clock_rules()
        assert rules["direction"]["time"] == "decrement"

    def test_preset_has_cost_map(self):
        """Preset has a cost map with action types."""
        rules = cyberpunk_noir_clock_rules()
        assert "combat" in rules["cost_map"]
        assert "talk" in rules["cost_map"]
        assert "_default" in rules["cost_map"]

    def test_preset_loads_into_config(self):
        """Preset can be loaded into a working ClockConfig."""
        rules = cyberpunk_noir_clock_rules()
        config = load_clock_config({"clock_rules": rules})
        assert config.enabled is True
        assert "heat" in config.clocks_enabled
        assert config.get_cost("combat") == {"heat": 1}

    def test_preset_default_cost_fallback(self):
        """Unknown actions fall back to _default cost in preset."""
        rules = cyberpunk_noir_clock_rules()
        config = load_clock_config({"clock_rules": rules})
        costs = config.get_cost("totally_unknown_action")
        assert costs == {"time": 1}


class TestLoadClockConfig:
    """Tests for load_clock_config from system_json."""

    def test_empty_dict_returns_empty_config(self):
        """Empty system_json returns empty config (no clocks)."""
        config = load_clock_config({})
        assert config.clocks_enabled == []
        assert config.cost_map == {}

    def test_none_returns_empty_config(self):
        """None system_json returns empty config."""
        config = load_clock_config(None)
        assert config.clocks_enabled == []

    def test_no_clock_rules_returns_empty_config(self):
        """System JSON without clock_rules returns empty config."""
        config = load_clock_config({"other_key": "value"})
        assert config.clocks_enabled == []

    def test_custom_clocks_enabled(self):
        """Custom clocks_enabled list is respected."""
        system = {"clock_rules": {"clocks_enabled": ["heat", "time"]}}
        config = load_clock_config(system)
        assert config.clocks_enabled == ["heat", "time"]

    def test_disabled_clocks(self):
        """Clocks can be fully disabled."""
        system = {"clock_rules": {"enabled": False}}
        config = load_clock_config(system)
        assert config.enabled is False

    def test_custom_direction(self):
        """Custom direction map is respected."""
        system = {"clock_rules": {"direction": {"time": "decrement", "heat": "decrement"}}}
        config = load_clock_config(system)
        assert config.direction["heat"] == "decrement"
        assert config.direction["time"] == "decrement"

    def test_show_deltas_from_display(self):
        """show_deltas is loaded from display.show_deltas."""
        system = {"clock_rules": {"display": {"show_deltas": False}}}
        config = load_clock_config(system)
        assert config.show_deltas is False

    def test_custom_cost_map(self):
        """Custom cost_map overrides defaults."""
        custom_costs = {"violence": {"heat": 3}, "talk": {"time": 2}}
        system = {"clock_rules": {"cost_map": custom_costs, "clocks_enabled": ["heat", "time"]}}
        config = load_clock_config(system)
        assert config.cost_map["violence"] == {"heat": 3}
        assert config.cost_map["talk"] == {"time": 2}


class TestGetCost:
    """Tests for ClockConfig.get_cost()."""

    def _cyberpunk_config(self):
        return load_clock_config({"clock_rules": cyberpunk_noir_clock_rules()})

    def test_known_action_returns_costs(self):
        """Known action type returns configured costs."""
        config = self._cyberpunk_config()
        costs = config.get_cost("combat")
        assert "heat" in costs
        assert costs["heat"] == 1

    def test_unknown_action_uses_default_key(self):
        """Unknown action type falls back to _default cost map entry."""
        config = self._cyberpunk_config()
        costs = config.get_cost("totally_unknown_action")
        assert costs == {"time": 1}

    def test_cost_filtered_to_active_clocks(self):
        """Costs are filtered to only include active clocks."""
        config = ClockConfig(
            clocks_enabled=["time"],
            cost_map={"combat": {"heat": 1}, "_default": {"time": 1}}
        )
        costs = config.get_cost("combat")
        # combat costs heat, but heat isn't enabled
        assert "heat" not in costs

    def test_steal_costs_both_heat_and_time(self):
        """Steal action costs both heat and time."""
        config = self._cyberpunk_config()
        costs = config.get_cost("steal")
        assert costs["heat"] == 2
        assert costs["time"] == 1

    def test_empty_config_no_costs(self):
        """Empty config returns no costs for any action."""
        config = ClockConfig()
        assert config.get_cost("combat") == {}
        assert config.get_cost("anything") == {}


class TestApplyDirection:
    """Tests for ClockConfig.apply_direction()."""

    def test_decrement_clock(self):
        """Decrementing clock gets negated delta."""
        config = ClockConfig(direction={"time": "decrement"})
        assert config.apply_direction("time", 1) == -1
        assert config.apply_direction("time", 3) == -3

    def test_increment_clock(self):
        """Incrementing clock keeps positive delta."""
        config = ClockConfig(direction={})
        assert config.apply_direction("heat", 1) == 1
        assert config.apply_direction("heat", 2) == 2

    def test_custom_decrement_clock(self):
        """Custom clock with decrement direction."""
        config = ClockConfig(direction={"fuel": "decrement"})
        assert config.apply_direction("fuel", 5) == -5

    def test_already_negative_delta_for_increment(self):
        """Negative delta on incrementing clock stays negative."""
        config = ClockConfig(direction={})
        assert config.apply_direction("heat", -1) == -1


class TestIsClockActive:
    """Tests for ClockConfig.is_clock_active()."""

    def test_active_clock(self):
        config = ClockConfig(clocks_enabled=["heat", "time"])
        assert config.is_clock_active("heat") is True

    def test_inactive_clock(self):
        config = ClockConfig(clocks_enabled=["heat", "time"])
        assert config.is_clock_active("rep") is False

    def test_no_clocks_active(self):
        config = ClockConfig()
        assert config.is_clock_active("heat") is False


class TestComplicationEffects:
    """Tests for ClockConfig.get_complication_effects()."""

    def _cyberpunk_config(self):
        return load_clock_config({"clock_rules": cyberpunk_noir_clock_rules()})

    def test_combat_complication(self):
        """Combat actions get combat-specific complication effects."""
        config = self._cyberpunk_config()
        effects = config.get_complication_effects("combat")
        assert any(e["id"] == "heat" for e in effects)

    def test_default_complication(self):
        """Non-combat actions get default complication effects."""
        config = self._cyberpunk_config()
        effects = config.get_complication_effects("talk")
        assert any(e["id"] == "time" for e in effects)

    def test_attack_maps_to_combat_category(self):
        """Attack action maps to combat category."""
        config = self._cyberpunk_config()
        effects = config.get_complication_effects("attack")
        assert any(e["id"] == "heat" for e in effects)

    def test_empty_config_no_effects(self):
        """Empty config returns no complication effects."""
        config = ClockConfig()
        assert config.get_complication_effects("combat") == []


class TestFailureEffects:
    """Tests for ClockConfig.get_failure_clock_effects()."""

    def _cyberpunk_config(self):
        return load_clock_config({"clock_rules": cyberpunk_noir_clock_rules()})

    def test_consequential_combat_failure(self):
        """Consequential combat failure causes harm."""
        config = self._cyberpunk_config()
        effects = config.get_failure_clock_effects("combat", "consequential")
        assert any(e["id"] == "harm" for e in effects)

    def test_forgiving_default_failure(self):
        """Forgiving default failure costs time."""
        config = self._cyberpunk_config()
        effects = config.get_failure_clock_effects("talk", "forgiving")
        assert any(e["id"] == "time" for e in effects)

    def test_punishing_combat_failure(self):
        """Punishing combat failure causes harm and heat."""
        config = self._cyberpunk_config()
        effects = config.get_failure_clock_effects("combat", "punishing")
        ids = [e["id"] for e in effects]
        assert "harm" in ids
        assert "heat" in ids

    def test_unknown_failure_mode_falls_back(self):
        """Unknown failure mode falls back to consequential."""
        config = self._cyberpunk_config()
        effects = config.get_failure_clock_effects("talk", "nonexistent_mode")
        assert len(effects) > 0

    def test_empty_config_no_effects(self):
        """Empty config returns no failure effects."""
        config = ClockConfig()
        assert config.get_failure_clock_effects("combat", "consequential") == []


class TestTensionClock:
    """Tests for ClockConfig.get_tension_clock()."""

    def _cyberpunk_config(self):
        return load_clock_config({"clock_rules": cyberpunk_noir_clock_rules()})

    def test_heat_keyword_match(self):
        """Tension text with 'heat' matches heat clock."""
        config = self._cyberpunk_config()
        assert config.get_tension_clock("The heat is rising") == "heat"

    def test_time_keyword_match(self):
        """Tension text with 'deadline' matches time clock."""
        config = self._cyberpunk_config()
        assert config.get_tension_clock("The deadline approaches") == "time"

    def test_attention_keyword_match(self):
        """Tension text with 'attention' matches heat clock."""
        config = self._cyberpunk_config()
        assert config.get_tension_clock("You've drawn attention") == "heat"

    def test_no_match_returns_none(self):
        """Tension text with no keywords returns None."""
        config = self._cyberpunk_config()
        assert config.get_tension_clock("Something mysterious happens") is None

    def test_empty_config_no_match(self):
        """Empty config matches nothing."""
        config = ClockConfig()
        assert config.get_tension_clock("The heat is rising") is None
