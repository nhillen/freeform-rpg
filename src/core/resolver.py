"""
Resolver - Executes validated actions and produces state changes.

Handles dice rolls, clock updates, fact discovery, and state diffs.
"""

import random
from dataclasses import dataclass, field
from typing import Optional, Tuple

from ..db.state_store import StateStore


@dataclass
class RollResult:
    """Result of a dice roll."""
    dice: str
    raw_values: list[int]
    total: int
    outcome: str  # 'failure', 'mixed', 'success', 'critical'
    margin: int  # How far above/below threshold


@dataclass
class ResolverOutput:
    """Output from the Resolver stage."""
    engine_events: list[dict]
    state_diff: dict
    rolls: list[RollResult]

    def to_dict(self) -> dict:
        return {
            "engine_events": self.engine_events,
            "state_diff": self.state_diff,
            "rolls": [
                {
                    "dice": r.dice,
                    "raw_values": r.raw_values,
                    "total": r.total,
                    "outcome": r.outcome,
                    "margin": r.margin
                }
                for r in self.rolls
            ]
        }


class Resolver:
    """
    Resolves validated actions into concrete outcomes.

    Responsibilities:
    - Apply costs from validator (regardless of success)
    - Execute dice rolls when outcomes are uncertain
    - Determine action outcomes (success, failure, mixed)
    - Emit engine events for narrative generation
    - Produce state diffs for database commit
    """

    # Default roll system (2d6 bands)
    DEFAULT_ROLL_BANDS = {
        "failure": (2, 6),
        "mixed": (7, 9),
        "success": (10, 12)
    }

    def __init__(self, state_store: StateStore):
        self.store = state_store

    def resolve(
        self,
        context_packet: dict,
        validator_output: dict,
        planner_output: dict,
        options: Optional[dict] = None
    ) -> ResolverOutput:
        """
        Resolve validated actions into outcomes.

        Args:
            context_packet: Current context
            validator_output: Output from Validator
            planner_output: Output from Planner
            options: Resolution options (e.g., force_outcome for testing)

        Returns:
            ResolverOutput with events, state_diff, and rolls
        """
        options = options or {}

        engine_events = []
        rolls = []
        state_diff = {
            "clocks": [],
            "facts_add": [],
            "facts_update": [],
            "inventory_changes": [],
            "scene_update": {},
            "threads_update": []
        }

        # Get game system from context (for roll mechanics)
        calibration = context_packet.get("calibration", {})
        risk_settings = calibration.get("risk", {})

        # Apply costs first (they happen regardless of outcome)
        costs = validator_output.get("costs", {})
        self._apply_costs(costs, state_diff)

        # Resolve each allowed action
        for action in validator_output.get("allowed_actions", []):
            action_events, action_rolls, action_diff = self._resolve_action(
                action,
                context_packet,
                planner_output,
                risk_settings,
                options
            )
            engine_events.extend(action_events)
            rolls.extend(action_rolls)
            self._merge_diff(state_diff, action_diff)

        # Process planner tension move (if any)
        tension_move = planner_output.get("tension_move")
        if tension_move:
            tension_events, tension_diff = self._apply_tension_move(
                tension_move,
                context_packet
            )
            engine_events.extend(tension_events)
            self._merge_diff(state_diff, tension_diff)

        return ResolverOutput(
            engine_events=engine_events,
            state_diff=state_diff,
            rolls=rolls
        )

    def _apply_costs(self, costs: dict, state_diff: dict) -> None:
        """Apply costs to state diff."""
        clock_names = ["heat", "time", "cred", "harm", "rep"]

        for clock_name in clock_names:
            delta = costs.get(clock_name, 0)
            if delta != 0:
                # Time decrements, others increment
                if clock_name == "time":
                    delta = -delta
                state_diff["clocks"].append({
                    "id": clock_name,
                    "delta": delta
                })

    def _resolve_action(
        self,
        action: dict,
        context_packet: dict,
        planner_output: dict,
        risk_settings: dict,
        options: dict
    ) -> Tuple[list[dict], list[RollResult], dict]:
        """Resolve a single action."""
        events = []
        rolls = []
        diff = {
            "clocks": [],
            "facts_add": [],
            "facts_update": [],
            "inventory_changes": [],
            "scene_update": {},
            "threads_update": []
        }

        action_type = action.get("action", "")
        target_id = action.get("target_id", "")
        details = action.get("details", "")

        # Determine if roll is needed
        needs_roll = self._needs_roll(action_type, context_packet)

        if needs_roll:
            # Perform roll
            roll_result = self._roll(options.get("force_roll"))
            rolls.append(roll_result)

            # Determine outcome based on roll
            outcome = roll_result.outcome
        else:
            # Auto-success for non-risky actions
            outcome = "success"

        # Generate events based on outcome
        if outcome == "success" or outcome == "critical":
            events.append({
                "type": "action_succeeded",
                "details": {
                    "action": action_type,
                    "target_id": target_id,
                    "description": details,
                    "critical": outcome == "critical"
                },
                "tags": ["player_action"]
            })

            # Apply action-specific effects
            action_diff = self._apply_success_effects(
                action_type, target_id, details, context_packet
            )
            self._merge_diff(diff, action_diff)

        elif outcome == "mixed":
            events.append({
                "type": "action_partial",
                "details": {
                    "action": action_type,
                    "target_id": target_id,
                    "description": details,
                    "complication": self._generate_complication(action_type, context_packet)
                },
                "tags": ["player_action", "complication"]
            })

            # Partial success - some effect plus complication
            action_diff = self._apply_mixed_effects(
                action_type, target_id, details, context_packet, risk_settings
            )
            self._merge_diff(diff, action_diff)

        else:  # failure
            events.append({
                "type": "action_failed",
                "details": {
                    "action": action_type,
                    "target_id": target_id,
                    "description": details,
                    "consequence": self._generate_consequence(action_type, context_packet, risk_settings)
                },
                "tags": ["player_action", "failure"]
            })

            # Failure - consequence without effect
            action_diff = self._apply_failure_effects(
                action_type, target_id, context_packet, risk_settings
            )
            self._merge_diff(diff, action_diff)

        return events, rolls, diff

    def _needs_roll(self, action_type: str, context_packet: dict) -> bool:
        """Determine if an action needs a roll."""
        # Safe actions that don't need rolls
        safe_actions = {
            "look", "examine", "observe", "listen", "wait",
            "think", "remember", "talk", "ask", "say"
        }

        if action_type.lower() in safe_actions:
            return False

        # Risky actions need rolls
        risky_actions = {
            "attack", "fight", "combat", "shoot", "steal",
            "hack", "sneak", "climb", "jump", "chase",
            "persuade", "intimidate", "deceive", "negotiate"
        }

        if action_type.lower() in risky_actions:
            return True

        # Default: roll for uncertain outcomes
        return True

    def _roll(self, forced_total: Optional[int] = None) -> RollResult:
        """Perform a 2d6 roll."""
        if forced_total is not None:
            # For testing - distribute forced total across dice
            d1 = min(6, max(1, forced_total // 2))
            d2 = forced_total - d1
            raw_values = [d1, d2]
            total = forced_total
        else:
            raw_values = [random.randint(1, 6), random.randint(1, 6)]
            total = sum(raw_values)

        # Determine outcome from bands
        if total <= 6:
            outcome = "failure"
            margin = 7 - total
        elif total <= 9:
            outcome = "mixed"
            margin = 0
        elif total == 12:
            outcome = "critical"
            margin = total - 10
        else:
            outcome = "success"
            margin = total - 10

        return RollResult(
            dice="2d6",
            raw_values=raw_values,
            total=total,
            outcome=outcome,
            margin=margin
        )

    def _apply_success_effects(
        self,
        action_type: str,
        target_id: str,
        details: str,
        context_packet: dict
    ) -> dict:
        """Apply effects for successful action."""
        diff = {
            "clocks": [],
            "facts_add": [],
            "facts_update": [],
            "inventory_changes": [],
            "scene_update": {},
            "threads_update": []
        }

        # Investigation actions discover facts
        if action_type.lower() in ["investigate", "search", "examine", "hack"]:
            # In a real implementation, this would reveal specific facts
            # For now, just mark the action type
            diff["facts_add"].append({
                "subject_id": target_id or "scene",
                "predicate": "investigated_by_player",
                "object": {"action": action_type, "details": details},
                "visibility": "known",
                "tags": ["player_discovery"]
            })

        # Social actions might improve relationships
        if action_type.lower() in ["talk", "persuade", "help"]:
            # Would update relationship intensity
            pass

        return diff

    def _apply_mixed_effects(
        self,
        action_type: str,
        target_id: str,
        details: str,
        context_packet: dict,
        risk_settings: dict
    ) -> dict:
        """Apply effects for mixed success."""
        diff = self._apply_success_effects(action_type, target_id, details, context_packet)

        # Add complication cost
        complication_cost = 1
        if risk_settings.get("failure_mode") == "punishing":
            complication_cost = 2

        # Usually adds heat or time
        if action_type.lower() in ["combat", "attack", "violence"]:
            diff["clocks"].append({"id": "heat", "delta": complication_cost})
        else:
            diff["clocks"].append({"id": "time", "delta": -complication_cost})

        return diff

    def _apply_failure_effects(
        self,
        action_type: str,
        target_id: str,
        context_packet: dict,
        risk_settings: dict
    ) -> dict:
        """Apply effects for failed action."""
        diff = {
            "clocks": [],
            "facts_add": [],
            "facts_update": [],
            "inventory_changes": [],
            "scene_update": {},
            "threads_update": []
        }

        # Failures have consequences based on risk settings
        failure_mode = risk_settings.get("failure_mode", "consequential")

        if failure_mode == "forgiving":
            # Minor consequence - just time lost
            diff["clocks"].append({"id": "time", "delta": -1})

        elif failure_mode == "consequential":
            # Moderate consequence
            if action_type.lower() in ["combat", "attack"]:
                diff["clocks"].append({"id": "harm", "delta": 1})
            else:
                diff["clocks"].append({"id": "heat", "delta": 1})

        else:  # punishing
            # Severe consequence
            if action_type.lower() in ["combat", "attack"]:
                diff["clocks"].append({"id": "harm", "delta": 2})
            diff["clocks"].append({"id": "heat", "delta": 1})

        return diff

    def _generate_complication(self, action_type: str, context_packet: dict) -> str:
        """Generate a complication description for mixed success."""
        complications = {
            "combat": ["You're exposed", "Weapon jammed", "They called for backup"],
            "social": ["They're suspicious now", "Someone overheard", "It'll cost you"],
            "stealth": ["You left evidence", "Someone noticed", "Took longer than expected"],
            "investigate": ["Incomplete information", "Trail goes cold", "Someone knows you're asking"],
            "default": ["An unexpected complication", "Things got messy", "Not quite what you hoped"]
        }

        category = "default"
        if action_type.lower() in ["attack", "fight", "shoot"]:
            category = "combat"
        elif action_type.lower() in ["talk", "persuade", "negotiate"]:
            category = "social"
        elif action_type.lower() in ["sneak", "steal", "hide"]:
            category = "stealth"
        elif action_type.lower() in ["investigate", "search", "examine"]:
            category = "investigate"

        return random.choice(complications[category])

    def _generate_consequence(
        self,
        action_type: str,
        context_packet: dict,
        risk_settings: dict
    ) -> str:
        """Generate a consequence description for failure."""
        lethality = risk_settings.get("lethality", "moderate")

        if lethality == "low":
            consequences = ["Setback", "Lost opportunity", "Minor trouble"]
        elif lethality == "brutal":
            consequences = ["Serious harm", "Major exposure", "Everything goes wrong"]
        else:
            consequences = ["Things get worse", "Unwanted attention", "A real problem"]

        return random.choice(consequences)

    def _apply_tension_move(
        self,
        tension_move: str,
        context_packet: dict
    ) -> Tuple[list[dict], dict]:
        """Apply the planner's tension move."""
        events = []
        diff = {
            "clocks": [],
            "facts_add": [],
            "facts_update": [],
            "inventory_changes": [],
            "scene_update": {},
            "threads_update": []
        }

        # Tension moves advance clocks or create events
        if "heat" in tension_move.lower() or "attention" in tension_move.lower():
            diff["clocks"].append({"id": "heat", "delta": 1})
            events.append({
                "type": "clock_advanced",
                "details": {"clock": "heat", "reason": tension_move},
                "tags": ["tension", "gm_move"]
            })

        elif "time" in tension_move.lower() or "deadline" in tension_move.lower():
            diff["clocks"].append({"id": "time", "delta": -1})
            events.append({
                "type": "clock_advanced",
                "details": {"clock": "time", "reason": tension_move},
                "tags": ["tension", "gm_move"]
            })

        else:
            # Generic tension event
            events.append({
                "type": "npc_action",
                "details": {"description": tension_move},
                "tags": ["tension", "gm_move"]
            })

        return events, diff

    def _merge_diff(self, target: dict, source: dict) -> None:
        """Merge source diff into target diff."""
        for key in ["clocks", "facts_add", "facts_update", "inventory_changes", "threads_update"]:
            if key in source and source[key]:
                target[key].extend(source[key])

        if source.get("scene_update"):
            target["scene_update"].update(source["scene_update"])


def resolve(
    state_store: StateStore,
    context_packet: dict,
    validator_output: dict,
    planner_output: dict,
    options: Optional[dict] = None
) -> dict:
    """Convenience function to run resolution."""
    resolver = Resolver(state_store)
    result = resolver.resolve(context_packet, validator_output, planner_output, options)
    return result.to_dict()
