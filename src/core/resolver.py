"""
Resolver - Executes validated actions and produces state changes.

Handles dice rolls, clock updates, fact discovery, and state diffs.
"""

import random
import uuid
from dataclasses import dataclass, field
from typing import Optional, Tuple

from ..db.state_store import StateStore
from .clock_config import ClockConfig, load_clock_config


@dataclass
class RollResult:
    """Result of a dice roll."""
    dice: str
    raw_values: list[int]
    total: int
    outcome: str  # 'failure', 'mixed', 'success', 'critical'
    margin: int  # How far above/below threshold
    action: str = ""  # What action this roll was for


@dataclass
class ResolverOutput:
    """Output from the Resolver stage."""
    engine_events: list[dict]
    state_diff: dict
    rolls: list[RollResult]
    total_estimated_minutes: int = 0

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
                    "margin": r.margin,
                    "action": r.action
                }
                for r in self.rolls
            ],
            "total_estimated_minutes": self.total_estimated_minutes
        }


class Resolver:
    """
    Resolves validated actions into concrete outcomes.

    Responsibilities:
    - Apply costs from validator (regardless of success)
    - Execute dice rolls when outcomes are uncertain
    - Determine action outcomes (success, failure, mixed)
    - Create/clear situation facts based on outcomes and context
    - Apply severity-tiered failure consequences
    - Track failure streaks and resolve threats at threshold
    - Emit engine events for narrative generation
    - Produce state diffs for database commit
    """

    # Default roll system (2d6 bands)
    DEFAULT_ROLL_BANDS = {
        "failure": (2, 6),
        "mixed": (7, 9),
        "success": (10, 12)
    }

    # Maps action types to the situation condition created on failure
    CONDITION_MAP = {
        "sneak": "exposed",
        "hide": "exposed",
        "steal": "detected",
        "hack": "detected",
        "flee": "cornered",
        "chase": "pursued",
        "climb": "exposed",
        "fight": "injured",
        "attack": "injured",
        "combat": "injured",
        "deceive": "detected",
    }

    # Maps conditions to what success types clear them
    CLEAR_MAP = {
        "exposed": ["hide_success", "flee_success", "scene_change"],
        "detected": ["scene_change", "deceive_success"],
        "cornered": ["fight_success", "talk_success", "scene_change"],
        "injured": ["rest_success", "medical_success"],
        "pursued": ["flee_success", "hide_success", "fight_success"],
    }

    def __init__(self, state_store: StateStore):
        self.store = state_store

    def _resolve_duration(self, action: dict, action_type: str,
                          clock_config: Optional[ClockConfig]) -> int:
        """Resolve fictional duration in minutes for an action.

        Priority: valid LLM estimate > duration_map > hardcoded 5.
        """
        est = action.get("estimated_minutes")
        if isinstance(est, int) and 1 <= est <= 120:
            return est
        if clock_config:
            return clock_config.get_default_duration(action_type)
        return 5

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
            "threads_update": [],
            "relationship_changes": []
        }

        # Get game system from context (for roll mechanics)
        calibration = context_packet.get("calibration", {})
        risk_settings = calibration.get("risk", {})

        # Load clock configuration
        clock_config = load_clock_config(context_packet.get("system", {}))

        # Apply costs first (they happen regardless of outcome)
        costs = validator_output.get("costs", {})
        if clock_config.enabled:
            self._apply_costs(costs, state_diff, clock_config)

        # Extract risk_flags from validator output and pass through to actions
        risk_flags = validator_output.get("risk_flags", [])
        resolve_options = dict(options)
        if risk_flags:
            resolve_options["risk_flags"] = risk_flags

        # Deduplicate and cap actions (max 2, no same-type+same-target dupes)
        raw_actions = validator_output.get("allowed_actions", [])
        allowed_actions = []
        seen_keys = set()
        for action in raw_actions:
            key = (action.get("action", "").lower(), action.get("target_id", "").lower())
            if key not in seen_keys:
                seen_keys.add(key)
                allowed_actions.append(action)
            if len(allowed_actions) >= 2:
                break

        # Resolve each allowed action and sum fictional durations
        total_estimated_minutes = 0
        outcomes = []
        for action in allowed_actions:
            duration = self._resolve_duration(action, action.get("action", ""), clock_config)
            total_estimated_minutes += duration
            action_events, action_rolls, action_diff = self._resolve_action(
                action,
                context_packet,
                planner_output,
                risk_settings,
                resolve_options,
                clock_config
            )
            engine_events.extend(action_events)
            rolls.extend(action_rolls)
            self._merge_diff(state_diff, action_diff)

            # Track outcomes for streak calculation
            for event in action_events:
                if event["type"] in ("action_succeeded", "action_partial"):
                    outcomes.append("success")
                elif event["type"] == "action_failed":
                    outcomes.append("failure")

        # Process planner tension move (if any)
        tension_move = planner_output.get("tension_move")
        if tension_move:
            tension_events, tension_diff = self._apply_tension_move(
                tension_move,
                context_packet,
                clock_config
            )
            engine_events.extend(tension_events)
            self._merge_diff(state_diff, tension_diff)

        # Check failure streak and apply escalation if needed
        if outcomes:
            streak_events, streak_diff = self._check_failure_streak(
                outcomes, context_packet, clock_config
            )
            engine_events.extend(streak_events)
            self._merge_diff(state_diff, streak_diff)

        return ResolverOutput(
            engine_events=engine_events,
            state_diff=state_diff,
            rolls=rolls,
            total_estimated_minutes=total_estimated_minutes
        )

    def _apply_costs(self, costs: dict, state_diff: dict, clock_config: Optional[ClockConfig] = None) -> None:
        """Apply costs to state diff."""
        if clock_config is None:
            clock_config = ClockConfig()

        for clock_name in clock_config.clocks_enabled:
            delta = costs.get(clock_name, 0)
            if delta != 0:
                delta = clock_config.apply_direction(clock_name, delta)
                state_diff["clocks"].append({
                    "id": clock_name,
                    "delta": delta,
                    "source": "cost"
                })

    def _resolve_action(
        self,
        action: dict,
        context_packet: dict,
        planner_output: dict,
        risk_settings: dict,
        options: dict,
        clock_config: Optional[ClockConfig] = None
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
            "threads_update": [],
            "relationship_changes": []
        }

        action_type = action.get("action", "")
        target_id = action.get("target_id", "")
        details = action.get("details", "")

        # Determine if roll is needed (risk_flags passed via options)
        risk_flags = options.get("risk_flags")
        needs_roll = self._needs_roll(action_type, context_packet, risk_flags)

        if needs_roll:
            # Perform roll
            roll_result = self._roll(options.get("force_roll"))
            roll_result.action = action_type
            rolls.append(roll_result)

            # Determine outcome based on roll
            outcome = roll_result.outcome
        else:
            # Auto-success for non-risky actions
            outcome = "success"

        # Generate events based on outcome
        estimated_minutes = self._resolve_duration(action, action_type, clock_config)

        if outcome == "success" or outcome == "critical":
            event_details = {
                "action": action_type,
                "target_id": target_id,
                "description": details,
                "critical": outcome == "critical",
                "outcome_state": self._describe_outcome_state(action_type, target_id, outcome, context_packet),
                "estimated_minutes": estimated_minutes
            }

            # Include concrete discoveries for search/investigate
            if action_type.lower() in ["search", "investigate", "examine"] and target_id:
                discoveries = self._gather_search_discoveries(target_id, context_packet)
                if discoveries:
                    event_details["discoveries"] = discoveries

            events.append({
                "type": "action_succeeded",
                "details": event_details,
                "tags": ["player_action"]
            })

            # Apply action-specific effects
            action_diff = self._apply_success_effects(
                action_type, target_id, details, context_packet
            )
            self._merge_diff(diff, action_diff)

            # Emit relationship_changed events
            for rel_change in action_diff.get("relationship_changes", []):
                events.append({
                    "type": "relationship_changed",
                    "details": {
                        "a_id": rel_change["a_id"],
                        "b_id": rel_change["b_id"],
                        "rel_type": rel_change.get("rel_type", "trust"),
                        "delta": rel_change["delta"]
                    },
                    "tags": ["social", "relationship"]
                })

            # Clear resolved situation facts on success
            clear_events = self._clear_resolved_situations(
                action_type, outcome, context_packet, diff
            )
            events.extend(clear_events)

        elif outcome == "mixed":
            events.append({
                "type": "action_partial",
                "details": {
                    "action": action_type,
                    "target_id": target_id,
                    "description": details,
                    "complication": self._generate_complication(action_type, context_packet),
                    "mixed_state": "Player succeeded but at a cost — describe both the success and the complication",
                    "estimated_minutes": estimated_minutes
                },
                "tags": ["player_action", "complication"]
            })

            # Partial success - some effect plus complication
            action_diff = self._apply_mixed_effects(
                action_type, target_id, details, context_packet, risk_settings, clock_config
            )
            self._merge_diff(diff, action_diff)

            # Clear situations on mixed success too (partial counts)
            clear_events = self._clear_resolved_situations(
                action_type, outcome, context_packet, diff
            )
            events.extend(clear_events)

        else:  # failure
            # Compute severity tier for this failure
            severity_tier = self._compute_severity_tier(
                risk_flags or [], context_packet, clock_config
            )

            events.append({
                "type": "action_failed",
                "details": {
                    "action": action_type,
                    "target_id": target_id,
                    "description": details,
                    "consequence": self._generate_consequence(action_type, context_packet, risk_settings),
                    "failure_state": self._describe_failure_state(action_type, target_id, context_packet),
                    "estimated_minutes": estimated_minutes,
                    "severity_tier": severity_tier
                },
                "tags": ["player_action", "failure"]
            })

            # Apply severity-tiered failure effects
            action_diff = self._apply_failure_effects(
                action_type, target_id, context_packet, risk_settings,
                clock_config, severity_tier=severity_tier
            )
            self._merge_diff(diff, action_diff)

            # Create situation fact for tier 1+ failures
            if severity_tier >= 1:
                condition = self._map_action_to_condition(action_type)
                if condition:
                    severity_label = "hard" if severity_tier >= 2 else "soft"
                    situation_events = self._create_situation_fact(
                        action_type, target_id, severity_label,
                        context_packet, diff
                    )
                    events.extend(situation_events)

        return events, rolls, diff

    def _needs_roll(self, action_type: str, context_packet: dict, risk_flags: list = None) -> bool:
        """Determine if an action needs a roll."""
        # Safe actions that don't need rolls (in normal circumstances)
        safe_actions = {
            "look", "examine", "observe", "listen", "wait",
            "think", "remember", "talk", "ask", "say",
            "search", "investigate", "read", "check", "assess",
            "use", "take", "grab", "pickup", "drop", "give", "put",
            "open", "close", "move", "go", "enter", "exit", "walk",
        }

        # Risk flags from interpreter override safe classification
        if risk_flags and action_type.lower() in safe_actions:
            risky_flag_types = {"violence", "contested", "dangerous", "pursuit", "hostile_present"}
            if any(flag in risky_flag_types for flag in risk_flags):
                return True

        if action_type.lower() in safe_actions:
            return False

        # Risky actions need rolls
        risky_actions = {
            "attack", "fight", "combat", "shoot", "steal",
            "hack", "sneak", "climb", "jump", "chase",
            "persuade", "intimidate", "deceive", "negotiate",
            "provoke",
        }

        if action_type.lower() in risky_actions:
            return True

        # Default: roll for uncertain outcomes
        return True

    def _describe_outcome_state(self, action_type: str, target_id: str, outcome: str, context_packet: dict) -> str:
        """Describe what the outcome means in concrete terms for the narrator."""
        states = {
            "sneak": "Player is undetected and in a concealed position",
            "hide": "Player is hidden from view",
            "climb": "Player has reached the higher/lower position",
            "move": "Player has relocated successfully",
            "flee": "Player has escaped the immediate threat",
            "chase": "Player is gaining/closing distance",
            "persuade": f"Target {target_id} is convinced and willing to cooperate",
            "intimidate": f"Target {target_id} is frightened and backing down",
            "deceive": f"Target {target_id} believes the deception",
            "hack": f"Player has access to {target_id}'s systems",
            "steal": f"Player has taken the item without being noticed",
            "search": f"Player has thoroughly examined {target_id}",
            "investigate": f"Player has gathered information from {target_id}",
        }
        base = states.get(action_type.lower(), f"Player's {action_type} on {target_id} succeeded")
        if outcome == "critical":
            base += " — exceptionally well"
        return base

    def _describe_failure_state(self, action_type: str, target_id: str, context_packet: dict) -> str:
        """Describe what failure means in concrete terms for the narrator."""
        states = {
            "sneak": "Player's sneak attempt was detected — they are now exposed",
            "hide": "Player failed to find cover — they are visible",
            "climb": "Player couldn't make the climb — still at original position",
            "move": "Player was unable to reach their destination",
            "flee": "Player failed to escape — still trapped",
            "chase": "Player lost ground in the pursuit",
            "persuade": f"Target {target_id} is unconvinced and may be more guarded",
            "intimidate": f"Target {target_id} is unimpressed and may be hostile",
            "deceive": f"Target {target_id} saw through the deception",
            "hack": f"Player failed to breach {target_id}'s systems — may have triggered alerts",
            "steal": f"Player's theft attempt was noticed",
            "search": f"Player found nothing useful on {target_id}",
            "investigate": f"Player's investigation of {target_id} came up empty",
        }
        return states.get(action_type.lower(), f"Player's {action_type} on {target_id} failed")

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
            "threads_update": [],
            "relationship_changes": []
        }

        # Investigation actions discover facts and surface entity info
        if action_type.lower() in ["investigate", "search", "examine", "hack"]:
            diff["facts_add"].append({
                "subject_id": target_id or "scene",
                "predicate": "investigated_by_player",
                "object": {"action": action_type, "details": details},
                "visibility": "known",
                "tags": ["player_discovery"]
            })

            # Reveal hidden (world-visibility) facts about the target
            if target_id:
                all_facts = self.store.get_facts_for_subject(target_id)
                for fact in all_facts:
                    if fact.get("visibility") == "world":
                        diff["facts_update"].append({
                            "id": fact["id"],
                            "visibility": "known"
                        })

        # Social actions update relationships
        if action_type.lower() in ["talk", "persuade", "help", "negotiate"]:
            if target_id and target_id.lower() not in ("scene", "self", "player"):
                diff["relationship_changes"].append({
                    "a_id": "player",
                    "b_id": target_id,
                    "rel_type": "trust",
                    "delta": 1
                })

        return diff

    def _gather_search_discoveries(
        self,
        target_id: str,
        context_packet: dict
    ) -> list[dict]:
        """Gather discoverable information about a search target for engine events."""
        discoveries = []

        # Surface entity attrs as discoverable info
        entity = self.store.get_entity(target_id)
        if entity:
            attrs = entity.get("attrs", {})
            # Surface relevant attributes
            for key in ["knowledge", "cause_of_death", "status", "description"]:
                if key in attrs:
                    discoveries.append({
                        "type": key,
                        "detail": attrs[key]
                    })

        # Surface any hidden facts about this entity being revealed
        all_facts = self.store.get_facts_for_subject(target_id)
        for fact in all_facts:
            if fact.get("visibility") == "world":
                discoveries.append({
                    "type": "hidden_fact",
                    "predicate": fact["predicate"],
                    "detail": fact["object"]
                })

        # Check inventory (items the entity is carrying)
        try:
            inventory = self.store.get_inventory(target_id)
            for item in inventory:
                item_entity = self.store.get_entity(item["item_id"])
                if item_entity:
                    discoveries.append({
                        "type": "item_found",
                        "item_id": item["item_id"],
                        "name": item_entity.get("name", item["item_id"]),
                        "detail": item_entity.get("attrs", {}).get("description", "")
                    })
        except Exception:
            pass

        return discoveries

    def _apply_mixed_effects(
        self,
        action_type: str,
        target_id: str,
        details: str,
        context_packet: dict,
        risk_settings: dict,
        clock_config: Optional[ClockConfig] = None
    ) -> dict:
        """Apply effects for mixed success."""
        if clock_config is None:
            clock_config = load_clock_config(context_packet.get("system", {}))

        diff = self._apply_success_effects(action_type, target_id, details, context_packet)

        if not clock_config.enabled:
            return diff

        # Add complication cost
        multiplier = 2 if risk_settings.get("failure_mode") == "punishing" else 1

        for effect in clock_config.get_complication_effects(action_type):
            clock_id = effect["id"]
            delta = effect["delta"] * multiplier
            delta = clock_config.apply_direction(clock_id, delta)
            diff["clocks"].append({"id": clock_id, "delta": delta, "source": "complication"})

        return diff

    def _apply_failure_effects(
        self,
        action_type: str,
        target_id: str,
        context_packet: dict,
        risk_settings: dict,
        clock_config: Optional[ClockConfig] = None,
        severity_tier: int = 0
    ) -> dict:
        """Apply effects for failed action, scaled by severity tier.

        Tier 0 (SAFE): Current behavior — clock effects only from failure_effects config
        Tier 1 (RISKY): Clock effects + situation fact (soft)
        Tier 2 (DANGEROUS): Clock effects + harm for physical actions + situation fact (hard) + extra heat for stealth
        """
        if clock_config is None:
            clock_config = load_clock_config(context_packet.get("system", {}))

        diff = {
            "clocks": [],
            "facts_add": [],
            "facts_update": [],
            "inventory_changes": [],
            "scene_update": {},
            "threads_update": [],
            "relationship_changes": []
        }

        # Failed social actions sour relationships
        if action_type.lower() in ["persuade", "intimidate", "deceive", "negotiate", "provoke"]:
            if target_id and target_id.lower() not in ("scene", "self", "player"):
                diff["relationship_changes"].append({
                    "a_id": "player",
                    "b_id": target_id,
                    "rel_type": "trust",
                    "delta": -1
                })

        if not clock_config.enabled:
            return diff

        # Standard failure clock effects (all tiers)
        failure_mode = risk_settings.get("failure_mode", "consequential")

        for effect in clock_config.get_failure_clock_effects(action_type, failure_mode):
            clock_id = effect["id"]
            delta = effect["delta"]
            delta = clock_config.apply_direction(clock_id, delta)
            diff["clocks"].append({"id": clock_id, "delta": delta, "source": "failure"})

        # Tier 2: Physical failures during danger cause harm
        if severity_tier >= 2:
            tier2_actions = clock_config.failure_severity.get(
                "tier2_harm_actions",
                ["sneak", "hide", "flee", "climb", "fight", "attack", "chase"]
            )
            if action_type.lower() in tier2_actions:
                # Add harm if not already applied by standard failure effects
                existing_harm = any(c["id"] == "harm" for c in diff["clocks"])
                if not existing_harm:
                    diff["clocks"].append({
                        "id": "harm", "delta": 1, "source": "failure"
                    })

            # Extra heat for stealth failures during danger
            stealth_actions = {"sneak", "hide", "steal"}
            if action_type.lower() in stealth_actions:
                diff["clocks"].append({
                    "id": "heat", "delta": 1, "source": "failure"
                })

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
        context_packet: dict,
        clock_config: Optional[ClockConfig] = None
    ) -> Tuple[list[dict], dict]:
        """Apply the planner's tension move."""
        if clock_config is None:
            clock_config = load_clock_config(context_packet.get("system", {}))

        events = []
        diff = {
            "clocks": [],
            "facts_add": [],
            "facts_update": [],
            "inventory_changes": [],
            "scene_update": {},
            "threads_update": [],
            "relationship_changes": []
        }

        # Match tension move text to a clock via configured keywords
        matched_clock = clock_config.get_tension_clock(tension_move) if clock_config.enabled else None

        if matched_clock:
            delta = clock_config.apply_direction(matched_clock, 1)
            diff["clocks"].append({"id": matched_clock, "delta": delta, "source": "tension"})
            events.append({
                "type": "clock_advanced",
                "details": {"clock": matched_clock, "reason": tension_move},
                "tags": ["tension", "gm_move"]
            })
        else:
            # Generic tension event (no clock match or clocks disabled)
            events.append({
                "type": "npc_action",
                "details": {"description": tension_move},
                "tags": ["tension", "gm_move"]
            })

        return events, diff

    def _map_action_to_condition(self, action_type: str) -> Optional[str]:
        """Return the situation condition that results from failing this action type."""
        return self.CONDITION_MAP.get(action_type.lower())

    def _get_clear_conditions(self, condition: str) -> list[str]:
        """Return what success types clear this condition."""
        return self.CLEAR_MAP.get(condition, [])

    def _create_situation_fact(
        self,
        action_type: str,
        target_id: str,
        severity: str,
        context_packet: dict,
        diff: dict
    ) -> list[dict]:
        """Create a situation fact for a failed action. Returns engine events."""
        condition = self._map_action_to_condition(action_type)
        if not condition:
            return []

        events = []
        clears_on = self._get_clear_conditions(condition)

        # Check for existing active situation with same condition
        active_situations = context_packet.get("active_situations", [])
        existing = None
        for sit in active_situations:
            if sit.get("condition") == condition:
                existing = sit
                break

        if existing:
            # If upgrading soft -> hard, update existing
            if existing.get("severity") == "soft" and severity == "hard":
                diff["facts_update"].append({
                    "id": existing["fact_id"],
                    "object": {
                        "condition": condition,
                        "active": True,
                        "source_action": action_type,
                        "severity": "hard",
                        "clears_on": clears_on,
                        "narrative_hint": f"Situation worsened — player's {action_type} failure escalated exposure"
                    }
                })
                events.append({
                    "type": "situation_created",
                    "details": {
                        "condition": condition,
                        "severity": "hard",
                        "upgraded_from": "soft",
                        "source_action": action_type,
                        "narrative_hint": f"Situation worsened — player's {action_type} failure escalated exposure"
                    },
                    "tags": ["situation", "escalation"]
                })
            # Same or higher severity already exists — don't duplicate
            return events

        # Create new situation fact
        fact_id = f"situation_{uuid.uuid4().hex[:12]}"
        narrative_hint = self._describe_failure_state(action_type, target_id, context_packet)

        diff["facts_add"].append({
            "subject_id": "player",
            "predicate": "situation",
            "object": {
                "condition": condition,
                "active": True,
                "source_action": action_type,
                "severity": severity,
                "clears_on": clears_on,
                "narrative_hint": narrative_hint
            },
            "visibility": "known",
            "tags": ["situation", "active"],
            "id": fact_id
        })

        events.append({
            "type": "situation_created",
            "details": {
                "condition": condition,
                "severity": severity,
                "source_action": action_type,
                "narrative_hint": narrative_hint
            },
            "tags": ["situation"]
        })

        return events

    def _clear_resolved_situations(
        self,
        action_type: str,
        outcome: str,
        context_packet: dict,
        diff: dict
    ) -> list[dict]:
        """On success, clear active situation facts whose clears_on matches."""
        events = []
        success_key = f"{action_type.lower()}_success"

        active_situations = context_packet.get("active_situations", [])
        for sit in active_situations:
            clears_on = sit.get("clears_on", [])
            if success_key in clears_on:
                diff["facts_update"].append({
                    "id": sit["fact_id"],
                    "object": {
                        "condition": sit["condition"],
                        "active": False,
                        "source_action": sit.get("source_action", ""),
                        "severity": sit.get("severity", "soft"),
                        "clears_on": clears_on,
                        "narrative_hint": sit.get("narrative_hint", "")
                    }
                })
                events.append({
                    "type": "situation_cleared",
                    "details": {
                        "condition": sit["condition"],
                        "cleared_by": f"{action_type}_{outcome}",
                        "fact_id": sit["fact_id"]
                    },
                    "tags": ["situation", "resolved"]
                })

        return events

    def _compute_severity_tier(
        self,
        risk_flags: list,
        context_packet: dict,
        clock_config: Optional[ClockConfig] = None
    ) -> int:
        """Compute severity tier based on risk flags, active situations, and threats.

        Tier 0 (SAFE): No risk flags, no active threats
        Tier 1 (RISKY): Risk flags present, no active threat in scene
        Tier 2 (DANGEROUS): Active threat in scene (hostile NPC or pending_threat)
        """
        risky_flags = {"violence", "contested", "dangerous", "pursuit", "hostile_present"}
        has_risk_flags = bool(set(risk_flags or []) & risky_flags)

        # Check for active threats
        has_threat = self._has_active_threat(context_packet)

        if has_threat:
            return 2
        elif has_risk_flags:
            return 1
        else:
            return 0

    def _has_active_threat(self, context_packet: dict) -> bool:
        """Check if there's an active threat in the current context."""
        # Check pending threats
        pending_threats = context_packet.get("pending_threats", [])
        if pending_threats:
            return True

        # Check NPC capabilities for high+ threat NPCs
        npc_caps = context_packet.get("npc_capabilities", [])
        high_threat_levels = {"high", "extreme"}
        if any(npc.get("threat_level") in high_threat_levels for npc in npc_caps):
            return True

        # Check active situations with hard severity
        active_situations = context_packet.get("active_situations", [])
        if any(sit.get("severity") == "hard" for sit in active_situations):
            return True

        return False

    def _check_failure_streak(
        self,
        outcomes: list[str],
        context_packet: dict,
        clock_config: Optional[ClockConfig] = None
    ) -> Tuple[list[dict], dict]:
        """Check failure streak after resolving all actions. Returns (events, diff)."""
        events = []
        diff = {
            "clocks": [],
            "facts_add": [],
            "facts_update": [],
            "inventory_changes": [],
            "scene_update": {},
            "threads_update": [],
            "relationship_changes": []
        }

        all_failed = all(o == "failure" for o in outcomes) and len(outcomes) > 0
        any_succeeded = any(o == "success" for o in outcomes)

        if not all_failed:
            return events, diff

        # Current turn adds to streak
        streak = context_packet.get("failure_streak", {"count": 0})
        new_count = streak.get("count", 0) + 1
        has_active_threat = self._has_active_threat(context_packet)

        threshold = 3  # default
        if clock_config and clock_config.failure_severity:
            threshold = clock_config.failure_severity.get("streak_threshold", 3)

        if new_count >= threshold and has_active_threat:
            # Threat resolves against player
            resolve_events, resolve_diff = self._resolve_threat_against_player(
                context_packet, clock_config
            )
            events.extend(resolve_events)
            self._merge_diff(diff, resolve_diff)
        elif new_count == threshold - 1 and has_active_threat:
            # Warning: next failure will be catastrophic
            events.append({
                "type": "failure_streak_warning",
                "details": {
                    "streak_count": new_count,
                    "next_failure_critical": True
                },
                "tags": ["warning", "escalation"]
            })

        return events, diff

    def _resolve_threat_against_player(
        self,
        context_packet: dict,
        clock_config: Optional[ClockConfig] = None
    ) -> Tuple[list[dict], dict]:
        """Resolve an active threat against the player at streak threshold."""
        events = []
        diff = {
            "clocks": [],
            "facts_add": [],
            "facts_update": [],
            "inventory_changes": [],
            "scene_update": {},
            "threads_update": [],
            "relationship_changes": []
        }

        # Find primary threat NPC (highest threat_level)
        npc_caps = context_packet.get("npc_capabilities", [])
        threat_order = {"extreme": 4, "high": 3, "moderate": 2, "low": 1}
        primary_threat = None
        for npc in sorted(
            npc_caps,
            key=lambda n: threat_order.get(n.get("threat_level", "low"), 0),
            reverse=True
        ):
            primary_threat = npc
            break

        npc_id = primary_threat["entity_id"] if primary_threat else "unknown_threat"
        npc_name = primary_threat["name"] if primary_threat else "the threat"
        escalation = primary_threat.get("escalation_profile", {}) if primary_threat else {}
        consequence_desc = escalation.get("hard", f"{npc_name} has caught up with the player")

        # Determine harm from config
        base_harm = 2
        if clock_config and clock_config.failure_severity:
            base_harm = clock_config.failure_severity.get("tier3_base_harm", 2)

        events.append({
            "type": "threat_resolved_against_player",
            "details": {
                "threat_entity_id": npc_id,
                "threat_entity_name": npc_name,
                "consequence_type": "capture",
                "consequence_description": consequence_desc,
                "harm_delta": base_harm,
                "binding": True
            },
            "tags": ["threat_resolution", "binding", "critical"]
        })

        # Apply harm
        diff["clocks"].append({
            "id": "harm", "delta": base_harm, "source": "threat_resolution"
        })

        # Create cornered situation fact
        fact_id = f"situation_{uuid.uuid4().hex[:12]}"
        diff["facts_add"].append({
            "subject_id": "player",
            "predicate": "situation",
            "object": {
                "condition": "cornered",
                "active": True,
                "source_action": "threat_resolution",
                "severity": "hard",
                "clears_on": ["fight_success", "talk_success", "scene_change"],
                "narrative_hint": f"{npc_name} has the player cornered — direct confrontation or surrender"
            },
            "visibility": "known",
            "tags": ["situation", "active"],
            "id": fact_id
        })

        return events, diff

    def _merge_diff(self, target: dict, source: dict) -> None:
        """Merge source diff into target diff."""
        for key in ["clocks", "facts_add", "facts_update", "inventory_changes", "threads_update", "relationship_changes"]:
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
