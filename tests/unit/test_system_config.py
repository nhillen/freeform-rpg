"""
Tests for SystemConfig loading and defaults.
"""

import pytest
from src.core.system_config import (
    SystemConfig,
    ResolutionConfig,
    StatSchema,
    DifficultyConfig,
    WillpowerConfig,
    load_system_config,
    mage_ascension_resolution_rules,
)


class TestDefaultConfig:
    """Default config matches current 2d6 resolver behavior."""

    def test_empty_dict_returns_default(self):
        """load_system_config({}) returns 2d6 defaults."""
        config = load_system_config({})
        assert config.name == "default_2d6"
        assert config.resolution.method == "2d6_bands"
        assert not config.is_dice_pool()

    def test_none_returns_default(self):
        """load_system_config(None-ish) returns defaults."""
        config = load_system_config(None)
        assert config.name == "default_2d6"

    def test_no_resolution_rules_returns_default(self):
        """System JSON with clock_rules but no resolution_rules returns 2d6."""
        config = load_system_config({
            "clock_rules": {"enabled": True, "clocks_enabled": ["heat"]}
        })
        assert config.name == "default_2d6"
        assert config.resolution.method == "2d6_bands"

    def test_default_has_no_stat_schema(self):
        """Default 2d6 config has empty stat schema."""
        config = load_system_config({})
        assert config.stat_schema.attributes == {}
        assert config.stat_schema.abilities == {}

    def test_default_willpower_disabled(self):
        """Default config has willpower disabled."""
        config = load_system_config({})
        assert not config.willpower.enabled

    def test_default_system_summary(self):
        """Default config produces correct system summary."""
        config = load_system_config({})
        summary = config.system_summary()
        assert summary["name"] == "default_2d6"
        assert "2d6" in summary["resolution"]
        assert not summary["botch_possible"]

    def test_default_empty_overrides(self):
        """Default config has empty override sets."""
        config = load_system_config({})
        assert config.condition_map == {}
        assert config.clear_map == {}
        assert config.safe_actions == set()
        assert config.risky_actions == set()
        assert config.action_stat_map == {}


class TestMageConfig:
    """Mage: The Ascension config parses correctly."""

    @pytest.fixture
    def mage_config(self):
        return load_system_config({
            "resolution_rules": mage_ascension_resolution_rules()
        })

    def test_name(self, mage_config):
        assert mage_config.name == "mage_ascension"

    def test_is_dice_pool(self, mage_config):
        assert mage_config.is_dice_pool()
        assert mage_config.resolution.method == "dice_pool"

    def test_die_type(self, mage_config):
        assert mage_config.resolution.die_type == 10

    def test_difficulty_default(self, mage_config):
        assert mage_config.difficulty.default == 6

    def test_ones_cancel(self, mage_config):
        assert mage_config.resolution.ones_cancel_successes is True

    def test_botch_on_ones(self, mage_config):
        assert mage_config.resolution.botch_on_ones is True

    def test_threshold_past_9(self, mage_config):
        assert mage_config.resolution.threshold_past_9 is True

    def test_pool_outcome_thresholds(self, mage_config):
        thresholds = mage_config.resolution.pool_outcome_thresholds
        assert thresholds["mixed"] == 1
        assert thresholds["success"] == 2
        assert thresholds["critical"] == 4

    def test_stat_schema_attributes(self, mage_config):
        attrs = mage_config.stat_schema.attributes
        assert "physical" in attrs
        assert "dexterity" in attrs["physical"]
        assert len(attrs) == 3  # physical, social, mental

    def test_stat_schema_abilities(self, mage_config):
        abilities = mage_config.stat_schema.abilities
        assert "talents" in abilities
        assert "stealth" in abilities["skills"]

    def test_stat_schema_special_traits(self, mage_config):
        traits = mage_config.stat_schema.special_traits
        assert "arete" in traits
        assert traits["arete"]["max"] == 10

    def test_all_attribute_names(self, mage_config):
        names = mage_config.stat_schema.all_attribute_names()
        assert "strength" in names
        assert "charisma" in names
        assert "intelligence" in names
        assert len(names) == 9

    def test_all_ability_names(self, mage_config):
        names = mage_config.stat_schema.all_ability_names()
        assert "stealth" in names
        assert "computer" in names
        assert len(names) == 29  # 9 talents + 10 skills + 10 knowledges

    def test_action_stat_map(self, mage_config):
        assert mage_config.action_stat_map["sneak"] == {
            "attribute": "dexterity", "ability": "stealth"
        }
        assert mage_config.action_stat_map["hack"] == {
            "attribute": "intelligence", "ability": "computer"
        }

    def test_get_stat_pair(self, mage_config):
        attr, ability = mage_config.get_stat_pair("sneak")
        assert attr == "dexterity"
        assert ability == "stealth"

    def test_get_stat_pair_default_fallback(self, mage_config):
        """Unknown action falls back to _default."""
        attr, ability = mage_config.get_stat_pair("unknown_action")
        assert attr == "wits"
        assert ability == "alertness"

    def test_willpower_enabled(self, mage_config):
        assert mage_config.willpower.enabled is True
        assert mage_config.willpower.auto_successes_per_spend == 1
        assert mage_config.willpower.max_per_turn == 1

    def test_retry_penalty(self, mage_config):
        assert mage_config.difficulty.retry_penalty == 1

    def test_system_summary(self, mage_config):
        summary = mage_config.system_summary()
        assert summary["name"] == "mage_ascension"
        assert "Dice pool" in summary["resolution"]
        assert summary["ones_cancel"] is True
        assert summary["botch_possible"] is True
        assert summary["willpower"] is True


class TestPartialConfig:
    """Configs with missing fields use sensible defaults."""

    def test_minimal_dice_pool(self):
        """Minimal dice pool config fills in defaults."""
        config = load_system_config({
            "resolution_rules": {
                "resolution": {"method": "dice_pool", "die_type": 10}
            }
        })
        assert config.is_dice_pool()
        assert config.resolution.die_type == 10
        # Defaults filled in
        assert config.difficulty.default == 6
        assert config.willpower.enabled is False
        assert config.action_stat_map == {}

    def test_missing_stat_schema(self):
        """Missing stat_schema returns empty."""
        config = load_system_config({
            "resolution_rules": {
                "resolution": {"method": "dice_pool"}
            }
        })
        assert config.stat_schema.attributes == {}

    def test_missing_willpower(self):
        """Missing willpower section defaults to disabled."""
        config = load_system_config({
            "resolution_rules": {
                "resolution": {"method": "dice_pool"}
            }
        })
        assert not config.willpower.enabled

    def test_get_stat_pair_no_map(self):
        """get_stat_pair with no map returns ultimate fallback."""
        config = SystemConfig()
        attr, ability = config.get_stat_pair("attack")
        assert attr == "wits"
        assert ability == "alertness"

    def test_name_auto_generated(self):
        """Name is auto-generated from method if not provided."""
        config = load_system_config({
            "resolution_rules": {
                "resolution": {"method": "dice_pool"}
            }
        })
        assert config.name == "dice_pool"

        config2 = load_system_config({
            "resolution_rules": {
                "resolution": {"method": "2d6_bands"}
            }
        })
        assert config2.name == "default_2d6"
