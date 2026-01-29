"""Stage S3: Systems Schema Validation.

Validates assembled engine config files for:
  1. Clock ID consistency and trigger range validity
  2. Outcome band coverage (no gaps in resolution ranges)
  3. Entity template completeness
  4. Circular escalation detection
  5. Cross-validation with lore entities
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .models import EntityRegistry
from .utils import write_stage_meta

logger = logging.getLogger(__name__)


@dataclass
class SystemsValidationReport:
    """Validation results for systems configs."""
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


class SystemsValidator:
    """Validates assembled systems configuration files."""

    def validate(
        self,
        configs_dir: str | Path,
        entity_registry: Optional[EntityRegistry] = None,
        output_dir: Optional[str | Path] = None,
    ) -> SystemsValidationReport:
        """Run full systems validation.

        Args:
            configs_dir: Directory containing assembled config YAML files.
            entity_registry: Optional entity registry for cross-validation.
            output_dir: Optional directory to write validation report.

        Returns:
            SystemsValidationReport with results.
        """
        configs_dir = Path(configs_dir)
        report = SystemsValidationReport()

        # Load all config files
        configs = self._load_configs(configs_dir, report)

        # Validate clocks
        if "scenario_fragment" in configs:
            self._validate_clocks(configs["scenario_fragment"], report)

        # Validate resolution
        if "resolution_mapping" in configs:
            self._validate_resolution(configs["resolution_mapping"], report)

        # Validate entity templates
        if "entity_templates" in configs:
            self._validate_entity_templates(configs["entity_templates"], report)

        # Validate conditions
        if "conditions_config" in configs:
            self._validate_conditions(configs["conditions_config"], report)

        # Cross-validate with lore
        if entity_registry:
            self._cross_validate_lore(configs, entity_registry, report)

        # Check for circular escalation
        if "scenario_fragment" in configs:
            self._check_circular_escalation(configs["scenario_fragment"], report)

        report.stats["configs_validated"] = len(configs)

        if output_dir:
            write_stage_meta(Path(output_dir), {
                "stage": "systems_validate",
                "status": "complete" if report.valid else "failed",
                "valid": report.valid,
                "errors": report.errors,
                "warnings": report.warnings,
            })

        log_fn = logger.info if report.valid else logger.warning
        log_fn(
            "Systems validation %s: %d errors, %d warnings",
            "PASSED" if report.valid else "FAILED",
            len(report.errors),
            len(report.warnings),
        )
        return report

    def _load_configs(
        self,
        configs_dir: Path,
        report: SystemsValidationReport
    ) -> dict[str, dict]:
        """Load all YAML config files."""
        configs: dict[str, dict] = {}
        yaml_files = list(configs_dir.glob("*.yaml"))

        if not yaml_files:
            report.add_warning("No config files found in configs directory")
            return configs

        for path in yaml_files:
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    configs[path.stem] = data
                else:
                    report.add_warning(f"{path.name}: not a valid YAML mapping")
            except Exception as e:
                report.add_error(f"Failed to load {path.name}: {e}")

        return configs

    def _validate_clocks(
        self,
        scenario: dict,
        report: SystemsValidationReport
    ) -> None:
        """Validate clock definitions and trigger ranges."""
        clocks = scenario.get("clocks", {})
        if not clocks:
            return

        for clock_id, clock_def in clocks.items():
            if not isinstance(clock_def, dict):
                report.add_error(f"Clock '{clock_id}': invalid definition")
                continue

            max_val = clock_def.get("max", 0)
            value = clock_def.get("value", 0)

            if max_val <= 0:
                report.add_error(f"Clock '{clock_id}': max must be > 0")

            if value < 0:
                report.add_error(f"Clock '{clock_id}': value cannot be negative")

            if value > max_val:
                report.add_warning(
                    f"Clock '{clock_id}': initial value ({value}) > max ({max_val})"
                )

            # Validate triggers
            triggers = clock_def.get("triggers", {})
            for threshold_str, effect in triggers.items():
                try:
                    threshold = int(threshold_str)
                    if threshold < 0 or threshold > max_val:
                        report.add_warning(
                            f"Clock '{clock_id}': trigger at {threshold} "
                            f"outside range 0-{max_val}"
                        )
                except ValueError:
                    report.add_error(
                        f"Clock '{clock_id}': invalid trigger threshold '{threshold_str}'"
                    )

    def _validate_resolution(
        self,
        resolution: dict,
        report: SystemsValidationReport
    ) -> None:
        """Validate resolution mechanics and outcome bands."""
        outcome_bands = resolution.get("outcome_bands", [])
        if not outcome_bands:
            report.add_warning("Resolution mapping has no outcome bands defined")
            return

        # Check for gaps in outcome bands
        ranges_found = []
        for band in outcome_bands:
            range_str = band.get("range", "")
            if "+" in range_str:
                try:
                    low = int(range_str.replace("+", ""))
                    ranges_found.append((low, 99))
                except ValueError:
                    pass
            elif "-" in range_str:
                parts = range_str.split("-")
                try:
                    low = int(parts[0])
                    high = int(parts[1])
                    ranges_found.append((low, high))
                except (ValueError, IndexError):
                    pass

        if ranges_found:
            ranges_found.sort()
            # Check for gaps between 2 and the highest range
            # (2 is the minimum 2d6 result)
            for i in range(len(ranges_found) - 1):
                current_high = ranges_found[i][1]
                next_low = ranges_found[i + 1][0]
                if next_low > current_high + 1:
                    report.add_warning(
                        f"Gap in outcome bands: {current_high + 1} to {next_low - 1}"
                    )

    def _validate_entity_templates(
        self,
        templates: dict,
        report: SystemsValidationReport
    ) -> None:
        """Validate entity template completeness."""
        entities = templates.get("templates", [])
        for entity in entities:
            if not isinstance(entity, dict):
                report.add_warning("Entity template is not a mapping")
                continue
            if not entity.get("threat_level"):
                report.add_warning("Entity template missing threat_level")

    def _validate_conditions(
        self,
        conditions_config: dict,
        report: SystemsValidationReport
    ) -> None:
        """Validate condition definitions."""
        conditions = conditions_config.get("conditions", {})
        for name, cond_def in conditions.items():
            if not isinstance(cond_def, dict):
                report.add_warning(f"Condition '{name}': invalid definition")
                continue
            if not cond_def.get("effect"):
                report.add_warning(f"Condition '{name}': missing effect description")

    def _cross_validate_lore(
        self,
        configs: dict[str, dict],
        registry: EntityRegistry,
        report: SystemsValidationReport
    ) -> None:
        """Cross-validate systems data with lore entity registry."""
        templates = configs.get("entity_templates", {})
        template_entities = templates.get("templates", [])

        # Check that referenced entities exist in lore
        for tmpl in template_entities:
            name = tmpl.get("name", "")
            if name and not registry.get(name.lower().replace(" ", "_")):
                report.add_warning(
                    f"Entity template '{name}' has no matching lore entry"
                )

    def _check_circular_escalation(
        self,
        scenario: dict,
        report: SystemsValidationReport
    ) -> None:
        """Check for circular escalation chains."""
        clocks = scenario.get("clocks", {})

        # Build a simple dependency graph from trigger effects
        # that reference other clocks
        clock_ids = set(clocks.keys())
        dependencies: dict[str, set[str]] = {cid: set() for cid in clock_ids}

        for clock_id, clock_def in clocks.items():
            triggers = clock_def.get("triggers", {})
            for _, effect in triggers.items():
                effect_lower = str(effect).lower()
                for other_id in clock_ids:
                    if other_id != clock_id and other_id in effect_lower:
                        dependencies[clock_id].add(other_id)

        # Detect cycles using DFS
        visited: set[str] = set()
        in_stack: set[str] = set()

        def has_cycle(node: str) -> bool:
            visited.add(node)
            in_stack.add(node)
            for neighbor in dependencies.get(node, set()):
                if neighbor in in_stack:
                    return True
                if neighbor not in visited and has_cycle(neighbor):
                    return True
            in_stack.discard(node)
            return False

        for clock_id in clock_ids:
            if clock_id not in visited:
                if has_cycle(clock_id):
                    report.add_warning(
                        f"Potential circular escalation detected involving clock '{clock_id}'"
                    )
                    break
