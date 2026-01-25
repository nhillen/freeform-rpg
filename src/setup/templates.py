"""
Scenario Templates - Structured YAML templates for campaign setup.

Templates define the skeleton of a scenario: locations, NPC roles, threads,
and case structure. The setup pipeline fills in specifics.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ScenarioTemplate:
    """A scenario template for campaign initialization."""
    id: str
    name: str
    description: str = ""
    genre: str = "cyberpunk_noir"
    estimated_length: str = "2-4 hours"

    # Genre context
    genre_rules: dict = field(default_factory=dict)

    # Structural elements
    locations: list[dict] = field(default_factory=list)
    npcs: list[dict] = field(default_factory=list)
    facts: list[dict] = field(default_factory=list)
    threads: list[dict] = field(default_factory=list)
    clocks: list[dict] = field(default_factory=list)

    # Starting state
    starting_scene: dict = field(default_factory=dict)
    opening_text: str = ""

    # Case structure
    revelations: list[dict] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path) -> "ScenarioTemplate":
        """Load template from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        return cls(
            id=data.get("id", path.stem),
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            genre=data.get("genre", "cyberpunk_noir"),
            estimated_length=data.get("estimated_length", "2-4 hours"),
            genre_rules=data.get("genre_rules", {}),
            locations=data.get("locations", []),
            npcs=data.get("npcs", data.get("entities", [])),  # Support both formats
            facts=data.get("facts", []),
            threads=data.get("threads", []),
            clocks=data.get("clocks", cls._default_clocks()),
            starting_scene=data.get("starting_scene", {}),
            opening_text=data.get("opening_text", ""),
            revelations=data.get("revelations", [])
        )

    @staticmethod
    def _default_clocks() -> list[dict]:
        """Return default clock configuration."""
        return [
            {
                "id": "heat",
                "name": "Heat",
                "value": 1,
                "max": 8,
                "triggers": {
                    "4": "Cops start asking questions",
                    "6": "Active investigation",
                    "8": "Raid imminent"
                }
            },
            {
                "id": "time",
                "name": "Time",
                "value": 8,
                "max": 12,
                "triggers": {
                    "4": "Dawn approaches",
                    "2": "Almost out of time",
                    "0": "Deadline passed"
                }
            },
            {
                "id": "harm",
                "name": "Harm",
                "value": 0,
                "max": 4,
                "triggers": {
                    "2": "Seriously hurt",
                    "4": "Critical condition"
                }
            },
            {
                "id": "cred",
                "name": "Cred",
                "value": 500,
                "max": 9999,
                "triggers": {}
            },
            {
                "id": "rep",
                "name": "Rep",
                "value": 2,
                "max": 5,
                "triggers": {
                    "0": "Nobody",
                    "4": "Well known"
                }
            }
        ]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "genre": self.genre,
            "estimated_length": self.estimated_length,
            "genre_rules": self.genre_rules,
            "locations": self.locations,
            "npcs": self.npcs,
            "facts": self.facts,
            "threads": self.threads,
            "clocks": self.clocks,
            "starting_scene": self.starting_scene,
            "opening_text": self.opening_text,
            "revelations": self.revelations
        }


def load_template(
    template_id: str,
    templates_dir: Optional[Path] = None
) -> ScenarioTemplate:
    """
    Load a scenario template by ID.

    Args:
        template_id: Template ID or path to YAML file
        templates_dir: Directory to search for templates

    Returns:
        ScenarioTemplate loaded from file
    """
    templates_dir = templates_dir or Path(__file__).parent.parent.parent / "scenarios"

    # Check if it's a direct path
    if Path(template_id).exists():
        return ScenarioTemplate.from_yaml(Path(template_id))

    # Search in templates directory
    for ext in [".yaml", ".yml"]:
        template_path = templates_dir / f"{template_id}{ext}"
        if template_path.exists():
            return ScenarioTemplate.from_yaml(template_path)

    # Return a minimal default template
    return _create_default_template(template_id)


def _create_default_template(template_id: str) -> ScenarioTemplate:
    """Create a minimal default template."""
    return ScenarioTemplate(
        id=template_id,
        name=f"Default: {template_id}",
        description="A minimal scenario template",
        genre="cyberpunk_noir",
        genre_rules={
            "setting": "Cyberpunk noir",
            "technology": "Near-future, cybernetics common",
            "tone": "Gritty, morally ambiguous"
        },
        locations=[
            {
                "id": "starting_location",
                "name": "The Neon Dragon Bar",
                "attrs": {
                    "description": "A dive bar in the Undercity, neutral ground",
                    "atmosphere": "Smoky, neon-lit, crowded"
                },
                "tags": ["bar", "neutral", "undercity"]
            }
        ],
        npcs=[
            {
                "id": "contact_npc",
                "name": "Viktor",
                "attrs": {
                    "role": "fixer",
                    "description": "A well-connected fixer with cybernetic eyes",
                    "agenda": "Profitable deals, no questions asked"
                },
                "tags": ["fixer", "contact"],
                "relationship": {
                    "type": "professional",
                    "intensity": 1,
                    "notes": {"history": "Has worked together before"}
                }
            }
        ],
        facts=[
            {
                "id": "fact_contact_reliable",
                "subject_id": "contact_npc",
                "predicate": "reputation",
                "object": {"trait": "reliable", "qualifier": "when paid"},
                "visibility": "known",
                "tags": []
            }
        ],
        threads=[
            {
                "id": "main_thread",
                "title": "Find the truth",
                "status": "active",
                "stakes": {
                    "success": "Answers and payment",
                    "failure": "More questions, more danger"
                },
                "tags": ["main"]
            }
        ],
        clocks=ScenarioTemplate._default_clocks(),
        starting_scene={
            "location_id": "starting_location",
            "present_entity_ids": ["player", "contact_npc"],
            "time": {"hour": 22, "period": "night"},
            "visibility_conditions": "dim",
            "noise_level": "moderate"
        },
        opening_text=(
            "The rain never stops in this city. You push through the beaded curtain "
            "of the Neon Dragon, scanning the smoky interior. Viktor is waiting in "
            "the back booth, cybernetic eyes glinting in the dim light. He has a job for you."
        )
    )


def list_templates(templates_dir: Optional[Path] = None) -> list[dict]:
    """List available scenario templates."""
    templates_dir = templates_dir or Path(__file__).parent.parent.parent / "scenarios"

    templates = []
    if templates_dir.exists():
        for path in templates_dir.glob("*.yaml"):
            try:
                with open(path) as f:
                    data = yaml.safe_load(f)
                templates.append({
                    "id": data.get("id", path.stem),
                    "name": data.get("name", path.stem),
                    "description": data.get("description", ""),
                    "path": str(path)
                })
            except Exception:
                pass

        for path in templates_dir.glob("*.yml"):
            try:
                with open(path) as f:
                    data = yaml.safe_load(f)
                templates.append({
                    "id": data.get("id", path.stem),
                    "name": data.get("name", path.stem),
                    "description": data.get("description", ""),
                    "path": str(path)
                })
            except Exception:
                pass

    return templates
