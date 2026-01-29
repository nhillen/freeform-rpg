"""
Tests for dice pool resolution mechanics.

Tests the _roll_dice_pool() method and Mage: The Ascension style resolution.
"""

import pytest
from src.core.resolver import Resolver, RollResult
from src.core.system_config import (
    SystemConfig,
    load_system_config,
    mage_ascension_resolution_rules,
)


@pytest.fixture
def mage_config():
    """Mage: The Ascension system config."""
    return load_system_config({
        "resolution_rules": mage_ascension_resolution_rules()
    })


@pytest.fixture
def mage_resolver(state_store):
    """Resolver ready for dice pool testing."""
    return Resolver(state_store)


class TestPoolSize:
    """Dice pool size from entity stats."""

    def test_pool_from_stats(self, mage_resolver, mage_config):
        """Pool size = attribute + ability."""
        stats = {"dexterity": 3, "stealth": 2}
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[6, 7, 8, 3, 2]  # 5 dice
        )
        assert result.pool_size == 5
        assert result.stat_pair == "dexterity+stealth"

    def test_missing_stats_default_pool_1(self, mage_resolver, mage_config):
        """Missing stats result in minimum pool of 1."""
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", {},
            forced_result=[7]  # forced 1 die
        )
        assert result.pool_size == 1

    def test_partial_stats(self, mage_resolver, mage_config):
        """Only one stat present still works."""
        stats = {"dexterity": 3}  # no stealth
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[6, 8, 4]
        )
        assert result.pool_size == 3

    def test_default_stat_pair_for_unknown_action(self, mage_resolver, mage_config):
        """Unknown action type uses _default mapping."""
        stats = {"wits": 2, "alertness": 3}
        result = mage_resolver._roll_dice_pool(
            mage_config, "some_weird_action", stats,
            forced_result=[6, 7, 3, 2, 1]
        )
        assert result.stat_pair == "wits+alertness"
        assert result.pool_size == 5


class TestSuccessCounting:
    """Successes counted correctly at various difficulties."""

    def test_standard_difficulty_6(self, mage_resolver, mage_config):
        """Dice >= 6 count as successes at difficulty 6."""
        stats = {"dexterity": 3, "stealth": 2}
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[6, 7, 8, 3, 2]
        )
        # 6, 7, 8 succeed; 3, 2 fail; no 1s
        assert result.successes == 3

    def test_higher_difficulty(self, mage_resolver, mage_config):
        """Higher difficulty requires higher dice."""
        stats = {"dexterity": 3, "stealth": 2}
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[6, 7, 8, 3, 2],
            difficulty_override=8
        )
        # Only 8 succeeds at difficulty 8
        assert result.successes == 1
        assert result.difficulty == 8

    def test_all_successes(self, mage_resolver, mage_config):
        """All dice succeed."""
        stats = {"strength": 4, "brawl": 3}
        result = mage_resolver._roll_dice_pool(
            mage_config, "attack", stats,
            forced_result=[6, 7, 8, 9, 10, 6, 7]
        )
        assert result.successes == 7

    def test_no_successes(self, mage_resolver, mage_config):
        """No dice succeed (but no 1s either)."""
        stats = {"dexterity": 3, "stealth": 2}
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[2, 3, 4, 5, 5]
        )
        assert result.successes == 0
        assert result.outcome == "failure"


class TestOnesCancel:
    """1s cancel successes in Mage."""

    def test_ones_reduce_successes(self, mage_resolver, mage_config):
        """Each 1 cancels one success."""
        stats = {"dexterity": 3, "stealth": 2}
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[6, 7, 1, 3, 2]
        )
        # 2 successes - 1 one = 1 net success
        assert result.successes == 1
        assert result.ones == 1

    def test_ones_cannot_go_negative(self, mage_resolver, mage_config):
        """Net successes floor at 0."""
        stats = {"dexterity": 3, "stealth": 2}
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[6, 1, 1, 3, 2]
        )
        # 1 success - 2 ones = 0 net (clamped)
        assert result.successes == 0
        assert result.ones == 2


class TestBotchDetection:
    """Botch: 0 net successes with 1s rolled."""

    def test_botch_no_successes_with_ones(self, mage_resolver, mage_config):
        """Zero successes with 1s = botch."""
        stats = {"dexterity": 2, "stealth": 1}
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[1, 3, 4]
        )
        assert result.outcome == "botch"
        assert result.ones == 1
        assert result.successes == 0

    def test_no_botch_without_ones(self, mage_resolver, mage_config):
        """Zero successes but no 1s = failure, not botch."""
        stats = {"dexterity": 2, "stealth": 1}
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[2, 3, 4]
        )
        assert result.outcome == "failure"
        assert result.ones == 0

    def test_ones_cancel_to_zero_not_botch_if_successes_existed(self, mage_resolver, mage_config):
        """Successes canceled by 1s is not a botch (had raw successes)."""
        stats = {"dexterity": 2, "stealth": 1}
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[7, 1, 3]
        )
        # 1 success - 1 one = 0 net, but raw successes > 0 so not botch
        assert result.outcome == "failure"
        assert result.successes == 0


class TestOutcomeBandMapping:
    """Net successes map to correct outcome bands."""

    def test_one_success_is_mixed(self, mage_resolver, mage_config):
        """1 net success = mixed."""
        stats = {"dexterity": 3, "stealth": 2}
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[6, 3, 4, 5, 2]
        )
        assert result.successes == 1
        assert result.outcome == "mixed"

    def test_two_successes_is_success(self, mage_resolver, mage_config):
        """2 net successes = success."""
        stats = {"dexterity": 3, "stealth": 2}
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[6, 7, 4, 5, 2]
        )
        assert result.successes == 2
        assert result.outcome == "success"

    def test_three_successes_is_success(self, mage_resolver, mage_config):
        """3 net successes = success."""
        stats = {"dexterity": 3, "stealth": 2}
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[6, 7, 8, 5, 2]
        )
        assert result.successes == 3
        assert result.outcome == "success"

    def test_four_successes_is_critical(self, mage_resolver, mage_config):
        """4+ net successes = critical."""
        stats = {"dexterity": 3, "stealth": 2}
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[6, 7, 8, 9, 2]
        )
        assert result.successes == 4
        assert result.outcome == "critical"

    def test_many_successes_is_critical(self, mage_resolver, mage_config):
        """Many successes still maps to critical."""
        stats = {"strength": 5, "brawl": 4}
        result = mage_resolver._roll_dice_pool(
            mage_config, "attack", stats,
            forced_result=[6, 7, 8, 9, 10, 6, 7, 8, 9]
        )
        assert result.successes == 9
        assert result.outcome == "critical"


class TestForcedResults:
    """Forced results for deterministic testing."""

    def test_forced_pool_values(self, mage_resolver, mage_config):
        """Forced result overrides random dice."""
        stats = {"dexterity": 3, "stealth": 2}
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[10, 10, 10]
        )
        assert result.raw_values == [10, 10, 10]
        assert result.successes == 3
        assert result.pool_size == 3

    def test_forced_pool_overrides_stat_pool_size(self, mage_resolver, mage_config):
        """Forced result determines pool size regardless of stats."""
        stats = {"dexterity": 5, "stealth": 5}  # Would be pool 10
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[6, 7]  # Only 2 dice
        )
        assert result.pool_size == 2


class TestThresholdPast9:
    """Difficulty > 9 eats successes (Mage rule)."""

    def test_difficulty_10(self, mage_resolver, mage_config):
        """Difficulty 10: each success costs 1 extra (threshold past 9)."""
        stats = {"intelligence": 4, "computer": 3}
        result = mage_resolver._roll_dice_pool(
            mage_config, "hack", stats,
            forced_result=[10, 10, 10, 10, 3, 4, 5],
            difficulty_override=10
        )
        # 4 successes at diff 10, penalty = 10-9 = 1
        # net = max(0, 4-1) = 3
        assert result.successes == 3
        assert result.difficulty == 10


class TestRollResultFields:
    """RollResult carries pool metadata."""

    def test_pool_roll_has_metadata(self, mage_resolver, mage_config):
        """Pool roll result includes all pool fields."""
        stats = {"dexterity": 3, "stealth": 2}
        result = mage_resolver._roll_dice_pool(
            mage_config, "sneak", stats,
            forced_result=[6, 7, 1, 3, 2]
        )
        assert result.dice == "5d10"
        assert result.pool_size == 5
        assert result.difficulty == 6
        assert result.stat_pair == "dexterity+stealth"
        assert result.ones == 1
        assert result.successes == 1  # 2 successes - 1 one

    def test_2d6_roll_has_zero_pool_fields(self, state_store):
        """Standard 2d6 roll has zero pool fields."""
        resolver = Resolver(state_store)
        result = resolver._roll_2d6(forced_total=10)
        assert result.pool_size == 0
        assert result.successes == 0
        assert result.ones == 0
        assert result.stat_pair == ""


class TestRollForSystem:
    """Dispatcher selects correct roll method."""

    def test_default_dispatches_to_2d6(self, state_store):
        """Default config dispatches to 2d6."""
        resolver = Resolver(state_store)
        config = SystemConfig()
        result = resolver._roll_for_system(
            config, "attack", {}, forced_roll=10
        )
        assert result.dice == "2d6"
        assert result.outcome == "success"

    def test_dice_pool_dispatches_to_pool(self, state_store, mage_config):
        """Dice pool config dispatches to pool method."""
        resolver = Resolver(state_store)
        stats = {"dexterity": 3, "stealth": 2}
        result = resolver._roll_for_system(
            mage_config, "sneak", stats,
            forced_pool=[6, 7, 8, 3, 2]
        )
        assert "d10" in result.dice
        assert result.successes == 3


class TestBotchInResolution:
    """Botch outcome handling in full action resolution."""

    def test_botch_forces_severity_tier_2(self, state_store, mage_config):
        """Botch forces minimum severity tier 2."""
        resolver = Resolver(state_store)
        from tests.fixtures.contexts import minimal_context
        context = minimal_context()
        # Add resolution_rules to context's system
        context["system"]["resolution_rules"] = mage_ascension_resolution_rules()
        # Add player stats
        for entity in context["entities"]:
            if entity["id"] == "player":
                entity["attrs"]["stats"] = {"dexterity": 2, "stealth": 1}

        action = {"action": "sneak", "target_id": "scene", "details": "sneaking"}
        events, rolls, diff = resolver._resolve_action(
            action, context, {}, {},
            {"force_pool": [1, 3, 4]},  # botch: no successes, one 1
            system_config=mage_config,
        )

        # Should have action_failed with botch=True
        failed_events = [e for e in events if e["type"] == "action_failed"]
        assert len(failed_events) == 1
        assert failed_events[0]["details"]["botch"] is True
        assert failed_events[0]["details"]["severity_tier"] >= 2

        # Should have action_botched event
        botch_events = [e for e in events if e["type"] == "action_botched"]
        assert len(botch_events) == 1


class TestGetEntityStats:
    """_get_entity_stats extracts player stats from context."""

    def test_extracts_stats(self, state_store):
        """Extracts stats from player entity."""
        resolver = Resolver(state_store)
        context = {
            "entities": [
                {
                    "id": "player",
                    "type": "pc",
                    "name": "Test",
                    "attrs": {
                        "stats": {"dexterity": 3, "stealth": 2, "wits": 4}
                    },
                    "tags": ["player"],
                }
            ]
        }
        stats = resolver._get_entity_stats(context)
        assert stats["dexterity"] == 3
        assert stats["stealth"] == 2
        assert stats["wits"] == 4

    def test_missing_stats_returns_empty(self, state_store):
        """No stats returns empty dict."""
        resolver = Resolver(state_store)
        context = {
            "entities": [
                {"id": "player", "type": "pc", "name": "Test", "attrs": {}, "tags": ["player"]}
            ]
        }
        stats = resolver._get_entity_stats(context)
        assert stats == {}

    def test_no_player_returns_empty(self, state_store):
        """No player entity returns empty dict."""
        resolver = Resolver(state_store)
        context = {"entities": []}
        stats = resolver._get_entity_stats(context)
        assert stats == {}
