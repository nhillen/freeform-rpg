"""
Calibration Settings - Tone, themes, risk, boundaries, and agency configuration.

These settings inform how the game plays: narrative style, consequence severity,
content boundaries, and player agency levels.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ToneSettings:
    """Tone spectrum settings."""
    gritty_vs_cinematic: float = 0.5  # 0=cinematic, 1=gritty
    dark_vs_light: float = 0.5  # 0=light/comedic, 1=dark
    moral_complexity: float = 0.5  # 0=clear good/evil, 1=gray
    slow_burn_vs_action: float = 0.5  # 0=action-heavy, 1=methodical

    @classmethod
    def from_responses(cls, responses: dict) -> "ToneSettings":
        """Create from player question responses."""
        # Map A/B/C answers to numeric values
        answer_map = {"a": 0.2, "b": 0.5, "c": 0.8}

        gritty = answer_map.get(responses.get("tone_gritty", "b"), 0.5)
        dark = answer_map.get(responses.get("tone_dark", "b"), 0.5)
        moral = answer_map.get(responses.get("tone_moral", "b"), 0.5)
        pacing = answer_map.get(responses.get("tone_pacing", "b"), 0.5)

        return cls(
            gritty_vs_cinematic=gritty,
            dark_vs_light=dark,
            moral_complexity=moral,
            slow_burn_vs_action=pacing
        )

    def to_dict(self) -> dict:
        return {
            "gritty_vs_cinematic": self.gritty_vs_cinematic,
            "dark_vs_light": self.dark_vs_light,
            "moral_complexity": self.moral_complexity,
            "slow_burn_vs_action": self.slow_burn_vs_action
        }


@dataclass
class ThemeSettings:
    """Theme configuration."""
    primary: list[str] = field(default_factory=list)
    secondary: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)

    @classmethod
    def from_responses(cls, responses: dict) -> "ThemeSettings":
        """Create from player theme selections."""
        primary = responses.get("themes_primary", [])
        if isinstance(primary, str):
            primary = [primary]

        secondary = responses.get("themes_secondary", [])
        if isinstance(secondary, str):
            secondary = [secondary]

        avoid = responses.get("themes_avoid", [])
        if isinstance(avoid, str):
            avoid = [avoid]

        return cls(primary=primary, secondary=secondary, avoid=avoid)

    def to_dict(self) -> dict:
        return {
            "primary": self.primary,
            "secondary": self.secondary,
            "avoid": self.avoid
        }


@dataclass
class RiskSettings:
    """Risk and lethality configuration."""
    lethality: str = "moderate"  # low, moderate, high, brutal
    failure_mode: str = "consequential"  # forgiving, consequential, punishing
    permanence: str = "meaningful"  # soft, meaningful, hard
    plot_armor: str = "thin"  # none, thin, thick

    @classmethod
    def from_responses(cls, responses: dict) -> "RiskSettings":
        """Create from player risk question responses."""
        lethality_map = {"a": "low", "b": "moderate", "c": "high"}
        failure_map = {"a": "forgiving", "b": "consequential", "c": "punishing"}

        return cls(
            lethality=lethality_map.get(responses.get("risk_lethality", "b"), "moderate"),
            failure_mode=failure_map.get(responses.get("risk_failure", "b"), "consequential"),
            permanence=responses.get("risk_permanence", "meaningful"),
            plot_armor=responses.get("risk_armor", "thin")
        )

    def to_dict(self) -> dict:
        return {
            "lethality": self.lethality,
            "failure_mode": self.failure_mode,
            "permanence": self.permanence,
            "plot_armor": self.plot_armor
        }


@dataclass
class BoundarySettings:
    """Content boundary configuration (lines and veils)."""
    lines: list[str] = field(default_factory=list)  # Hard limits - never include
    veils: list[str] = field(default_factory=list)  # Soft limits - fade to black
    explore: list[str] = field(default_factory=list)  # Explicitly included themes

    # Default lines that are always enforced
    DEFAULT_LINES = [
        "sexual_violence",
        "child_harm",
        "real_hate_symbols"
    ]

    def __post_init__(self):
        # Ensure defaults are always present
        for line in self.DEFAULT_LINES:
            if line not in self.lines:
                self.lines.append(line)

    @classmethod
    def from_responses(cls, responses: dict) -> "BoundarySettings":
        """Create from player boundary selections."""
        lines = list(cls.DEFAULT_LINES)  # Start with defaults
        lines.extend(responses.get("content_lines", []))

        veils = responses.get("content_veils", [])
        explore = responses.get("content_explore", [])

        return cls(lines=lines, veils=veils, explore=explore)

    def to_dict(self) -> dict:
        return {
            "lines": self.lines,
            "veils": self.veils,
            "explore": self.explore
        }


@dataclass
class AgencySettings:
    """Player agency configuration."""
    structure: str = "guided"  # sandbox, guided, linear
    world_plasticity: str = "responsive"  # fixed, responsive, malleable
    world_agency: str = "active"  # passive, active, aggressive
    ambiguity_handling: str = "interpret"  # clarify, interpret, both

    @classmethod
    def from_responses(cls, responses: dict) -> "AgencySettings":
        """Create from player agency question responses."""
        structure_map = {"a": "linear", "b": "guided", "c": "sandbox"}

        return cls(
            structure=structure_map.get(responses.get("agency_structure", "b"), "guided"),
            world_plasticity=responses.get("agency_plasticity", "responsive"),
            world_agency=responses.get("agency_world", "active"),
            ambiguity_handling=responses.get("agency_ambiguity", "interpret")
        )

    def to_dict(self) -> dict:
        return {
            "structure": self.structure,
            "world_plasticity": self.world_plasticity,
            "world_agency": self.world_agency,
            "ambiguity_handling": self.ambiguity_handling
        }


@dataclass
class CalibrationSettings:
    """Complete calibration settings for a campaign."""
    tone: ToneSettings = field(default_factory=ToneSettings)
    themes: ThemeSettings = field(default_factory=ThemeSettings)
    risk: RiskSettings = field(default_factory=RiskSettings)
    boundaries: BoundarySettings = field(default_factory=BoundarySettings)
    agency: AgencySettings = field(default_factory=AgencySettings)

    @classmethod
    def from_responses(cls, responses: dict) -> "CalibrationSettings":
        """Create from player question responses."""
        return cls(
            tone=ToneSettings.from_responses(responses),
            themes=ThemeSettings.from_responses(responses),
            risk=RiskSettings.from_responses(responses),
            boundaries=BoundarySettings.from_responses(responses),
            agency=AgencySettings.from_responses(responses)
        )

    @classmethod
    def from_preset(cls, preset_id: str) -> "CalibrationSettings":
        """Load from a preset configuration file."""
        presets = {
            "noir_standard": cls._noir_standard(),
            "pulp_adventure": cls._pulp_adventure(),
            "hard_boiled": cls._hard_boiled(),
            "one_bad_day": cls._one_bad_day(),
        }

        if preset_id in presets:
            return presets[preset_id]

        # Try loading from file
        preset_path = Path(__file__).parent.parent.parent / "calibration" / f"{preset_id}.yaml"
        if preset_path.exists():
            return cls.from_yaml(preset_path)

        raise ValueError(f"Unknown calibration preset: {preset_id}")

    @classmethod
    def from_yaml(cls, path: Path) -> "CalibrationSettings":
        """Load from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        return cls(
            tone=ToneSettings(**data.get("tone", {})),
            themes=ThemeSettings(**data.get("themes", {})),
            risk=RiskSettings(**data.get("risk", {})),
            boundaries=BoundarySettings(**data.get("boundaries", {})),
            agency=AgencySettings(**data.get("agency", {}))
        )

    @classmethod
    def _noir_standard(cls) -> "CalibrationSettings":
        """Noir Standard preset - gritty, morally gray, consequential."""
        return cls(
            tone=ToneSettings(
                gritty_vs_cinematic=0.7,
                dark_vs_light=0.6,
                moral_complexity=0.8,
                slow_burn_vs_action=0.5
            ),
            themes=ThemeSettings(
                primary=["identity_synthetic", "cost_of_survival"],
                secondary=["corporate_vs_individual", "trust_betrayal"],
                avoid=[]
            ),
            risk=RiskSettings(
                lethality="moderate",
                failure_mode="consequential",
                permanence="meaningful",
                plot_armor="thin"
            ),
            boundaries=BoundarySettings(
                lines=BoundarySettings.DEFAULT_LINES.copy(),
                veils=["graphic_torture"],
                explore=["violence_consequences", "moral_ambiguity"]
            ),
            agency=AgencySettings(
                structure="guided",
                world_plasticity="responsive",
                world_agency="active",
                ambiguity_handling="interpret"
            )
        )

    @classmethod
    def _pulp_adventure(cls) -> "CalibrationSettings":
        """Pulp Adventure preset - cinematic, heroic, forgiving."""
        return cls(
            tone=ToneSettings(
                gritty_vs_cinematic=0.3,
                dark_vs_light=0.3,
                moral_complexity=0.4,
                slow_burn_vs_action=0.3
            ),
            themes=ThemeSettings(
                primary=["heroism", "adventure"],
                secondary=["friendship", "discovery"],
                avoid=["nihilism"]
            ),
            risk=RiskSettings(
                lethality="low",
                failure_mode="forgiving",
                permanence="soft",
                plot_armor="thick"
            ),
            boundaries=BoundarySettings(
                lines=BoundarySettings.DEFAULT_LINES.copy(),
                veils=["graphic_violence"],
                explore=["action", "excitement"]
            ),
            agency=AgencySettings(
                structure="guided",
                world_plasticity="malleable",
                world_agency="passive",
                ambiguity_handling="clarify"
            )
        )

    @classmethod
    def _hard_boiled(cls) -> "CalibrationSettings":
        """Hard Boiled preset - very gritty, punishing, dark."""
        return cls(
            tone=ToneSettings(
                gritty_vs_cinematic=0.9,
                dark_vs_light=0.8,
                moral_complexity=0.9,
                slow_burn_vs_action=0.6
            ),
            themes=ThemeSettings(
                primary=["corruption", "survival"],
                secondary=["betrayal", "loss"],
                avoid=["redemption"]
            ),
            risk=RiskSettings(
                lethality="high",
                failure_mode="punishing",
                permanence="hard",
                plot_armor="none"
            ),
            boundaries=BoundarySettings(
                lines=BoundarySettings.DEFAULT_LINES.copy(),
                veils=[],
                explore=["violence", "desperation", "moral_decay"]
            ),
            agency=AgencySettings(
                structure="sandbox",
                world_plasticity="fixed",
                world_agency="aggressive",
                ambiguity_handling="interpret"
            )
        )

    @classmethod
    def _one_bad_day(cls) -> "CalibrationSettings":
        """One Bad Day preset - brutal, short, tragic."""
        return cls(
            tone=ToneSettings(
                gritty_vs_cinematic=0.95,
                dark_vs_light=0.9,
                moral_complexity=0.7,
                slow_burn_vs_action=0.4
            ),
            themes=ThemeSettings(
                primary=["doom", "desperation"],
                secondary=["sacrifice"],
                avoid=["hope"]
            ),
            risk=RiskSettings(
                lethality="brutal",
                failure_mode="punishing",
                permanence="hard",
                plot_armor="none"
            ),
            boundaries=BoundarySettings(
                lines=BoundarySettings.DEFAULT_LINES.copy(),
                veils=[],
                explore=["horror", "tragedy"]
            ),
            agency=AgencySettings(
                structure="linear",
                world_plasticity="fixed",
                world_agency="aggressive",
                ambiguity_handling="interpret"
            )
        )

    def to_dict(self) -> dict:
        """Convert to dict for storage."""
        return {
            "tone": self.tone.to_dict(),
            "themes": self.themes.to_dict(),
            "risk": self.risk.to_dict(),
            "boundaries": self.boundaries.to_dict(),
            "agency": self.agency.to_dict()
        }
