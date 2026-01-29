"""Tests for Stage S3: Systems Validation."""

import pytest
import yaml
from pathlib import Path

from src.ingest.models import EntityEntry, EntityRegistry
from src.ingest.systems_validate import SystemsValidator, SystemsValidationReport


def _write_config(configs_dir, name, data):
    configs_dir.mkdir(parents=True, exist_ok=True)
    (configs_dir / f"{name}.yaml").write_text(yaml.dump(data))


class TestSystemsValidator:
    def test_valid_configs_pass(self, tmp_path):
        configs_dir = tmp_path / "configs"
        _write_config(configs_dir, "scenario_fragment", {
            "clocks": {
                "heat": {"name": "Heat", "value": 0, "max": 10},
                "harm": {"name": "Harm", "value": 0, "max": 4},
            }
        })
        _write_config(configs_dir, "resolution_mapping", {
            "dice": ["2d6"],
            "outcome_bands": [
                {"range": "10+", "label": "critical"},
                {"range": "7-9", "label": "mixed"},
                {"range": "2-6", "label": "failure"},
            ],
        })

        validator = SystemsValidator()
        report = validator.validate(configs_dir)

        assert report.valid is True
        assert len(report.errors) == 0

    def test_invalid_clock_max(self, tmp_path):
        configs_dir = tmp_path / "configs"
        _write_config(configs_dir, "scenario_fragment", {
            "clocks": {
                "broken": {"name": "Broken", "value": 0, "max": 0},
            }
        })

        validator = SystemsValidator()
        report = validator.validate(configs_dir)

        assert any("max must be > 0" in e for e in report.errors)

    def test_clock_trigger_out_of_range(self, tmp_path):
        configs_dir = tmp_path / "configs"
        _write_config(configs_dir, "scenario_fragment", {
            "clocks": {
                "heat": {
                    "name": "Heat", "value": 0, "max": 10,
                    "triggers": {"15": "Beyond max"},
                },
            }
        })

        validator = SystemsValidator()
        report = validator.validate(configs_dir)

        assert any("outside range" in w for w in report.warnings)

    def test_outcome_band_gap_warning(self, tmp_path):
        configs_dir = tmp_path / "configs"
        _write_config(configs_dir, "resolution_mapping", {
            "outcome_bands": [
                {"range": "10+", "label": "critical"},
                {"range": "2-5", "label": "failure"},
                # Gap: 6-9 is missing
            ],
        })

        validator = SystemsValidator()
        report = validator.validate(configs_dir)

        assert any("Gap" in w for w in report.warnings)

    def test_condition_missing_effect(self, tmp_path):
        configs_dir = tmp_path / "configs"
        _write_config(configs_dir, "conditions_config", {
            "conditions": {
                "broken": {},
            }
        })

        validator = SystemsValidator()
        report = validator.validate(configs_dir)

        assert any("missing effect" in w for w in report.warnings)

    def test_cross_validation_with_lore(self, tmp_path):
        configs_dir = tmp_path / "configs"
        _write_config(configs_dir, "entity_templates", {
            "templates": [
                {"name": "Viktor Kozlov", "threat_level": "high"},
                {"name": "Unknown Entity", "threat_level": "low"},
            ]
        })

        registry = EntityRegistry()
        registry.add(EntityEntry(
            id="viktor_kozlov", name="Viktor Kozlov", entity_type="npc"
        ))

        validator = SystemsValidator()
        report = validator.validate(configs_dir, entity_registry=registry)

        # Viktor should match; Unknown Entity should warn
        assert any("Unknown Entity" in w for w in report.warnings)

    def test_circular_escalation_detection(self, tmp_path):
        configs_dir = tmp_path / "configs"
        _write_config(configs_dir, "scenario_fragment", {
            "clocks": {
                "heat": {
                    "name": "Heat", "value": 0, "max": 10,
                    "triggers": {"5": "Increase harm clock"},
                },
                "harm": {
                    "name": "Harm", "value": 0, "max": 4,
                    "triggers": {"3": "Increase heat clock"},
                },
            }
        })

        validator = SystemsValidator()
        report = validator.validate(configs_dir)

        assert any("circular" in w.lower() for w in report.warnings)

    def test_empty_configs_dir(self, tmp_path):
        configs_dir = tmp_path / "empty"
        configs_dir.mkdir()

        validator = SystemsValidator()
        report = validator.validate(configs_dir)

        assert report.valid is True
        assert any("No config files" in w for w in report.warnings)
