"""Setup module for game initialization and scenario loading."""

from .scenario_loader import ScenarioLoader, load_scenario
from .calibration import (
    CalibrationSettings,
    ToneSettings,
    ThemeSettings,
    RiskSettings,
    BoundarySettings,
    AgencySettings,
)
from .pipeline import SetupPipeline, SetupResult, CharacterData, run_setup
from .templates import ScenarioTemplate, load_template, list_templates

__all__ = [
    # Scenario loader
    "ScenarioLoader",
    "load_scenario",
    # Calibration
    "CalibrationSettings",
    "ToneSettings",
    "ThemeSettings",
    "RiskSettings",
    "BoundarySettings",
    "AgencySettings",
    # Pipeline
    "SetupPipeline",
    "SetupResult",
    "CharacterData",
    "run_setup",
    # Templates
    "ScenarioTemplate",
    "load_template",
    "list_templates",
]
