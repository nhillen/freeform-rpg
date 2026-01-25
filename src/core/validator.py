"""
Validator - Enforces game rules and constraints on proposed actions.

Checks presence, inventory, location feasibility, and contradiction rules.
Assigns costs to allowed actions.
"""

from dataclasses import dataclass, field
from typing import Optional

from ..db.state_store import StateStore
from ..context.builder import ContextBuilder


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

    def to_dict(self) -> dict:
        return {
            "allowed_actions": self.allowed_actions,
            "blocked_actions": self.blocked_actions,
            "clarification_needed": self.clarification_needed,
            "clarification_question": self.clarification_question,
            "costs": self.costs
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

    # Default costs by action category
    DEFAULT_COSTS = {
        "violence": {"heat": 1},
        "combat": {"heat": 1},
        "attack": {"heat": 1},
        "social": {"time": 1},
        "talk": {"time": 1},
        "investigate": {"time": 1},
        "search": {"time": 1},
        "examine": {"time": 1},
        "travel": {"time": 1},
        "move": {"time": 1},
        "go": {"time": 1},
        "crime": {"heat": 2},
        "steal": {"heat": 2, "time": 1},
        "hack": {"heat": 1, "time": 1},
        "bribe": {"cred": 50},
        "buy": {"cred": 0},  # Amount determined by context
    }

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
        allowed_actions = []
        blocked_actions = []
        total_costs = {"heat": 0, "time": 0, "cred": 0, "harm": 0, "rep": 0}

        proposed_actions = interpreter_output.get("proposed_actions", [])
        perception_flags = interpreter_output.get("perception_flags", [])

        # Check perception flags first - these block actions
        flagged_entities = {pf["entity_id"] for pf in perception_flags}

        for action in proposed_actions:
            result = self._validate_action(
                action,
                context_packet,
                flagged_entities
            )

            if result.allowed:
                allowed_actions.append({
                    "action": result.action,
                    "target_id": result.target_id,
                    "details": action.get("details", "")
                })
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

        return ValidatorOutput(
            allowed_actions=allowed_actions,
            blocked_actions=blocked_actions,
            clarification_needed=clarification_needed,
            clarification_question=clarification_question,
            costs=total_costs
        )

    def _validate_action(
        self,
        action: dict,
        context_packet: dict,
        flagged_entities: set
    ) -> ValidationResult:
        """Validate a single action."""
        action_type = action.get("action", "").lower()
        target_id = action.get("target_id", "")

        # Check 1: Target entity perception
        if target_id and target_id in flagged_entities:
            return ValidationResult(
                action=action_type,
                target_id=target_id,
                allowed=False,
                reason=f"Target '{target_id}' is not perceivable"
            )

        # Check 2: Target must be in present entities (if specified)
        if target_id:
            present_ids = set(context_packet.get("present_entities", []))
            # Allow targeting self or items in inventory
            inventory_items = {
                i["item_id"] for i in context_packet.get("inventory", [])
            }

            if target_id not in present_ids and target_id not in inventory_items:
                # Check if it's a known entity at all
                entity_ids = {e["id"] for e in context_packet.get("entities", [])}
                if target_id not in entity_ids:
                    return ValidationResult(
                        action=action_type,
                        target_id=target_id,
                        allowed=False,
                        reason=f"Unknown entity: '{target_id}'"
                    )
                else:
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
        costs = self._calculate_costs(action_type, action, context_packet)

        return ValidationResult(
            action=action_type,
            target_id=target_id,
            allowed=True,
            costs=costs
        )

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

        # Check for "dead" or "destroyed" facts
        if target_id:
            for fact in facts:
                if fact["subject_id"] == target_id:
                    if fact["predicate"] == "status" and fact["object"] in ["dead", "destroyed"]:
                        return f"Cannot target '{target_id}': they are {fact['object']}"

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
        context_packet: dict
    ) -> dict:
        """Calculate costs for an action."""
        # Start with default costs for action type
        costs = dict(self.DEFAULT_COSTS.get(action_type, {"time": 1}))

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
            return f"I'm not sure what you mean by '{action['action']}'. Could you clarify what you're trying to do?"

        return "Some of your intended actions aren't clear to me. Could you describe what you're trying to accomplish?"


def validate(
    state_store: StateStore,
    interpreter_output: dict,
    context_packet: dict
) -> dict:
    """Convenience function to run validation."""
    validator = Validator(state_store)
    result = validator.validate(interpreter_output, context_packet)
    return result.to_dict()
