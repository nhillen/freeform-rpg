"""
Validator - Enforces game rules and constraints on proposed actions.

Checks presence, inventory, location feasibility, and contradiction rules.
Assigns costs to allowed actions.
"""

from dataclasses import dataclass, field
from typing import Optional

from ..db.state_store import StateStore
from ..context.builder import ContextBuilder
from .clock_config import ClockConfig, load_clock_config


@dataclass
class ValidationResult:
    """Result of validating a single action."""
    action: str
    target_id: str
    allowed: bool
    reason: Optional[str] = None
    costs: dict = field(default_factory=dict)


@dataclass
class ValidatorOutput:
    """Complete validator output matching schema."""
    allowed_actions: list[dict]
    blocked_actions: list[dict]
    clarification_needed: bool
    clarification_question: str
    costs: dict
    risk_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "allowed_actions": self.allowed_actions,
            "blocked_actions": self.blocked_actions,
            "clarification_needed": self.clarification_needed,
            "clarification_question": self.clarification_question,
            "costs": self.costs,
            "risk_flags": self.risk_flags
        }


class Validator:
    """
    Validates proposed actions against game rules.

    Rules enforced:
    1. Presence check: referenced entities must exist and be perceivable
    2. Inventory check: required items must be available
    3. Location check: actions must be feasible from current location
    4. Contradiction check: actions cannot violate established facts
    5. Cost assignment: apply Heat, Time, Cred, Harm, Rep costs
    """

    def __init__(self, state_store: StateStore):
        self.store = state_store
        self.context_builder = ContextBuilder(state_store)

    def validate(
        self,
        interpreter_output: dict,
        context_packet: dict,
        campaign_id: Optional[str] = None
    ) -> ValidatorOutput:
        """
        Validate interpreter output against game rules.

        Args:
            interpreter_output: Output from Interpreter stage
            context_packet: Current context packet
            campaign_id: Campaign ID for loading additional state

        Returns:
            ValidatorOutput with allowed/blocked actions and costs
        """
        clock_config = load_clock_config(context_packet.get("system", {}))

        allowed_actions = []
        blocked_actions = []
        total_costs = {c: 0 for c in clock_config.clocks_enabled} if clock_config.enabled else {}

        proposed_actions = interpreter_output.get("proposed_actions", [])
        perception_flags = interpreter_output.get("perception_flags", [])

        # Resolve perception flag entity IDs (LLM may use names)
        # Only flag entities that remain unresolvable to present entities
        present_ids = set(context_packet.get("present_entities", []))
        flagged_entities = set()
        for pf in perception_flags:
            resolved = self._resolve_target_id(pf["entity_id"], context_packet)
            if resolved not in present_ids:
                flagged_entities.add(resolved)

        for action in proposed_actions:
            result = self._validate_action(
                action,
                context_packet,
                flagged_entities
            )

            if result.allowed:
                allowed_action = {
                    "action": result.action,
                    "target_id": result.target_id,
                    "details": action.get("details", "")
                }
                if "estimated_minutes" in action:
                    allowed_action["estimated_minutes"] = action["estimated_minutes"]
                allowed_actions.append(allowed_action)
                # Accumulate costs
                for cost_type, amount in result.costs.items():
                    total_costs[cost_type] = total_costs.get(cost_type, 0) + amount
            else:
                blocked_actions.append({
                    "action": result.action,
                    "reason": result.reason
                })

        # Determine if clarification is needed
        clarification_needed = False
        clarification_question = ""

        # If all actions were blocked due to perception issues, ask for clarification
        if not allowed_actions and blocked_actions:
            perception_blocks = [
                b for b in blocked_actions
                if "not perceivable" in b.get("reason", "").lower()
                or "not present" in b.get("reason", "").lower()
            ]
            if perception_blocks:
                clarification_needed = True
                clarification_question = self._generate_clarification(perception_blocks)

        # Pass through risk_flags from interpreter
        risk_flags = interpreter_output.get("risk_flags", [])

        return ValidatorOutput(
            allowed_actions=allowed_actions,
            blocked_actions=blocked_actions,
            clarification_needed=clarification_needed,
            clarification_question=clarification_question,
            costs=total_costs,
            risk_flags=risk_flags
        )

    def _resolve_target_id(self, target_id: str, context_packet: dict) -> str:
        """Resolve a target reference to an entity ID.

        The LLM interpreter may return entity names instead of IDs.
        Try to match by name (case-insensitive) when the ID isn't found directly.
        """
        if not target_id:
            return target_id

        entities = context_packet.get("entities", [])

        # Direct ID match
        entity_ids = {e["id"] for e in entities}
        if target_id in entity_ids:
            return target_id

        # Name match (case-insensitive)
        target_lower = target_id.lower()
        for entity in entities:
            if entity.get("name", "").lower() == target_lower:
                return entity["id"]

        # Partial name match (e.g. "jin" matching "Jin 'The Courier' Tanaka")
        for entity in entities:
            if target_lower in entity.get("name", "").lower():
                return entity["id"]

        return target_id

    # Targets that represent the general environment, not specific entities
    META_TARGETS = {"scene", "environment", "area", "surroundings", "room", "self", "player"}

    def _validate_action(
        self,
        action: dict,
        context_packet: dict,
        flagged_entities: set
    ) -> ValidationResult:
        """Validate a single action."""
        action_type = action.get("action", "").lower()
        raw_target = action.get("target_id", "")
        target_id = self._resolve_target_id(raw_target, context_packet)

        is_meta_target = target_id and target_id.lower() in self.META_TARGETS

        # Check 1: Target entity perception (skip for meta-targets)
        if not is_meta_target and target_id and target_id in flagged_entities:
            return ValidationResult(
                action=action_type,
                target_id=target_id,
                allowed=False,
                reason=f"Target '{target_id}' is not perceivable"
            )

        # Check 2: Target must be reachable (entity, scene feature, or environment)
        if target_id and not is_meta_target:
            present_ids = set(context_packet.get("present_entities", []))
            inventory_items = {
                i["item_id"] for i in context_packet.get("inventory", [])
            }
            entity_ids = {e["id"] for e in context_packet.get("entities", [])}
            location_id = context_packet.get("scene", {}).get("location_id", "")

            target_known = (
                target_id in present_ids
                or target_id in inventory_items
                or target_id in entity_ids
                or target_id == location_id
            )

            if not target_known:
                # Check scene features (e.g. "door", "dumpster", "fire escape")
                scene_features = self._get_scene_features(context_packet)
                target_lower = target_id.lower().replace("unknown_", "")
                feature_match = any(
                    target_lower in f.lower() or f.lower() in target_lower
                    for f in scene_features
                )

                # Check narrator-established facts
                facts = context_packet.get("facts", [])
                fact_match = any(
                    target_lower in str(f.get("object", "")).lower()
                    for f in facts
                    if f.get("predicate") == "narrator_established"
                )

                if feature_match or fact_match:
                    # Scene feature / established element — allow it
                    pass
                elif self._is_environment_action(action_type):
                    # Simple physical action on the environment — allow it
                    pass
                else:
                    return ValidationResult(
                        action=action_type,
                        target_id=target_id,
                        allowed=False,
                        reason=f"Unknown entity: '{target_id}'"
                    )

            # Known entity but not present in scene
            elif target_id not in present_ids and target_id not in inventory_items and target_id != location_id:
                if target_id in entity_ids:
                    return ValidationResult(
                        action=action_type,
                        target_id=target_id,
                        allowed=False,
                        reason=f"Target '{target_id}' is not present in the current scene"
                    )

        # Check 3: Inventory requirements (for actions that need items)
        inventory_required = self._get_inventory_requirements(action_type)
        if inventory_required:
            inventory = {i["item_id"]: i["qty"] for i in context_packet.get("inventory", [])}
            for item_id, qty_needed in inventory_required.items():
                if inventory.get(item_id, 0) < qty_needed:
                    return ValidationResult(
                        action=action_type,
                        target_id=target_id,
                        allowed=False,
                        reason=f"Missing required item: '{item_id}'"
                    )

        # Check 4: Contradiction check (action vs known facts)
        contradiction = self._check_contradictions(action, context_packet)
        if contradiction:
            return ValidationResult(
                action=action_type,
                target_id=target_id,
                allowed=False,
                reason=contradiction
            )

        # Calculate costs
        clock_config = load_clock_config(context_packet.get("system", {}))
        costs = self._calculate_costs(action_type, action, context_packet, clock_config)

        return ValidationResult(
            action=action_type,
            target_id=target_id,
            allowed=True,
            costs=costs
        )

    def _get_scene_features(self, context_packet: dict) -> list[str]:
        """Get features of the current scene's location."""
        scene = context_packet.get("scene", {})
        location_id = scene.get("location_id", "")
        if not location_id:
            return []

        for entity in context_packet.get("entities", []):
            if entity["id"] == location_id:
                return entity.get("attrs", {}).get("features", [])
        return []

    def _is_environment_action(self, action_type: str) -> bool:
        """Check if this action type is a simple environment interaction."""
        environment_actions = {
            "knock", "bang", "push", "pull", "open", "close",
            "climb", "jump", "touch", "use", "enter", "exit",
            "hide", "lean", "sit", "stand", "crouch", "run",
            "move", "go", "walk", "look", "listen", "wait",
            "yell", "shout", "call", "signal",
            "drop", "throw", "toss", "discard",
            "sneak", "dodge", "duck", "crawl",
        }
        return action_type.lower() in environment_actions

    def _get_inventory_requirements(self, action_type: str) -> dict:
        """Get inventory items required for an action type."""
        requirements = {
            "shoot": {"weapon": 1, "ammo": 1},
            "unlock": {"lockpick": 1},
            "pay": {"cred": 1},  # Handled separately
        }
        return requirements.get(action_type, {})

    def _check_contradictions(self, action: dict, context_packet: dict) -> Optional[str]:
        """Check if action contradicts known facts."""
        action_type = action.get("action", "").lower()
        target_id = action.get("target_id", "")

        facts = context_packet.get("facts", [])

        # Check for "dead" or "destroyed" facts (only blocks interactive actions)
        interactive_actions = {"talk", "ask", "speak", "persuade", "intimidate", "bribe", "trade", "give"}
        if target_id:
            for fact in facts:
                if fact["subject_id"] == target_id:
                    if fact["predicate"] == "status" and fact["object"] in ["dead", "destroyed"]:
                        if action_type in interactive_actions:
                            return f"Cannot {action_type} '{target_id}': they are {fact['object']}"

        # Check for location constraints
        scene = context_packet.get("scene", {})
        constraints = scene.get("constraints", {})

        if constraints.get("no_violence") and action_type in ["attack", "combat", "violence", "shoot"]:
            return "Violence is not possible in this location"

        if constraints.get("no_magic") and action_type in ["cast", "spell", "magic"]:
            return "Magic does not work in this location"

        return None

    def _calculate_costs(
        self,
        action_type: str,
        action: dict,
        context_packet: dict,
        clock_config: Optional["ClockConfig"] = None
    ) -> dict:
        """Calculate costs for an action."""
        if clock_config is None:
            clock_config = load_clock_config(context_packet.get("system", {}))

        if not clock_config.enabled:
            return {}

        # Start with configured costs for action type
        costs = clock_config.get_cost(action_type)

        # Adjust based on calibration risk settings
        calibration = context_packet.get("calibration", {})
        risk = calibration.get("risk", {})

        # In low lethality games, reduce harm costs
        if risk.get("lethality") == "low":
            if "harm" in costs:
                costs["harm"] = max(0, costs["harm"] - 1)

        # In brutal games, increase costs
        if risk.get("lethality") == "brutal":
            for cost_type in costs:
                costs[cost_type] = int(costs[cost_type] * 1.5)

        return costs

    def _generate_clarification(self, blocked_actions: list) -> str:
        """Generate a clarification question for blocked actions."""
        if len(blocked_actions) == 1:
            action = blocked_actions[0]
            reason = action.get("reason", "")
            if "not present" in reason or "not perceivable" in reason or "Unknown entity" in reason:
                return f"You don't see anything like that here. What are you trying to interact with?"
            return f"Could you clarify what you're trying to do?"

        return "Some of your intended actions aren't clear. Could you describe what you're trying to accomplish?"


def validate(
    state_store: StateStore,
    interpreter_output: dict,
    context_packet: dict
) -> dict:
    """Convenience function to run validation."""
    validator = Validator(state_store)
    result = validator.validate(interpreter_output, context_packet)
    return result.to_dict()
