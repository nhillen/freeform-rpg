"""Stage S2: Engine Config Assembly.

Merges raw systems extractions into engine-compatible configuration files:
  - scenario_fragment.yaml   — partial scenario config (clocks, threads)
  - entity_templates.yaml    — NPC/entity stat block templates
  - calibration_preset.yaml  — difficulty presets and tuning
  - conditions_config.yaml   — status effect definitions
  - resolution_mapping.yaml  — action-to-resolution mapping
"""

import logging
from pathlib import Path
from typing import Optional

import yaml

from .models import SystemsExtractionManifest
from .utils import ensure_dir, write_stage_meta

logger = logging.getLogger(__name__)


class SystemsAssembler:
    """Assembles extracted mechanical data into engine config files."""

    def assemble(
        self,
        extraction: SystemsExtractionManifest,
        output_dir: str | Path,
    ) -> dict[str, Path]:
        """Assemble engine config files from extracted systems data.

        Args:
            extraction: Systems extraction manifest from Stage S1.
            output_dir: Directory to write assembled configs.

        Returns:
            Dict mapping config name to file path.
        """
        output_dir = Path(output_dir)
        ensure_dir(output_dir)

        outputs: dict[str, Path] = {}

        # Scenario fragment (clocks, threads)
        scenario = self._assemble_scenario(extraction)
        if scenario:
            path = output_dir / "scenario_fragment.yaml"
            self._write_yaml(path, scenario)
            outputs["scenario_fragment"] = path

        # Entity templates
        templates = self._assemble_entity_templates(extraction)
        if templates:
            path = output_dir / "entity_templates.yaml"
            self._write_yaml(path, templates)
            outputs["entity_templates"] = path

        # Calibration preset
        calibration = self._assemble_calibration(extraction)
        if calibration:
            path = output_dir / "calibration_preset.yaml"
            self._write_yaml(path, calibration)
            outputs["calibration_preset"] = path

        # Conditions config
        conditions = self._assemble_conditions(extraction)
        if conditions:
            path = output_dir / "conditions_config.yaml"
            self._write_yaml(path, conditions)
            outputs["conditions_config"] = path

        # Resolution mapping
        resolution = self._assemble_resolution(extraction)
        if resolution:
            path = output_dir / "resolution_mapping.yaml"
            self._write_yaml(path, resolution)
            outputs["resolution_mapping"] = path

        write_stage_meta(output_dir, {
            "stage": "systems_assemble",
            "status": "complete",
            "configs_generated": list(outputs.keys()),
        })

        logger.info("Assembled %d config files", len(outputs))
        return outputs

    def _assemble_scenario(
        self,
        extraction: SystemsExtractionManifest
    ) -> Optional[dict]:
        """Build a partial scenario config from clock/escalation data."""
        clocks_data = extraction.extractions.get("clocks", {})
        escalation_data = extraction.extractions.get("escalation", {})

        if not clocks_data and not escalation_data:
            return None

        scenario: dict = {}

        # Clocks
        clocks = clocks_data.get("clocks", [])
        if clocks:
            scenario["clocks"] = {}
            for clock in clocks:
                clock_id = clock.get("name", "unknown").lower().replace(" ", "_")
                scenario["clocks"][clock_id] = {
                    "name": clock.get("name", clock_id),
                    "value": clock.get("value", 0),
                    "max": clock.get("max", 10),
                }
                # Add triggers if available
                triggers = clocks_data.get("triggers", [])
                if triggers:
                    clock_triggers = {}
                    for t in triggers:
                        threshold = t.get("threshold")
                        if threshold is not None:
                            clock_triggers[str(threshold)] = t.get("effect", "")
                    if clock_triggers:
                        scenario["clocks"][clock_id]["triggers"] = clock_triggers

        # Escalation profiles
        esc_triggers = escalation_data.get("triggers", [])
        if esc_triggers:
            scenario["escalation_notes"] = esc_triggers

        return scenario

    def _assemble_entity_templates(
        self,
        extraction: SystemsExtractionManifest
    ) -> Optional[dict]:
        """Build entity templates from stat block data."""
        stats_data = extraction.extractions.get("entity_stats", {})
        if not stats_data:
            return None

        entities = stats_data.get("entities", [])
        if not entities:
            return None

        return {
            "templates": entities,
            "source": "pdf_ingest",
        }

    def _assemble_calibration(
        self,
        extraction: SystemsExtractionManifest
    ) -> Optional[dict]:
        """Build calibration preset from difficulty data."""
        cal_data = extraction.extractions.get("calibration", {})
        if not cal_data:
            return None

        return {
            "presets": cal_data.get("presets", []),
            "difficulty_modifiers": cal_data.get("difficulty_modifiers", []),
            "source": "pdf_ingest",
        }

    def _assemble_conditions(
        self,
        extraction: SystemsExtractionManifest
    ) -> Optional[dict]:
        """Build conditions config from extracted conditions."""
        cond_data = extraction.extractions.get("conditions", {})
        if not cond_data:
            return None

        conditions = cond_data.get("conditions", [])
        if not conditions:
            return None

        return {
            "conditions": {
                c.get("name", "unknown"): {
                    "effect": c.get("effect", ""),
                }
                for c in conditions
            },
            "source": "pdf_ingest",
        }

    def _assemble_resolution(
        self,
        extraction: SystemsExtractionManifest
    ) -> Optional[dict]:
        """Build resolution mapping from dice/action data."""
        res_data = extraction.extractions.get("resolution", {})
        action_data = extraction.extractions.get("action_types", {})

        if not res_data and not action_data:
            return None

        result: dict = {"source": "pdf_ingest"}

        if res_data:
            result["dice"] = res_data.get("dice", [])
            result["outcome_bands"] = res_data.get("outcome_bands", [])
            result["modifiers"] = res_data.get("modifiers", [])

        if action_data:
            result["action_types"] = action_data.get("action_types", [])

        return result

    def _write_yaml(self, path: Path, data: dict) -> None:
        """Write data as YAML file."""
        path.write_text(
            yaml.dump(data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
