"""
Scenario Loader - Loads scenario YAML files and populates initial game state.

Handles campaign creation, entity population, and initial state setup.
"""

from pathlib import Path
from typing import Optional

import yaml

from ..db.state_store import StateStore, new_id


class ScenarioLoader:
    """Loads scenario files and populates database with initial state."""

    def __init__(self, state_store: StateStore, scenarios_dir: Optional[Path] = None):
        self.store = state_store
        self.scenarios_dir = scenarios_dir or Path(__file__).parent.parent.parent / "scenarios"

    def list_scenarios(self) -> list[dict]:
        """List available scenarios."""
        scenarios = []
        for path in self.scenarios_dir.glob("*.yaml"):
            try:
                with open(path) as f:
                    data = yaml.safe_load(f)
                scenarios.append({
                    "id": data.get("id", path.stem),
                    "name": data.get("name", path.stem),
                    "description": data.get("description", ""),
                    "path": str(path)
                })
            except Exception as e:
                print(f"Warning: Could not load {path}: {e}")
        return scenarios

    def load_scenario(
        self,
        scenario_id: str,
        campaign_id: Optional[str] = None,
        campaign_name: Optional[str] = None
    ) -> dict:
        """
        Load a scenario and create initial game state.

        Args:
            scenario_id: ID of scenario to load (or path to YAML)
            campaign_id: Optional ID for the campaign (auto-generated if not provided)
            campaign_name: Optional name for the campaign

        Returns:
            Campaign dict with ID and summary
        """
        # Find and load scenario file
        scenario_path = self._find_scenario(scenario_id)
        with open(scenario_path) as f:
            scenario = yaml.safe_load(f)

        # Generate campaign ID if needed
        campaign_id = campaign_id or new_id()
        campaign_name = campaign_name or scenario.get("name", scenario_id)

        # Create campaign
        campaign = self.store.create_campaign(
            campaign_id=campaign_id,
            name=campaign_name,
            calibration=scenario.get("calibration", {}),
            system=scenario.get("system", {}),
            genre_rules=scenario.get("genre_rules", {})
        )

        # Load clocks
        for clock_data in scenario.get("clocks", []):
            self.store.create_clock(
                clock_id=clock_data["id"],
                name=clock_data["name"],
                value=clock_data["value"],
                max_value=clock_data["max"],
                triggers=clock_data.get("triggers", {}),
                tags=clock_data.get("tags", [])
            )

        # Load entities
        for entity_data in scenario.get("entities", []):
            self.store.create_entity(
                entity_id=entity_data["id"],
                entity_type=entity_data["type"],
                name=entity_data["name"],
                attrs=entity_data.get("attrs", {}),
                tags=entity_data.get("tags", [])
            )

        # Load facts
        for fact_data in scenario.get("facts", []):
            self.store.create_fact(
                fact_id=fact_data.get("id", new_id()),
                subject_id=fact_data["subject_id"],
                predicate=fact_data["predicate"],
                obj=fact_data.get("object", {}),
                visibility=fact_data.get("visibility", "world"),
                confidence=fact_data.get("confidence", 1.0),
                tags=fact_data.get("tags", [])
            )

        # Load relationships
        for rel_data in scenario.get("relationships", []):
            self.store.create_relationship(
                a_id=rel_data["a_id"],
                b_id=rel_data["b_id"],
                rel_type=rel_data["rel_type"],
                intensity=rel_data.get("intensity", 0),
                notes=rel_data.get("notes", {})
            )

        # Load threads
        for thread_data in scenario.get("threads", []):
            self.store.create_thread(
                thread_id=thread_data["id"],
                title=thread_data["title"],
                status=thread_data.get("status", "active"),
                stakes=thread_data.get("stakes", {}),
                related_entity_ids=thread_data.get("related_entity_ids", []),
                tags=thread_data.get("tags", [])
            )

        # Set starting scene
        starting_scene = scenario.get("starting_scene", {})
        if starting_scene:
            self.store.set_scene(
                location_id=starting_scene.get("location_id", "unknown"),
                present_entity_ids=starting_scene.get("present_entity_ids", []),
                time=starting_scene.get("time", {}),
                constraints=starting_scene.get("constraints", {}),
                visibility_conditions=starting_scene.get("visibility_conditions", "normal"),
                noise_level=starting_scene.get("noise_level", "normal"),
                obscured_entities=starting_scene.get("obscured_entities", [])
            )

        # Add initial inventory for player
        player_entity = self.store.get_entity("player")
        if player_entity:
            # Check for items in scenario
            for entity in scenario.get("entities", []):
                if entity["type"] == "item" and "equipped" in entity.get("tags", []):
                    self.store.add_inventory("player", entity["id"], 1)

            # Add credstick if player has cred clock
            cred_clock = self.store.get_clock_by_name("Cred")
            if cred_clock:
                self.store.add_inventory("player", "credstick", 1, {"value": cred_clock["value"]})

        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "scenario_id": scenario.get("id", scenario_id),
            "scenario_name": scenario.get("name", ""),
            "opening_text": scenario.get("opening_text", ""),
            "entities_loaded": len(scenario.get("entities", [])),
            "facts_loaded": len(scenario.get("facts", [])),
            "clocks_loaded": len(scenario.get("clocks", []))
        }

    def _find_scenario(self, scenario_id: str) -> Path:
        """Find scenario file by ID or path."""
        # Check if it's a direct path
        if Path(scenario_id).exists():
            return Path(scenario_id)

        # Check scenarios directory
        scenario_path = self.scenarios_dir / f"{scenario_id}.yaml"
        if scenario_path.exists():
            return scenario_path

        # Check with yml extension
        scenario_path = self.scenarios_dir / f"{scenario_id}.yml"
        if scenario_path.exists():
            return scenario_path

        raise FileNotFoundError(f"Scenario not found: {scenario_id}")


def load_scenario(
    state_store: StateStore,
    scenario_id: str,
    campaign_id: Optional[str] = None
) -> dict:
    """Convenience function to load a scenario."""
    loader = ScenarioLoader(state_store)
    return loader.load_scenario(scenario_id, campaign_id)
