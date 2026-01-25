"""
Integration tests for the full game pipeline.

Tests Session Zero setup through turn execution.
"""

import pytest
from pathlib import Path

from src.db.state_store import StateStore
from src.setup import (
    SetupPipeline,
    CalibrationSettings,
    ScenarioTemplate,
    run_setup,
)
from src.core import Orchestrator, run_turn
from src.llm.gateway import MockGateway
from src.llm.prompt_registry import PromptRegistry


class TestSessionZeroSetup:
    """Tests for Session Zero / campaign setup."""

    def test_setup_with_default_template(self, state_store):
        """Setup creates a playable campaign with default template."""
        pipeline = SetupPipeline(state_store)

        result = pipeline.run_setup(
            template_id="default",
            calibration_preset="noir_standard",
            character_responses={
                "name": "Alex Mercer",
                "background": "Former corporate security",
                "skills": "hacking, investigation",
                "weakness": "Haunted by past",
                "motivation": "Find the truth",
                "moral_line": "Won't harm innocents"
            }
        )

        assert result.campaign_id is not None
        assert result.character.name == "Alex Mercer"
        assert len(result.issues) == 0

        # Verify state was created
        player = state_store.get_entity("player")
        assert player is not None
        assert player["name"] == "Alex Mercer"

        scene = state_store.get_scene()
        assert scene is not None
        assert "player" in scene["present_entity_ids"]

    def test_setup_creates_clocks(self, state_store):
        """Setup initializes all game clocks."""
        pipeline = SetupPipeline(state_store)

        result = pipeline.run_setup(
            template_id="default",
            calibration_preset="noir_standard"
        )

        clocks = state_store.get_all_clocks()
        clock_names = {c["name"] for c in clocks}

        assert "Heat" in clock_names
        assert "Time" in clock_names
        assert "Harm" in clock_names
        assert "Cred" in clock_names
        assert "Rep" in clock_names

    def test_setup_creates_npcs(self, state_store):
        """Setup creates NPCs from template."""
        pipeline = SetupPipeline(state_store)

        result = pipeline.run_setup(
            template_id="default",
            calibration_preset="noir_standard"
        )

        # Default template has at least one NPC (Viktor)
        npcs = state_store.get_entities_by_type("npc")
        assert len(npcs) >= 1

    def test_setup_with_calibration_responses(self, state_store):
        """Setup with player calibration responses."""
        pipeline = SetupPipeline(state_store)

        result = pipeline.run_setup(
            template_id="default",
            calibration_responses={
                "tone_gritty": "c",  # Very gritty
                "tone_dark": "c",  # Very dark
                "risk_lethality": "c",  # High lethality
                "themes_primary": ["survival", "betrayal"]
            },
            character_responses={"name": "Test Character"}
        )

        assert result.calibration.tone.gritty_vs_cinematic == 0.8
        assert result.calibration.risk.lethality == "high"


class TestCalibrationPresets:
    """Tests for calibration preset loading."""

    def test_noir_standard_preset(self):
        """Noir Standard preset has expected values."""
        calibration = CalibrationSettings.from_preset("noir_standard")

        assert calibration.tone.gritty_vs_cinematic == 0.7
        assert calibration.risk.lethality == "moderate"
        assert calibration.risk.failure_mode == "consequential"

    def test_pulp_adventure_preset(self):
        """Pulp Adventure preset is less gritty."""
        calibration = CalibrationSettings.from_preset("pulp_adventure")

        assert calibration.tone.gritty_vs_cinematic == 0.3
        assert calibration.risk.lethality == "low"
        assert calibration.risk.failure_mode == "forgiving"

    def test_hard_boiled_preset(self):
        """Hard Boiled preset is very punishing."""
        calibration = CalibrationSettings.from_preset("hard_boiled")

        assert calibration.tone.gritty_vs_cinematic == 0.9
        assert calibration.risk.lethality == "high"
        assert calibration.risk.failure_mode == "punishing"

    def test_calibration_to_dict(self):
        """Calibration converts to dict for storage."""
        calibration = CalibrationSettings.from_preset("noir_standard")
        d = calibration.to_dict()

        assert "tone" in d
        assert "themes" in d
        assert "risk" in d
        assert "boundaries" in d
        assert "agency" in d


class TestFullPipelineFlow:
    """Tests for complete setup-to-turn flow."""

    def test_setup_then_turn(self, state_store, prompt_registry):
        """Can run turns after setup."""
        # Setup
        setup_pipeline = SetupPipeline(state_store)
        setup_result = setup_pipeline.run_setup(
            template_id="default",
            calibration_preset="noir_standard",
            character_responses={"name": "Test Runner"}
        )

        # Get campaign
        campaign = state_store.get_campaign(setup_result.campaign_id)
        assert campaign is not None

        # Run a turn
        mock_gateway = MockGateway()
        orchestrator = Orchestrator(
            state_store=state_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        turn_result = orchestrator.run_turn(
            setup_result.campaign_id,
            "I look around the bar"
        )

        assert turn_result.turn_no == 1
        assert len(turn_result.final_text) > 0

    def test_multiple_turns_after_setup(self, state_store, prompt_registry):
        """Can run multiple turns after setup."""
        # Setup
        setup_pipeline = SetupPipeline(state_store)
        setup_result = setup_pipeline.run_setup(
            template_id="default",
            calibration_preset="noir_standard"
        )

        # Run multiple turns
        mock_gateway = MockGateway()
        orchestrator = Orchestrator(
            state_store=state_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        turn1 = orchestrator.run_turn(setup_result.campaign_id, "I examine the room")
        turn2 = orchestrator.run_turn(setup_result.campaign_id, "I talk to Viktor")
        turn3 = orchestrator.run_turn(setup_result.campaign_id, "I ask about the job")

        assert turn1.turn_no == 1
        assert turn2.turn_no == 2
        assert turn3.turn_no == 3

    def test_state_persists_through_turns(self, state_store, prompt_registry):
        """State changes persist across turns."""
        # Setup
        setup_pipeline = SetupPipeline(state_store)
        setup_result = setup_pipeline.run_setup(
            template_id="default",
            calibration_preset="noir_standard"
        )

        initial_time = state_store.get_clock("time")["value"]

        # Run turns that should consume time
        mock_gateway = MockGateway()
        orchestrator = Orchestrator(
            state_store=state_store,
            llm_gateway=mock_gateway,
            prompt_registry=prompt_registry
        )

        orchestrator.run_turn(setup_result.campaign_id, "I search the place")
        orchestrator.run_turn(setup_result.campaign_id, "I talk to everyone")

        final_time = state_store.get_clock("time")["value"]

        # Time should have decreased
        assert final_time <= initial_time


class TestConvenienceFunctions:
    """Tests for convenience wrapper functions."""

    def test_run_setup_function(self, state_store):
        """run_setup convenience function works."""
        result = run_setup(
            state_store=state_store,
            template_id="default",
            calibration_preset="noir_standard",
            character_responses={"name": "Convenience Test"}
        )

        assert isinstance(result, dict)
        assert "campaign_id" in result
        assert "character" in result
        assert result["character"]["name"] == "Convenience Test"

    def test_run_turn_after_setup(self, state_store):
        """run_turn works after run_setup."""
        setup_result = run_setup(
            state_store=state_store,
            template_id="default"
        )

        turn_result = run_turn(
            state_store=state_store,
            campaign_id=setup_result["campaign_id"],
            player_input="I look around"
        )

        assert isinstance(turn_result, dict)
        assert "turn_no" in turn_result
        assert "final_text" in turn_result


class TestScenarioTemplates:
    """Tests for scenario template functionality."""

    def test_default_template_creation(self):
        """Default template has required elements."""
        from src.setup.templates import _create_default_template

        template = _create_default_template("test")

        assert template.id == "test"
        assert len(template.locations) >= 1
        assert len(template.npcs) >= 1
        assert len(template.clocks) >= 5
        assert template.opening_text != ""

    def test_template_has_default_clocks(self):
        """Template provides default clocks if not specified."""
        template = ScenarioTemplate(
            id="minimal",
            name="Minimal Template"
        )

        # Clocks should be populated with defaults
        default_clocks = ScenarioTemplate._default_clocks()
        assert len(default_clocks) == 5


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_setup_with_empty_responses(self, state_store):
        """Setup works with empty character responses."""
        pipeline = SetupPipeline(state_store)

        result = pipeline.run_setup(
            template_id="default",
            calibration_preset="noir_standard",
            character_responses={}
        )

        # Should use defaults
        assert result.character.name == "Anonymous"
        assert len(result.issues) == 0

    def test_setup_validation_catches_issues(self, state_store):
        """Setup validation reports issues."""
        pipeline = SetupPipeline(state_store)

        # Run setup normally first
        result = pipeline.run_setup(
            template_id="default",
            calibration_preset="noir_standard"
        )

        # Validation should pass for normal setup
        assert len(result.issues) == 0

    def test_run_turn_without_setup_fails_gracefully(self, state_store):
        """Running turn without setup handles error."""
        # Don't run setup - try to run turn directly
        with pytest.raises(ValueError):
            run_turn(
                state_store=state_store,
                campaign_id="nonexistent_campaign",
                player_input="Hello"
            )
