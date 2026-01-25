"""
Context Builder - Constructs context packets for LLM prompts.

Handles state loading, perception filtering, and priority-based selection.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..db.state_store import StateStore


@dataclass
class ContextOptions:
    """Options for context building."""
    max_entities: int = 50
    max_facts: int = 100
    max_recent_events: int = 5
    include_world_facts: bool = False  # Include facts player hasn't discovered
    include_obscured: bool = False  # Include obscured entities


class ContextBuilder:
    """
    Builds context packets for LLM prompts.

    Applies perception filtering to ensure the LLM only sees what
    the player character can perceive.
    """

    def __init__(self, state_store: StateStore):
        self.store = state_store

    def build_context(
        self,
        campaign_id: str,
        player_input: str,
        options: Optional[ContextOptions] = None
    ) -> dict:
        """
        Build a context packet for the current game state.

        Returns a ContextPacket dict ready for LLM injection.
        """
        options = options or ContextOptions()

        # Get campaign config
        campaign = self.store.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign not found: {campaign_id}")

        # Get current scene
        scene = self.store.get_scene()
        if not scene:
            scene = {
                "location_id": "unknown",
                "present_entity_ids": [],
                "time": {"utc": datetime.utcnow().isoformat()},
                "constraints": {},
                "visibility_conditions": "normal",
                "noise_level": "normal",
                "obscured_entities": []
            }

        # Get entities in scene (with perception filtering)
        present_ids = scene["present_entity_ids"]
        obscured_ids = set(scene.get("obscured_entities", []))

        if not options.include_obscured:
            # Filter out obscured entities
            visible_ids = [eid for eid in present_ids if eid not in obscured_ids]
        else:
            visible_ids = present_ids

        # Apply entity limit
        visible_ids = visible_ids[:options.max_entities]

        entities = self.store.get_entities_by_ids(visible_ids)

        # Get facts (with perception filtering)
        if options.include_world_facts:
            # Include all facts about visible entities
            all_facts = []
            for entity in entities:
                all_facts.extend(self.store.get_facts_for_subject(entity["id"]))
        else:
            # Only include known facts
            all_facts = self.store.get_known_facts()

        # Filter to facts about entities in context
        entity_ids = {e["id"] for e in entities}
        facts = [f for f in all_facts if f["subject_id"] in entity_ids]
        facts = facts[:options.max_facts]

        # Get clocks
        clocks = self.store.get_all_clocks()

        # Get active threads
        threads = self.store.get_active_threads()

        # Get player inventory (assuming player entity has id 'player')
        inventory = self.store.get_inventory("player")

        # Get recent events for summary
        current_turn = campaign.get("current_turn", 0)
        start_turn = max(1, current_turn - options.max_recent_events + 1)
        recent_events = []
        if current_turn > 0:
            events = self.store.get_events_range(campaign_id, start_turn, current_turn)
            recent_events = [
                {"turn_no": e["turn_no"], "text": e["final_text"][:500]}
                for e in events
            ]

        # Build context packet
        context_packet = {
            "scene": {
                "location_id": scene["location_id"],
                "time": scene["time"],
                "constraints": scene["constraints"],
                "visibility_conditions": scene.get("visibility_conditions", "normal"),
                "noise_level": scene.get("noise_level", "normal")
            },
            "present_entities": visible_ids,
            "entities": self._format_entities(entities),
            "facts": self._format_facts(facts),
            "threads": self._format_threads(threads),
            "clocks": self._format_clocks(clocks),
            "inventory": self._format_inventory(inventory),
            "summary": self._build_summary(campaign, recent_events),
            "recent_events": recent_events,
            # Include calibration for tone/theme awareness
            "calibration": {
                "tone": campaign.get("calibration", {}).get("tone", {}),
                "themes": campaign.get("calibration", {}).get("themes", {}),
                "risk": campaign.get("calibration", {}).get("risk", {})
            },
            "genre_rules": campaign.get("genre_rules", {})
        }

        return context_packet

    def _format_entities(self, entities: list[dict]) -> list[dict]:
        """Format entities for context packet."""
        return [
            {
                "id": e["id"],
                "type": e["type"],
                "name": e["name"],
                "attrs": e["attrs"],
                "tags": e["tags"]
            }
            for e in entities
        ]

    def _format_facts(self, facts: list[dict]) -> list[dict]:
        """Format facts for context packet."""
        return [
            {
                "id": f["id"],
                "subject_id": f["subject_id"],
                "predicate": f["predicate"],
                "object": f["object"],
                "visibility": f["visibility"],
                "confidence": f["confidence"],
                "tags": f["tags"]
            }
            for f in facts
        ]

    def _format_threads(self, threads: list[dict]) -> list[dict]:
        """Format threads for context packet."""
        return [
            {
                "id": t["id"],
                "title": t["title"],
                "status": t["status"],
                "stakes": t["stakes"],
                "related_entity_ids": t["related_entity_ids"],
                "tags": t["tags"]
            }
            for t in threads
        ]

    def _format_clocks(self, clocks: list[dict]) -> list[dict]:
        """Format clocks for context packet."""
        return [
            {
                "id": c["id"],
                "name": c["name"],
                "value": c["value"],
                "max": c["max"],
                "triggers": c["triggers"],
                "tags": c["tags"]
            }
            for c in clocks
        ]

    def _format_inventory(self, inventory: list[dict]) -> list[dict]:
        """Format inventory for context packet."""
        return [
            {
                "owner_id": i["owner_id"],
                "item_id": i["item_id"],
                "qty": i["qty"],
                "flags": i["flags"]
            }
            for i in inventory
        ]

    def _build_summary(self, campaign: dict, recent_events: list[dict]) -> dict:
        """Build summary section."""
        # Get scene summary from recent events
        scene_summary = ""
        if recent_events:
            last_event = recent_events[-1]
            scene_summary = last_event.get("text", "")[:200]

        # Get thread summary from campaign
        thread_summary = ""
        threads = self.store.get_active_threads()
        if threads:
            thread_titles = [t["title"] for t in threads[:3]]
            thread_summary = "Active: " + ", ".join(thread_titles)

        return {
            "scene": scene_summary,
            "threads": thread_summary
        }

    def get_entity_perception(
        self,
        entity_id: str,
        scene: Optional[dict] = None
    ) -> dict:
        """
        Check if an entity can be perceived.

        Returns dict with:
            - perceivable: bool
            - reason: str (if not perceivable)
            - clarity: str ('clear', 'obscured', 'unknown')
        """
        if scene is None:
            scene = self.store.get_scene()

        if not scene:
            return {
                "perceivable": False,
                "reason": "no_scene",
                "clarity": "unknown"
            }

        present_ids = set(scene.get("present_entity_ids", []))
        obscured_ids = set(scene.get("obscured_entities", []))

        if entity_id not in present_ids:
            # Check if entity exists at all
            entity = self.store.get_entity(entity_id)
            if not entity:
                return {
                    "perceivable": False,
                    "reason": "not_known",
                    "clarity": "unknown"
                }
            return {
                "perceivable": False,
                "reason": "not_present",
                "clarity": "unknown"
            }

        if entity_id in obscured_ids:
            return {
                "perceivable": True,
                "reason": None,
                "clarity": "obscured"
            }

        return {
            "perceivable": True,
            "reason": None,
            "clarity": "clear"
        }


def build_context(
    state_store: StateStore,
    campaign_id: str,
    player_input: str,
    options: Optional[ContextOptions] = None
) -> dict:
    """Convenience function to build context packet."""
    builder = ContextBuilder(state_store)
    return builder.build_context(campaign_id, player_input, options)
