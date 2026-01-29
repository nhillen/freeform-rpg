"""System extraction configuration loader.

Loads and merges extraction configs with inheritance:
  _base.yaml -> system.yaml -> pack/extraction.yaml

Provides system-specific patterns for extraction while maintaining
the generic structural detection philosophy.
"""

import re
from pathlib import Path
from typing import Optional

import yaml

from .models import (
    ExtractionConfig,
    ExtractionHints,
    GuidanceConfig,
    GuidancePattern,
    HealthConfig,
    MechanicalIndicator,
    RatingScale,
    SectionPattern,
    StatBlockHints,
)


# Default location for system configs
SYSTEMS_DIR = Path(__file__).parent.parent.parent / "systems"


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override dict into base dict.

    - Dicts are merged recursively
    - Lists are concatenated (override appended to base)
    - Scalars are replaced by override
    """
    result = base.copy()

    for key, value in override.items():
        if key in result:
            base_val = result[key]
            if isinstance(base_val, dict) and isinstance(value, dict):
                result[key] = deep_merge(base_val, value)
            elif isinstance(base_val, list) and isinstance(value, list):
                # Concatenate lists, avoiding duplicates for simple values
                seen = set()
                merged = []
                for item in base_val + value:
                    if isinstance(item, dict):
                        merged.append(item)
                    elif item not in seen:
                        seen.add(item)
                        merged.append(item)
                result[key] = merged
            else:
                result[key] = value
        else:
            result[key] = value

    return result


def load_yaml_file(path: Path) -> dict:
    """Load a YAML file, returning empty dict if not found."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def parse_mechanical_indicators(raw: list[dict]) -> list[MechanicalIndicator]:
    """Parse raw indicator dicts into MechanicalIndicator objects."""
    indicators = []
    for item in raw:
        if isinstance(item, dict) and "pattern" in item:
            indicators.append(MechanicalIndicator(
                pattern=item["pattern"],
                meaning=item.get("meaning", "unknown"),
                confidence=item.get("confidence", 0.5),
            ))
    return indicators


def parse_section_patterns(raw: dict) -> dict[str, SectionPattern]:
    """Parse raw section pattern dicts into SectionPattern objects."""
    patterns = {}
    for name, data in raw.items():
        if isinstance(data, dict) and "header_pattern" in data:
            patterns[name] = SectionPattern(
                header_pattern=data["header_pattern"],
                content_type=data.get("content_type", "unknown"),
                rating_type=data.get("rating_type", "dots"),
                confidence=data.get("confidence", 0.7),
            )
    return patterns


def parse_rating_scale(raw: dict) -> RatingScale:
    """Parse a single rating scale dict."""
    return RatingScale(
        symbol=raw.get("symbol", ""),
        empty_symbol=raw.get("empty_symbol", ""),
        max=raw.get("max", 5),
        symbols=raw.get("symbols", []),
        filled=raw.get("filled", []),
        empty=raw.get("empty", []),
        typical_max=raw.get("typical_max", 5),
        range=tuple(raw.get("range", [1, 10])),
        default=raw.get("default", 5),
        descriptions=raw.get("descriptions", {}),
        applies_to=raw.get("applies_to", []),
    )


def parse_rating_scales(raw: dict) -> dict[str, RatingScale]:
    """Parse raw rating scale dicts into RatingScale objects."""
    scales = {}
    for name, data in raw.items():
        if isinstance(data, dict):
            scales[name] = parse_rating_scale(data)
    return scales


def parse_stat_block_hints(raw: dict) -> StatBlockHints:
    """Parse stat block hints."""
    return StatBlockHints(
        npc_format=raw.get("npc_format", ""),
        markers=raw.get("markers", []),
    )


def parse_health_config(raw: dict) -> HealthConfig:
    """Parse health track configuration."""
    return HealthConfig(
        track_type=raw.get("track_type", "levels"),
        levels=raw.get("levels", []),
        damage_types=raw.get("damage_types", []),
    )


def parse_guidance_patterns(raw: list[dict]) -> list[GuidancePattern]:
    """Parse raw guidance pattern dicts into GuidancePattern objects."""
    patterns = []
    for item in raw:
        if isinstance(item, dict) and "pattern" in item:
            patterns.append(GuidancePattern(
                pattern=item["pattern"],
                meaning=item.get("meaning", "unknown"),
                confidence=item.get("confidence", 0.5),
            ))
    return patterns


def parse_guidance_config(raw: dict) -> GuidanceConfig:
    """Parse GM guidance extraction config."""
    return GuidanceConfig(
        chapter_indicators=raw.get("chapter_indicators", []),
        content_patterns=parse_guidance_patterns(raw.get("content_patterns", [])),
        categories=raw.get("categories", []),
    )


def parse_extraction_hints(raw: dict) -> ExtractionHints:
    """Parse the extraction section of a config."""
    if not raw:
        return ExtractionHints()

    return ExtractionHints(
        mechanical_indicators=parse_mechanical_indicators(
            raw.get("mechanical_indicators", [])
        ),
        section_patterns=parse_section_patterns(
            raw.get("section_patterns", {})
        ),
        rating_scales=parse_rating_scales(
            raw.get("rating_scales", {})
        ),
        stat_blocks=parse_stat_block_hints(
            raw.get("stat_blocks", {})
        ),
        health=parse_health_config(
            raw.get("health", {})
        ),
        gm_guidance=parse_guidance_config(
            raw.get("gm_guidance", {})
        ),
    )


def dict_to_extraction_config(data: dict, sources: list[str]) -> ExtractionConfig:
    """Convert merged dict to ExtractionConfig object."""
    return ExtractionConfig(
        id=data.get("id", "_base"),
        name=data.get("name", "Unknown System"),
        inherits=data.get("inherits"),
        extraction=parse_extraction_hints(data.get("extraction", {})),
        sources=sources,
    )


def load_system_config_raw(system_id: str, systems_dir: Path = SYSTEMS_DIR) -> dict:
    """Load raw system config with inheritance resolution.

    Returns merged dict from _base -> system.
    """
    # Always start with _base
    base_path = systems_dir / "_base.yaml"
    merged = load_yaml_file(base_path)
    sources = []
    if base_path.exists():
        sources.append(str(base_path))

    # If requesting specific system (not _base), load and merge
    if system_id and system_id != "_base":
        system_path = systems_dir / f"{system_id}.yaml"
        system_data = load_yaml_file(system_path)

        if system_data:
            sources.append(str(system_path))

            # Check for inheritance chain (e.g., mage_ascension -> world_of_darkness -> _base)
            inherits = system_data.get("inherits")
            if inherits and inherits != "_base":
                parent_data = load_system_config_raw(inherits, systems_dir)
                merged = deep_merge(merged, parent_data)

            merged = deep_merge(merged, system_data)

    return merged, sources


def load_extraction_config(
    pack_path: Optional[Path] = None,
    system_hint: Optional[str] = None,
    systems_dir: Path = SYSTEMS_DIR,
) -> ExtractionConfig:
    """Load merged extraction config: _base -> system -> pack.

    Args:
        pack_path: Path to content pack directory (optional)
        system_hint: System ID to use (e.g., "world_of_darkness")
        systems_dir: Directory containing system configs

    Returns:
        ExtractionConfig with merged patterns from all sources

    Priority:
        1. Pack's extraction.yaml overrides take precedence
        2. System config (from pack.yaml's system field or system_hint)
        3. _base.yaml provides defaults
    """
    # Determine system ID
    system_id = system_hint

    if pack_path and not system_id:
        # Check pack.yaml for system field
        pack_yaml_path = pack_path / "pack.yaml"
        if pack_yaml_path.exists():
            pack_yaml = load_yaml_file(pack_yaml_path)
            system_id = pack_yaml.get("system")

    # Load base + system config
    merged, sources = load_system_config_raw(system_id, systems_dir)

    # Load pack extraction overrides
    if pack_path:
        pack_extraction_path = pack_path / "extraction.yaml"
        if pack_extraction_path.exists():
            pack_extraction = load_yaml_file(pack_extraction_path)
            sources.append(str(pack_extraction_path))

            # Check if pack extends a different system
            extends = pack_extraction.get("extends")
            if extends and extends != system_id:
                # Re-load with the extended system as base
                merged, base_sources = load_system_config_raw(extends, systems_dir)
                sources = base_sources + [str(pack_extraction_path)]

            merged = deep_merge(merged, pack_extraction)

    return dict_to_extraction_config(merged, sources)


def compile_patterns(config: ExtractionConfig) -> dict[str, list[re.Pattern]]:
    """Compile regex patterns from config for efficient matching.

    Returns dict with:
        - mechanical: Compiled patterns for mechanical indicators
        - sections: Dict of section_name -> compiled header pattern
        - guidance: Compiled patterns for GM guidance detection
    """
    compiled = {
        "mechanical": [],
        "sections": {},
        "guidance": [],
        "stat_blocks": [],
    }

    # Compile mechanical indicators
    for indicator in config.extraction.mechanical_indicators:
        try:
            compiled["mechanical"].append({
                "pattern": re.compile(indicator.pattern, re.IGNORECASE | re.MULTILINE),
                "meaning": indicator.meaning,
                "confidence": indicator.confidence,
            })
        except re.error:
            pass  # Skip invalid patterns

    # Compile section patterns
    for name, section in config.extraction.section_patterns.items():
        try:
            compiled["sections"][name] = {
                "pattern": re.compile(section.header_pattern, re.IGNORECASE),
                "content_type": section.content_type,
                "rating_type": section.rating_type,
                "confidence": section.confidence,
            }
        except re.error:
            pass

    # Compile guidance patterns
    for pattern in config.extraction.gm_guidance.content_patterns:
        try:
            compiled["guidance"].append({
                "pattern": re.compile(pattern.pattern, re.IGNORECASE),
                "meaning": pattern.meaning,
                "confidence": pattern.confidence,
            })
        except re.error:
            pass

    # Compile stat block markers
    for marker in config.extraction.stat_blocks.markers:
        try:
            compiled["stat_blocks"].append(re.compile(marker, re.IGNORECASE))
        except re.error:
            pass

    return compiled


def get_available_systems(systems_dir: Path = SYSTEMS_DIR) -> list[str]:
    """List available system configs (excluding _base)."""
    if not systems_dir.exists():
        return []

    systems = []
    for path in systems_dir.glob("*.yaml"):
        if path.stem != "_base":
            systems.append(path.stem)

    return sorted(systems)
