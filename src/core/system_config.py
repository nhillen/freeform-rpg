"""
System configuration framework.

Config-driven resolution system adapter. Campaigns define resolution_rules
in their system config to select dice mechanics (2d6 bands, dice pool, etc.).

Without resolution_rules, the default 2d6 band system is used — all existing
scenarios work identically with zero changes.

Follows the same pattern as ClockConfig: dataclasses loaded from scenario YAML.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ResolutionConfig:
    """How dice resolution works for this system.

    method: '2d6_bands' (default) or 'dice_pool'
    """
    method: str = "2d6_bands"
    die_type: int = 6
    default_difficulty: int = 6
    ones_cancel_successes: bool = False
    botch_on_ones: bool = False
    threshold_past_9: bool = False
    pool_outcome_thresholds: dict = field(default_factory=lambda: {
        "botch": 0,
        "failure": 0,
        "mixed": 1,
        "success": 2,
        "critical": 4,
    })
    # 2d6 band boundaries (only used when method == '2d6_bands')
    bands: dict = field(default_factory=lambda: {
        "failure": [2, 6],
        "mixed": [7, 9],
        "success": [10, 11],
        "critical": [12, 12],
    })


@dataclass
class StatSchema:
    """Defines what stats exist in this system.

    attributes: category -> list of stat names
    abilities: category -> list of ability names
    special_traits: trait_name -> {min, max}
    """
    attributes: dict = field(default_factory=dict)
    abilities: dict = field(default_factory=dict)
    special_traits: dict = field(default_factory=dict)

    def all_attribute_names(self) -> list[str]:
        """Flat list of all attribute names across categories."""
        names = []
        for cat_list in self.attributes.values():
            names.extend(cat_list)
        return names

    def all_ability_names(self) -> list[str]:
        """Flat list of all ability names across categories."""
        names = []
        for cat_list in self.abilities.values():
            names.extend(cat_list)
        return names


@dataclass
class DifficultyConfig:
    """Difficulty settings for the resolution system."""
    default: int = 6
    auto_success_if_pool_gte_difficulty: bool = False
    retry_penalty: int = 0


@dataclass
class WillpowerConfig:
    """Willpower/resource spending rules."""
    enabled: bool = False
    resource_name: str = "willpower"
    auto_successes_per_spend: int = 1
    max_per_turn: int = 1


@dataclass
class SystemConfig:
    """Complete resolution system configuration.

    With no arguments, returns the default 2d6 band system that matches
    all current hardcoded behavior in resolver.py.
    """
    name: str = "default_2d6"
    resolution: ResolutionConfig = field(default_factory=ResolutionConfig)
    stat_schema: StatSchema = field(default_factory=StatSchema)
    difficulty: DifficultyConfig = field(default_factory=DifficultyConfig)
    willpower: WillpowerConfig = field(default_factory=WillpowerConfig)

    # Action type -> {attribute, ability} mapping for dice pool systems
    action_stat_map: dict = field(default_factory=dict)

    # Condition and clear maps (override resolver defaults when non-empty)
    condition_map: dict = field(default_factory=dict)
    clear_map: dict = field(default_factory=dict)

    # Safe/risky action sets (override resolver defaults when non-empty)
    safe_actions: set = field(default_factory=set)
    risky_actions: set = field(default_factory=set)

    # Inventory requirements override (action_type -> {item: qty})
    inventory_requirements: dict = field(default_factory=dict)

    def get_stat_pair(self, action_type: str) -> tuple[str, str]:
        """Get (attribute, ability) for an action type.

        Falls back to _default entry, then ('wits', 'alertness').
        """
        entry = self.action_stat_map.get(
            action_type.lower(),
            self.action_stat_map.get("_default", {})
        )
        if not entry:
            return ("wits", "alertness")
        return (entry.get("attribute", "wits"), entry.get("ability", "alertness"))

    def is_dice_pool(self) -> bool:
        """Check if this system uses dice pool resolution."""
        return self.resolution.method == "dice_pool"

    def system_summary(self) -> dict:
        """Human-readable summary for LLM context."""
        if self.is_dice_pool():
            return {
                "name": self.name,
                "resolution": (
                    f"Dice pool: roll (attribute + ability) d{self.resolution.die_type}s, "
                    f"count successes >= difficulty (default {self.difficulty.default})"
                ),
                "ones_cancel": self.resolution.ones_cancel_successes,
                "botch_possible": self.resolution.botch_on_ones,
                "willpower": self.willpower.enabled,
            }
        return {
            "name": self.name,
            "resolution": "2d6 sum against bands: 6- fail, 7-9 mixed, 10+ success, 12 critical",
            "ones_cancel": False,
            "botch_possible": False,
            "willpower": False,
        }


def load_system_config(system_json: dict) -> SystemConfig:
    """Load SystemConfig from campaign system_json.

    Returns default 2d6 config when system_json has no resolution_rules.
    Existing scenarios without resolution_rules work identically.
    """
    if not system_json:
        return SystemConfig()

    rules = system_json.get("resolution_rules", {})
    if not rules:
        return SystemConfig()

    # Parse resolution
    res_data = rules.get("resolution", {})
    resolution = ResolutionConfig(
        method=res_data.get("method", "2d6_bands"),
        die_type=res_data.get("die_type", 6),
        default_difficulty=res_data.get("default_difficulty", 6),
        ones_cancel_successes=res_data.get("ones_cancel_successes", False),
        botch_on_ones=res_data.get("botch_on_ones", False),
        threshold_past_9=res_data.get("threshold_past_9", False),
        pool_outcome_thresholds=res_data.get("pool_outcome_thresholds", ResolutionConfig().pool_outcome_thresholds),
        bands=res_data.get("bands", ResolutionConfig().bands),
    )

    # Parse stat schema
    schema_data = rules.get("stat_schema", {})
    stat_schema = StatSchema(
        attributes=schema_data.get("attributes", {}),
        abilities=schema_data.get("abilities", {}),
        special_traits=schema_data.get("special_traits", {}),
    )

    # Parse difficulty
    diff_data = rules.get("difficulty", {})
    difficulty = DifficultyConfig(
        default=diff_data.get("default", 6),
        auto_success_if_pool_gte_difficulty=diff_data.get("auto_success_if_pool_gte_difficulty", False),
        retry_penalty=diff_data.get("retry_penalty", 0),
    )

    # Parse willpower
    wp_data = rules.get("willpower", {})
    willpower = WillpowerConfig(
        enabled=wp_data.get("enabled", False),
        resource_name=wp_data.get("resource_name", "willpower"),
        auto_successes_per_spend=wp_data.get("auto_successes_per_spend", 1),
        max_per_turn=wp_data.get("max_per_turn", 1),
    )

    # Parse action stat map
    action_stat_map = rules.get("action_stat_map", {})

    # Parse condition/clear overrides
    condition_map = rules.get("condition_map", {})
    clear_map = rules.get("clear_map", {})

    # Parse safe/risky action sets
    safe_actions = set(rules.get("safe_actions", []))
    risky_actions = set(rules.get("risky_actions", []))

    # Parse inventory requirements
    inventory_requirements = rules.get("inventory_requirements", {})

    # Determine name
    name = rules.get("name", "")
    if not name:
        name = "dice_pool" if resolution.method == "dice_pool" else "default_2d6"

    return SystemConfig(
        name=name,
        resolution=resolution,
        stat_schema=stat_schema,
        difficulty=difficulty,
        willpower=willpower,
        action_stat_map=action_stat_map,
        condition_map=condition_map,
        clear_map=clear_map,
        safe_actions=safe_actions,
        risky_actions=risky_actions,
        inventory_requirements=inventory_requirements,
    )


# --- System presets ---

def mage_ascension_resolution_rules() -> dict:
    """Return full resolution_rules for Mage: The Ascension.

    Put this in scenario system_json under "resolution_rules".
    """
    return {
        "name": "mage_ascension",
        "resolution": {
            "method": "dice_pool",
            "die_type": 10,
            "default_difficulty": 6,
            "ones_cancel_successes": True,
            "botch_on_ones": True,
            "threshold_past_9": True,
            "pool_outcome_thresholds": {
                "botch": 0,
                "failure": 0,
                "mixed": 1,
                "success": 2,
                "critical": 4,
            },
        },
        "stat_schema": {
            "attributes": {
                "physical": ["strength", "dexterity", "stamina"],
                "social": ["charisma", "manipulation", "appearance"],
                "mental": ["perception", "intelligence", "wits"],
            },
            "abilities": {
                "talents": [
                    "alertness", "athletics", "awareness", "brawl",
                    "expression", "intimidation", "leadership",
                    "streetwise", "subterfuge",
                ],
                "skills": [
                    "crafts", "drive", "etiquette", "firearms",
                    "martial_arts", "meditation", "melee",
                    "stealth", "survival", "technology",
                ],
                "knowledges": [
                    "academics", "computer", "cosmology", "enigmas",
                    "investigation", "law", "linguistics",
                    "medicine", "occult", "science",
                ],
            },
            "special_traits": {
                "arete": {"min": 1, "max": 10},
                "willpower": {"min": 1, "max": 10},
                "quintessence": {"min": 0, "max": 20},
                "paradox": {"min": 0, "max": 20},
            },
        },
        "action_stat_map": {
            "sneak": {"attribute": "dexterity", "ability": "stealth"},
            "hide": {"attribute": "dexterity", "ability": "stealth"},
            "attack": {"attribute": "strength", "ability": "brawl"},
            "fight": {"attribute": "strength", "ability": "brawl"},
            "shoot": {"attribute": "dexterity", "ability": "firearms"},
            "climb": {"attribute": "dexterity", "ability": "athletics"},
            "chase": {"attribute": "dexterity", "ability": "athletics"},
            "flee": {"attribute": "dexterity", "ability": "athletics"},
            "persuade": {"attribute": "charisma", "ability": "expression"},
            "intimidate": {"attribute": "strength", "ability": "intimidation"},
            "deceive": {"attribute": "manipulation", "ability": "subterfuge"},
            "negotiate": {"attribute": "charisma", "ability": "expression"},
            "hack": {"attribute": "intelligence", "ability": "computer"},
            "steal": {"attribute": "dexterity", "ability": "subterfuge"},
            "investigate": {"attribute": "perception", "ability": "investigation"},
            "search": {"attribute": "perception", "ability": "awareness"},
            "examine": {"attribute": "perception", "ability": "awareness"},
            "_default": {"attribute": "wits", "ability": "alertness"},
        },
        "difficulty": {
            "default": 6,
            "auto_success_if_pool_gte_difficulty": False,
            "retry_penalty": 1,
        },
        "willpower": {
            "enabled": True,
            "resource_name": "willpower",
            "auto_successes_per_spend": 1,
            "max_per_turn": 1,
        },
    }
