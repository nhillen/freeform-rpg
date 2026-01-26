"""
Tests for the fictional time estimation system.

Tests scene time advancement, period transitions, midnight rollover,
and edge cases.
"""

import pytest
from src.core.orchestrator import Orchestrator
from src.db.state_store import StateStore


class TestComputePeriod:
    """Tests for Orchestrator._compute_period()."""

    def test_night_hours(self):
        """Late night and early morning hours map to night."""
        assert Orchestrator._compute_period(0) == "night"
        assert Orchestrator._compute_period(1) == "night"
        assert Orchestrator._compute_period(4) == "night"
        assert Orchestrator._compute_period(20) == "night"
        assert Orchestrator._compute_period(23) == "night"

    def test_pre_dawn(self):
        """Hour 5 is pre_dawn."""
        assert Orchestrator._compute_period(5) == "pre_dawn"

    def test_dawn(self):
        """Hours 6-7 are dawn."""
        assert Orchestrator._compute_period(6) == "dawn"
        assert Orchestrator._compute_period(7) == "dawn"

    def test_morning(self):
        """Hours 8-11 are morning."""
        assert Orchestrator._compute_period(8) == "morning"
        assert Orchestrator._compute_period(11) == "morning"

    def test_afternoon(self):
        """Hours 12-16 are afternoon."""
        assert Orchestrator._compute_period(12) == "afternoon"
        assert Orchestrator._compute_period(16) == "afternoon"

    def test_evening(self):
        """Hours 17-19 are evening."""
        assert Orchestrator._compute_period(17) == "evening"
        assert Orchestrator._compute_period(19) == "evening"


class TestAdvanceSceneTime:
    """Tests for Orchestrator._advance_scene_time()."""

    def _make_orchestrator(self, state_store):
        """Create an orchestrator with minimal dependencies."""
        from src.llm.gateway import MockGateway
        from src.llm.prompt_registry import PromptRegistry
        from pathlib import Path

        prompts_dir = Path(__file__).parent.parent.parent / "src" / "prompts"
        return Orchestrator(
            state_store=state_store,
            llm_gateway=MockGateway(),
            prompt_registry=PromptRegistry(prompts_dir),
        )

    def test_basic_time_advance(self, state_store):
        """Scene time advances by the given minutes."""
        state_store.set_scene(
            location_id="test_loc",
            present_entity_ids=["player"],
            time={"hour": 23, "minute": 0, "period": "night", "weather": "rain"},
        )

        orch = self._make_orchestrator(state_store)
        result = orch._advance_scene_time(15)

        assert result["new_hour"] == 23
        assert result["new_minute"] == 15
        assert result["period_changed"] is False

        # Verify DB was updated
        scene = state_store.get_scene()
        assert scene["time"]["hour"] == 23
        assert scene["time"]["minute"] == 15

    def test_midnight_rollover(self, state_store):
        """Time correctly rolls over past midnight."""
        state_store.set_scene(
            location_id="test_loc",
            present_entity_ids=["player"],
            time={"hour": 23, "minute": 50, "period": "night"},
        )

        orch = self._make_orchestrator(state_store)
        result = orch._advance_scene_time(30)

        assert result["new_hour"] == 0
        assert result["new_minute"] == 20
        assert result["new_period"] == "night"
        assert result["period_changed"] is False

    def test_period_transition(self, state_store):
        """Period changes when crossing a boundary."""
        state_store.set_scene(
            location_id="test_loc",
            present_entity_ids=["player"],
            time={"hour": 5, "minute": 50, "period": "pre_dawn"},
        )

        orch = self._make_orchestrator(state_store)
        result = orch._advance_scene_time(15)

        assert result["new_hour"] == 6
        assert result["new_minute"] == 5
        assert result["old_period"] == "pre_dawn"
        assert result["new_period"] == "dawn"
        assert result["period_changed"] is True

    def test_weather_preserved(self, state_store):
        """Weather and other fields are preserved when time advances."""
        state_store.set_scene(
            location_id="test_loc",
            present_entity_ids=["player"],
            time={"hour": 10, "minute": 30, "period": "morning", "weather": "fog"},
        )

        orch = self._make_orchestrator(state_store)
        orch._advance_scene_time(10)

        scene = state_store.get_scene()
        assert scene["time"]["weather"] == "fog"
        assert scene["time"]["hour"] == 10
        assert scene["time"]["minute"] == 40

    def test_missing_minute_field(self, state_store):
        """Missing minute field defaults to 0 (backward compatible)."""
        state_store.set_scene(
            location_id="test_loc",
            present_entity_ids=["player"],
            time={"hour": 14, "period": "afternoon"},
        )

        orch = self._make_orchestrator(state_store)
        result = orch._advance_scene_time(45)

        assert result["new_hour"] == 14
        assert result["new_minute"] == 45

    def test_no_scene_returns_empty(self, state_store):
        """No scene in DB returns empty dict without crashing."""
        orch = self._make_orchestrator(state_store)
        result = orch._advance_scene_time(10)
        assert result == {}

    def test_zero_minutes_returns_empty(self, state_store):
        """Zero minutes returns empty dict (no change)."""
        state_store.set_scene(
            location_id="test_loc",
            present_entity_ids=["player"],
            time={"hour": 12, "minute": 0, "period": "afternoon"},
        )

        orch = self._make_orchestrator(state_store)
        result = orch._advance_scene_time(0)
        assert result == {}

    def test_large_advance_wraps_correctly(self, state_store):
        """Large time advance wraps correctly past 24 hours."""
        state_store.set_scene(
            location_id="test_loc",
            present_entity_ids=["player"],
            time={"hour": 22, "minute": 0, "period": "night"},
        )

        orch = self._make_orchestrator(state_store)
        # Advance 3 hours
        result = orch._advance_scene_time(180)

        assert result["new_hour"] == 1
        assert result["new_minute"] == 0
        assert result["new_period"] == "night"

    def test_dawn_to_morning_transition(self, state_store):
        """Dawn to morning transition at hour 8."""
        state_store.set_scene(
            location_id="test_loc",
            present_entity_ids=["player"],
            time={"hour": 7, "minute": 45, "period": "dawn"},
        )

        orch = self._make_orchestrator(state_store)
        result = orch._advance_scene_time(20)

        assert result["new_hour"] == 8
        assert result["new_minute"] == 5
        assert result["old_period"] == "dawn"
        assert result["new_period"] == "morning"
        assert result["period_changed"] is True

    def test_evening_to_night_transition(self, state_store):
        """Evening to night transition at hour 20."""
        state_store.set_scene(
            location_id="test_loc",
            present_entity_ids=["player"],
            time={"hour": 19, "minute": 50, "period": "evening"},
        )

        orch = self._make_orchestrator(state_store)
        result = orch._advance_scene_time(15)

        assert result["new_hour"] == 20
        assert result["new_minute"] == 5
        assert result["old_period"] == "evening"
        assert result["new_period"] == "night"
        assert result["period_changed"] is True
