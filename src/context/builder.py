"""
Context Builder - Constructs context packets for LLM prompts.

Handles state loading, perception filtering, and priority-based selection.
"""

import json
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
    include_lore: bool = True  # Include lore_context if available


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
        options: Optional[ContextOptions] = None,
        lore_context: Optional[dict] = None
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

        # Filter to facts about entities in context, plus scene-level facts
        entity_ids = {e["id"] for e in entities}
        facts = [
            f for f in all_facts
            if f["subject_id"] in entity_ids
            or f["subject_id"] == "scene"
            or f.get("predicate") == "narrator_established"
        ]
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
            "genre_rules": campaign.get("genre_rules", {}),
            "system": campaign.get("system", {}),
            # Enriched context sections
            "relationships": self._get_player_relationships(),
            "npc_agendas": self._extract_npc_agendas(entities),
            "investigation_progress": self._compute_investigation_progress(threads),
            "pending_threats": self._get_pending_threats(),
            "npc_capabilities": self._extract_npc_capabilities(entities),
            "active_situations": self._get_active_situations(),
            "failure_streak": self._compute_failure_streak(campaign_id),
            # Lore context from content packs (empty when no packs loaded)
            "lore_context": lore_context if (options.include_lore and lore_context) else {}
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

    def _get_player_relationships(self) -> list[dict]:
        """Get player's relationships, enriched with entity names."""
        rels = self.store.get_relationships_for_entity("player")
        result = []
        for rel in rels:
            other_id = rel["b_id"] if rel["a_id"] == "player" else rel["a_id"]
            other_entity = self.store.get_entity(other_id)
            other_name = other_entity["name"] if other_entity else other_id
            result.append({
                "entity_id": other_id,
                "entity_name": other_name,
                "rel_type": rel["rel_type"],
                "intensity": rel["intensity"],
                "notes": rel["notes"]
            })
        return result

    def _extract_npc_agendas(self, entities: list[dict]) -> list[dict]:
        """Extract agendas from NPC entities present in scene."""
        agendas = []
        for entity in entities:
            if entity.get("type") == "npc":
                agenda = entity.get("attrs", {}).get("agenda")
                if agenda:
                    agendas.append({
                        "entity_id": entity["id"],
                        "name": entity["name"],
                        "agenda": agenda
                    })
        return agendas

    def _compute_investigation_progress(self, threads: list[dict]) -> dict:
        """Compute clue discovery progress per active thread."""
        progress = {}
        for thread in threads:
            thread_id = thread["id"]
            related_ids = set(thread.get("related_entity_ids", []))

            # Gather all facts related to this thread
            thread_facts = []
            for eid in related_ids:
                thread_facts.extend(self.store.get_facts_for_subject(eid))
            # Also include facts tagged with this thread ID
            scene_facts = self.store.get_facts_for_subject("scene")
            for f in scene_facts:
                if thread_id in f.get("tags", []):
                    thread_facts.append(f)

            # Deduplicate
            seen_ids = set()
            unique_facts = []
            for f in thread_facts:
                if f["id"] not in seen_ids:
                    seen_ids.add(f["id"])
                    unique_facts.append(f)

            # Count clues
            total_clues = 0
            found_clues = 0
            last_turn = None
            for fact in unique_facts:
                tags = fact.get("tags", [])
                is_clue = any(t in tags for t in ["clue", "discovery", "secret", "player_discovery"])
                if is_clue:
                    total_clues += 1
                    if fact["visibility"] == "known":
                        found_clues += 1
                        dt = fact.get("discovered_turn")
                        if dt is not None and (last_turn is None or dt > last_turn):
                            last_turn = dt

            if total_clues > 0:
                progress[thread_id] = {
                    "thread_name": thread["title"],
                    "clues_found": found_clues,
                    "clues_total": total_clues,
                    "last_clue_turn": last_turn
                }
        return progress

    def _get_pending_threats(self) -> list[dict]:
        """Get active pending_threat facts for soft/hard move tracking."""
        facts = self.store.get_facts_for_subject("scene")
        threats = []
        for fact in facts:
            if fact["predicate"] == "pending_threat" and fact["visibility"] == "known":
                obj = fact["object"] if isinstance(fact["object"], dict) else {"description": str(fact["object"])}
                threats.append({
                    "fact_id": fact["id"],
                    "description": obj.get("description", str(fact["object"])),
                    "turn_declared": obj.get("turn_issued") or fact.get("discovered_turn"),
                    "severity": obj.get("threat_type", "soft")
                })
        return threats

    def _extract_npc_capabilities(self, entities: list[dict]) -> list[dict]:
        """Extract capability data from NPC entities present in scene."""
        capabilities = []
        for entity in entities:
            if entity.get("type") != "npc":
                continue
            attrs = entity.get("attrs", {})
            # Only include if the NPC has any capability-related attrs
            if not any(k in attrs for k in ("threat_level", "capabilities", "equipment", "limitations", "escalation_profile")):
                continue
            capabilities.append({
                "entity_id": entity["id"],
                "name": entity["name"],
                "threat_level": attrs.get("threat_level", "low"),
                "capabilities": attrs.get("capabilities", []),
                "equipment": attrs.get("equipment", []),
                "limitations": attrs.get("limitations", []),
                "escalation_profile": attrs.get("escalation_profile", {})
            })
        return capabilities

    def _get_active_situations(self) -> list[dict]:
        """Get active situation facts affecting the player."""
        facts = self.store.get_facts_for_subject("player")
        situations = []
        for fact in facts:
            if fact["predicate"] != "situation":
                continue
            obj = fact["object"] if isinstance(fact["object"], dict) else {}
            if not obj.get("active", False):
                continue
            situations.append({
                "fact_id": fact["id"],
                "condition": obj.get("condition", "unknown"),
                "severity": obj.get("severity", "soft"),
                "narrative_hint": obj.get("narrative_hint", ""),
                "source_action": obj.get("source_action", ""),
                "source_turn": obj.get("source_turn"),
                "clears_on": obj.get("clears_on", [])
            })
        return situations

    def _compute_failure_streak(self, campaign_id: str) -> dict:
        """Compute consecutive failure streak from recent event history."""
        streak = {"count": 0, "actions": [], "during_threat": False}

        campaign = self.store.get_campaign(campaign_id)
        if not campaign:
            return streak

        current_turn = campaign.get("current_turn", 0)
        if current_turn <= 0:
            return streak

        # Walk backwards through recent turns (up to 10)
        start_turn = max(1, current_turn - 9)
        events = self.store.get_events_range(campaign_id, start_turn, current_turn)

        # Process in reverse chronological order
        consecutive_failures = 0
        failed_actions = []

        for event in reversed(events):
            engine_events_raw = event.get("engine_events_json", "[]")
            if isinstance(engine_events_raw, str):
                try:
                    engine_events = json.loads(engine_events_raw)
                except (json.JSONDecodeError, TypeError):
                    engine_events = []
            else:
                engine_events = engine_events_raw

            # Check if this turn had any player actions
            player_action_events = [
                e for e in engine_events
                if e.get("type") in ("action_succeeded", "action_failed", "action_partial")
            ]

            if not player_action_events:
                continue  # Skip turns with no player actions (clarification, etc.)

            # Check if all player actions failed
            has_success = any(
                e["type"] in ("action_succeeded", "action_partial")
                for e in player_action_events
            )

            if has_success:
                break  # Streak broken

            # All failed
            consecutive_failures += 1
            for e in player_action_events:
                action = e.get("details", {}).get("action", "")
                if action:
                    failed_actions.append(action)

        streak["count"] = consecutive_failures
        streak["actions"] = failed_actions

        # Check if currently during an active threat
        pending_threats = self._get_pending_threats()
        if pending_threats:
            streak["during_threat"] = True

        return streak

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
    options: Optional[ContextOptions] = None,
    lore_context: Optional[dict] = None
) -> dict:
    """Convenience function to build context packet."""
    builder = ContextBuilder(state_store)
    return builder.build_context(campaign_id, player_input, options, lore_context)
