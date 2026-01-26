"""
Setup Pipeline - Orchestrates Session Zero / campaign initialization.

Handles calibration, character creation, NPC population, and case structure.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..db.state_store import StateStore, new_id
from ..llm.gateway import LLMGateway, MockGateway
from .calibration import CalibrationSettings
from .templates import ScenarioTemplate, load_template


@dataclass
class CharacterData:
    """Player character data."""
    id: str
    name: str
    background: str
    skills: list[str]
    weakness: str
    motivation: str
    moral_line: str
    attrs: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=lambda: ["player"])

    def to_entity_dict(self) -> dict:
        attrs = {
            "background": self.background,
            "skills": self.skills,
            "weakness": self.weakness,
            "motivation": self.motivation,
            "moral_line": self.moral_line,
            **self.attrs
        }
        return {
            "id": self.id,
            "type": "pc",
            "name": self.name,
            "attrs": attrs,
            "tags": self.tags
        }


@dataclass
class SetupResult:
    """Result of the setup pipeline."""
    campaign_id: str
    calibration: CalibrationSettings
    character: CharacterData
    npcs_created: int
    facts_created: int
    summary: str
    opening_text: str
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "campaign_id": self.campaign_id,
            "calibration": self.calibration.to_dict(),
            "character": {
                "id": self.character.id,
                "name": self.character.name,
                "background": self.character.background
            },
            "npcs_created": self.npcs_created,
            "facts_created": self.facts_created,
            "summary": self.summary,
            "opening_text": self.opening_text,
            "issues": self.issues
        }


class SetupPipeline:
    """
    Orchestrates the Session Zero setup process.

    Phases:
    0. Calibration - tone, themes, risk, boundaries
    1. Load scenario template
    2. Character creation from player responses
    3. NPC population based on template + character
    4. Case structure generation
    5. State initialization
    6. Validation
    """

    def __init__(
        self,
        state_store: StateStore,
        llm_gateway: Optional[LLMGateway] = None,
        templates_dir: Optional[Path] = None
    ):
        self.store = state_store
        self.gateway = llm_gateway or MockGateway()
        self.templates_dir = templates_dir or Path(__file__).parent.parent.parent / "scenarios"

    def run_setup(
        self,
        template_id: str,
        calibration_responses: Optional[dict] = None,
        calibration_preset: Optional[str] = None,
        character_responses: Optional[dict] = None,
        campaign_id: Optional[str] = None
    ) -> SetupResult:
        """
        Run the complete setup pipeline.

        Args:
            template_id: Scenario template to use
            calibration_responses: Player answers to calibration questions
            calibration_preset: OR use a preset (e.g., "noir_standard")
            character_responses: Player answers to character questions
            campaign_id: Optional campaign ID (auto-generated if not provided)

        Returns:
            SetupResult with campaign info and summary
        """
        campaign_id = campaign_id or new_id()
        issues = []

        # Phase 0: Calibration
        if calibration_preset:
            calibration = CalibrationSettings.from_preset(calibration_preset)
        elif calibration_responses:
            calibration = CalibrationSettings.from_responses(calibration_responses)
        else:
            calibration = CalibrationSettings.from_preset("noir_standard")

        # Phase 1: Load template
        template = load_template(template_id, self.templates_dir)

        # Phase 2: Create character
        character_responses = character_responses or {}
        character = self._create_character(template, character_responses, calibration)

        # Phase 3: Create campaign in database
        self.store.create_campaign(
            campaign_id=campaign_id,
            name=template.name,
            calibration=calibration.to_dict(),
            system=template.system,
            genre_rules=template.genre_rules
        )

        # Phase 4: Initialize clocks from template
        self._initialize_clocks(template)

        # Phase 5: Create entities
        self.store.create_entity(
            entity_id=character.id,
            entity_type="pc",
            name=character.name,
            attrs=character.to_entity_dict()["attrs"],
            tags=character.tags
        )

        npcs_created = self._create_npcs(template, character, calibration)
        self._create_locations(template)

        # Phase 6: Create facts
        facts_created = self._create_facts(template, character, calibration)

        # Phase 7: Create threads
        self._create_threads(template, character)

        # Phase 8: Set starting scene
        self._set_starting_scene(template, character)

        # Phase 9: Validate
        validation_issues = self._validate_state(template, character)
        issues.extend(validation_issues)

        # Generate summary and opening
        summary = self._generate_summary(template, character, calibration)
        opening_text = template.opening_text or self._generate_opening(template, character)

        return SetupResult(
            campaign_id=campaign_id,
            calibration=calibration,
            character=character,
            npcs_created=npcs_created,
            facts_created=facts_created,
            summary=summary,
            opening_text=opening_text,
            issues=issues
        )

    def _create_character(
        self,
        template: ScenarioTemplate,
        responses: dict,
        calibration: CalibrationSettings
    ) -> CharacterData:
        """Create player character from responses."""
        # Extract from responses with defaults
        name = responses.get("name", "Anonymous")
        background = responses.get("background", "A survivor in the neon-lit shadows")
        skills = responses.get("skills", ["street smarts", "survival"])
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",")]

        weakness = responses.get("weakness", "Trust issues")
        motivation = responses.get("motivation", "Find the truth")
        moral_line = responses.get("moral_line", "Won't harm innocents")

        return CharacterData(
            id="player",
            name=name,
            background=background,
            skills=skills,
            weakness=weakness,
            motivation=motivation,
            moral_line=moral_line
        )

    def _initialize_clocks(self, template: ScenarioTemplate) -> None:
        """Initialize clocks from template."""
        for clock_data in template.clocks:
            self.store.create_clock(
                clock_id=clock_data["id"],
                name=clock_data["name"],
                value=clock_data["value"],
                max_value=clock_data["max"],
                triggers=clock_data.get("triggers", {}),
                tags=clock_data.get("tags", [])
            )

    def _create_npcs(
        self,
        template: ScenarioTemplate,
        character: CharacterData,
        calibration: CalibrationSettings
    ) -> int:
        """Create NPCs from template."""
        count = 0
        for npc_data in template.npcs:
            self.store.create_entity(
                entity_id=npc_data["id"],
                entity_type="npc",
                name=npc_data["name"],
                attrs=npc_data.get("attrs", {}),
                tags=npc_data.get("tags", [])
            )
            count += 1

            # Create relationship if specified
            if "relationship" in npc_data:
                rel = npc_data["relationship"]
                self.store.create_relationship(
                    a_id="player",
                    b_id=npc_data["id"],
                    rel_type=rel.get("type", "knows"),
                    intensity=rel.get("intensity", 0),
                    notes=rel.get("notes", {})
                )

        return count

    def _create_locations(self, template: ScenarioTemplate) -> None:
        """Create location entities from template."""
        for loc_data in template.locations:
            self.store.create_entity(
                entity_id=loc_data["id"],
                entity_type="location",
                name=loc_data["name"],
                attrs=loc_data.get("attrs", {}),
                tags=loc_data.get("tags", [])
            )

    def _create_facts(
        self,
        template: ScenarioTemplate,
        character: CharacterData,
        calibration: CalibrationSettings
    ) -> int:
        """Create facts from template."""
        count = 0
        for fact_data in template.facts:
            self.store.create_fact(
                fact_id=fact_data.get("id", new_id()),
                subject_id=fact_data["subject_id"],
                predicate=fact_data["predicate"],
                obj=fact_data.get("object", {}),
                visibility=fact_data.get("visibility", "world"),
                confidence=fact_data.get("confidence", 1.0),
                tags=fact_data.get("tags", [])
            )
            count += 1
        return count

    def _create_threads(
        self,
        template: ScenarioTemplate,
        character: CharacterData
    ) -> None:
        """Create threads from template."""
        for thread_data in template.threads:
            self.store.create_thread(
                thread_id=thread_data["id"],
                title=thread_data["title"],
                status=thread_data.get("status", "active"),
                stakes=thread_data.get("stakes", {}),
                related_entity_ids=thread_data.get("related_entity_ids", []),
                tags=thread_data.get("tags", [])
            )

    def _set_starting_scene(
        self,
        template: ScenarioTemplate,
        character: CharacterData
    ) -> None:
        """Set the starting scene."""
        scene = template.starting_scene
        present = scene.get("present_entity_ids", ["player"])
        if "player" not in present:
            present = ["player"] + present

        self.store.set_scene(
            location_id=scene.get("location_id", template.locations[0]["id"] if template.locations else "unknown"),
            present_entity_ids=present,
            time=scene.get("time", {"hour": 22, "period": "night"}),
            constraints=scene.get("constraints", {}),
            visibility_conditions=scene.get("visibility_conditions", "normal"),
            noise_level=scene.get("noise_level", "normal"),
            obscured_entities=scene.get("obscured_entities", [])
        )

    def _validate_state(
        self,
        template: ScenarioTemplate,
        character: CharacterData
    ) -> list[str]:
        """Validate the created state."""
        issues = []

        # Check player exists
        player = self.store.get_entity("player")
        if not player:
            issues.append("Player entity not created")

        # Check scene exists
        scene = self.store.get_scene()
        if not scene:
            issues.append("Starting scene not set")

        # Check clocks exist
        clocks = self.store.get_all_clocks()
        if len(clocks) < len(template.clocks):
            issues.append(f"Only {len(clocks)} of {len(template.clocks)} clocks created")

        # Check at least one thread exists
        threads = self.store.get_active_threads()
        if not threads:
            issues.append("No active threads created")

        return issues

    def _generate_summary(
        self,
        template: ScenarioTemplate,
        character: CharacterData,
        calibration: CalibrationSettings
    ) -> str:
        """Generate a summary of the setup."""
        tone_desc = "gritty" if calibration.tone.gritty_vs_cinematic > 0.5 else "cinematic"
        risk_desc = calibration.risk.lethality

        themes = ", ".join(calibration.themes.primary[:2]) if calibration.themes.primary else "survival"

        return (
            f"Campaign initialized: {template.name}\n"
            f"Character: {character.name}\n"
            f"Tone: {tone_desc}, Risk: {risk_desc}\n"
            f"Themes: {themes}"
        )

    def _generate_opening(
        self,
        template: ScenarioTemplate,
        character: CharacterData
    ) -> str:
        """Generate opening text if not provided by template."""
        location = template.locations[0]["name"] if template.locations else "the city"
        return (
            f"The neon lights of {location} flicker in the perpetual rain. "
            f"You are {character.name}, and tonight, everything changes."
        )


def run_setup(
    state_store: StateStore,
    template_id: str,
    calibration_preset: str = "noir_standard",
    character_responses: Optional[dict] = None,
    campaign_id: Optional[str] = None
) -> dict:
    """Convenience function to run setup."""
    pipeline = SetupPipeline(state_store)
    result = pipeline.run_setup(
        template_id=template_id,
        calibration_preset=calibration_preset,
        character_responses=character_responses,
        campaign_id=campaign_id
    )
    return result.to_dict()
