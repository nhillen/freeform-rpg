"""Tests for Stage S2: Systems Assembly."""

import pytest
import yaml
from pathlib import Path

from src.ingest.models import SystemsExtractionManifest
from src.ingest.systems_assemble import SystemsAssembler


def _make_extraction():
    """Create a systems extraction manifest with test data."""
    return SystemsExtractionManifest(
        extractions={
            "resolution": {
                "dice": ["2d6"],
                "outcome_bands": [
                    {"range": "10+", "label": "critical success"},
                    {"range": "7-9", "label": "mixed success"},
                    {"range": "2-6", "label": "failure"},
                ],
                "modifiers": [
                    {"value": "+2", "target": "stealth"},
                ],
            },
            "clocks": {
                "clocks": [
                    {"name": "Heat", "value": 0, "max": 10},
                    {"name": "Harm", "value": 0, "max": 4},
                ],
                "triggers": [
                    {"threshold": 5, "effect": "Police response escalates"},
                    {"threshold": 10, "effect": "SWAT deployed"},
                ],
            },
            "conditions": {
                "conditions": [
                    {"name": "exposed", "effect": "Enemies can attack freely"},
                    {"name": "hidden", "effect": "Cannot be targeted"},
                ],
            },
            "action_types": {
                "action_types": [
                    {"name": "examine", "description": "Look at something"},
                    {"name": "fight", "description": "Engage in combat"},
                ],
            },
        },
        source_segments=["seg_rules", "seg_clocks"],
    )


class TestSystemsAssembler:
    def test_assemble_creates_files(self, tmp_path):
        extraction = _make_extraction()

        assembler = SystemsAssembler()
        outputs = assembler.assemble(extraction, tmp_path / "output")

        assert len(outputs) > 0
        for name, path in outputs.items():
            assert path.exists()

    def test_scenario_fragment(self, tmp_path):
        extraction = _make_extraction()

        assembler = SystemsAssembler()
        outputs = assembler.assemble(extraction, tmp_path / "output")

        assert "scenario_fragment" in outputs
        data = yaml.safe_load(outputs["scenario_fragment"].read_text())
        assert "clocks" in data
        assert "heat" in data["clocks"]
        assert data["clocks"]["heat"]["max"] == 10

    def test_conditions_config(self, tmp_path):
        extraction = _make_extraction()

        assembler = SystemsAssembler()
        outputs = assembler.assemble(extraction, tmp_path / "output")

        assert "conditions_config" in outputs
        data = yaml.safe_load(outputs["conditions_config"].read_text())
        assert "conditions" in data
        assert "exposed" in data["conditions"]

    def test_resolution_mapping(self, tmp_path):
        extraction = _make_extraction()

        assembler = SystemsAssembler()
        outputs = assembler.assemble(extraction, tmp_path / "output")

        assert "resolution_mapping" in outputs
        data = yaml.safe_load(outputs["resolution_mapping"].read_text())
        assert "2d6" in data.get("dice", [])
        assert len(data.get("outcome_bands", [])) == 3

    def test_empty_extraction(self, tmp_path):
        extraction = SystemsExtractionManifest()

        assembler = SystemsAssembler()
        outputs = assembler.assemble(extraction, tmp_path / "output")

        assert len(outputs) == 0
