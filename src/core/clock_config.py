"""
Clock configuration framework.

Generic clock system that campaigns opt into by defining clock_rules
in their system config. Without clock_rules, no clocks are active.

Validator and resolver both delegate to ClockConfig for all clock behavior.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ClockConfig:
    """Resolved clock configuration for a campaign.

    With no arguments, creates an empty config — no clocks, no costs.
    Campaigns opt in to clocks by defining clock_rules in system config.
    """
    enabled: bool = True
    clocks_enabled: list[str] = field(default_factory=list)
    direction: dict[str, str] = field(default_factory=dict)
    cost_map: dict[str, dict[str, int]] = field(default_factory=dict)
    complication_clocks: dict = field(default_factory=dict)
    failure_effects: dict = field(default_factory=dict)
    tension_keywords: dict[str, list[str]] = field(default_factory=dict)
    show_deltas: bool = True
    duration_map: dict[str, int] = field(default_factory=dict)
    failure_severity: dict = field(default_factory=dict)

    def get_default_duration(self, action_type: str) -> int:
        """Default fictional duration in minutes. Falls back to _default, then 5."""
        return self.duration_map.get(action_type, self.duration_map.get("_default", 5))

    def get_cost(self, action_type: str) -> dict[str, int]:
        """Get cost for an action type. Returns filtered copy.

        Uses the "_default" key in cost_map as fallback for unlisted actions.
        Returns empty dict if no cost_map or no matching entry.
        """
        raw = dict(self.cost_map.get(action_type, self.cost_map.get("_default", {})))
        # Filter to only active clocks
        return {k: v for k, v in raw.items() if k in self.clocks_enabled}

    def apply_direction(self, clock_id: str, delta: int) -> int:
        """Apply direction to a delta. Decrementing clocks get negated."""
        if self.direction.get(clock_id) == "decrement":
            return -abs(delta)
        return abs(delta) if delta >= 0 else delta

    def is_clock_active(self, clock_id: str) -> bool:
        """Check if a clock is active in this campaign."""
        return clock_id in self.clocks_enabled

    def get_complication_effects(self, action_type: str) -> list[dict]:
        """Get clock effects for a complication (mixed result)."""
        if not self.complication_clocks:
            return []
        category = "combat" if action_type.lower() in ("combat", "attack", "violence") else "default"
        effects = self.complication_clocks.get(category, self.complication_clocks.get("default", []))
        if isinstance(effects, dict):
            effects = [effects]
        return effects

    def get_failure_clock_effects(self, action_type: str, failure_mode: str) -> list[dict]:
        """Get clock effects for a failure."""
        if not self.failure_effects:
            return []
        mode_effects = self.failure_effects.get(failure_mode, self.failure_effects.get("consequential", {}))
        if not mode_effects:
            return []
        category = "combat" if action_type.lower() in ("combat", "attack", "fight", "shoot") else "default"
        effects = mode_effects.get(category, mode_effects.get("default", []))
        if isinstance(effects, dict):
            effects = [effects]
        return effects

    def get_tension_clock(self, tension_text: str) -> Optional[str]:
        """Match tension move text to a clock ID via keywords. Returns None if no match."""
        text_lower = tension_text.lower()
        for clock_id, keywords in self.tension_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return clock_id
        return None


def load_clock_config(system_json: dict) -> ClockConfig:
    """Load ClockConfig from campaign system_json.

    Returns empty config (no clocks) when system_json has no clock_rules.
    Only campaigns that explicitly define clock_rules get clock behavior.
    """
    if not system_json:
        return ClockConfig()

    rules = system_json.get("clock_rules", {})
    if not rules:
        return ClockConfig()

    return ClockConfig(
        enabled=rules.get("enabled", True),
        clocks_enabled=rules.get("clocks_enabled", []),
        direction=rules.get("direction", {}),
        cost_map=rules.get("cost_map", {}),
        complication_clocks=rules.get("complication_clocks", {}),
        failure_effects=rules.get("failure_effects", {}),
        tension_keywords=rules.get("tension_keywords", {}),
        show_deltas=rules.get("display", {}).get("show_deltas", True),
        duration_map=rules.get("duration_map", {}),
        failure_severity=rules.get("failure_severity", {}),
    )


# --- Genre presets ---
# These return full clock_rules dicts suitable for system_json.
# Scenarios reference these or define their own.

def cyberpunk_noir_clock_rules() -> dict:
    """Return full clock_rules for cyberpunk noir genre.

    Put this in campaign system_json under "clock_rules" to get
    the standard cyberpunk noir clock behavior.
    """
    return {
        "enabled": True,
        "clocks_enabled": ["heat", "time", "cred", "harm", "rep"],
        "direction": {
            "time": "decrement",
        },
        "cost_map": {
            "_default": {},                    # unknown actions cost nothing by default
            "investigate": {"time": 1},
            "search": {"time": 1},
            "examine": {},                     # quick glance, no time cost
            "talk": {"time": 1},
            "social": {"time": 1},
            "persuade": {"time": 1},
            "negotiate": {"time": 1},
            "travel": {"time": 2},             # significant movement
            "move": {},                        # repositioning is instant
            "go": {},                          # same
            "hack": {"heat": 1, "time": 1},
            "steal": {"heat": 2, "time": 1},
            "combat": {"heat": 1},
            "attack": {"heat": 1},
            "violence": {"heat": 1},
            "crime": {"heat": 2},
            "bribe": {"cred": 50},
            "buy": {"cred": 0},
            "sneak": {},                       # physical, no time
            "climb": {},                       # physical, no time
            "use": {},                         # quick interaction
            "look": {},                        # instant
            "wait": {"time": 1},               # deliberately spending time
        },
        "complication_clocks": {
            "combat": [{"id": "heat", "delta": 1}],
            "default": [{"id": "time", "delta": 1}],
        },
        "failure_effects": {
            "forgiving": {
                "default": [{"id": "time", "delta": 1}],
            },
            "consequential": {
                "combat": [{"id": "harm", "delta": 1}],
                "default": [{"id": "heat", "delta": 1}],
            },
            "punishing": {
                "combat": [{"id": "harm", "delta": 2}, {"id": "heat", "delta": 1}],
                "default": [{"id": "heat", "delta": 1}],
            },
        },
        "tension_keywords": {
            "heat": ["heat", "attention"],
            "time": ["time", "deadline"],
        },
        "duration_map": {
            "_default": 5,
            "look": 1, "examine": 1, "use": 2,
            "move": 2, "go": 2, "sneak": 5, "climb": 5,
            "talk": 10, "ask": 5, "persuade": 15, "negotiate": 15, "intimidate": 5,
            "search": 15, "investigate": 20, "hack": 15,
            "travel": 30,
            "combat": 5, "attack": 3,
            "steal": 10, "wait": 15, "read": 5,
        },
        "failure_severity": {
            "streak_threshold": 3,
            "tier2_harm_actions": ["sneak", "hide", "flee", "climb", "fight", "attack", "chase"],
            "tier3_base_harm": 2,
        },
        "display": {
            "show_deltas": True,
        },
    }
