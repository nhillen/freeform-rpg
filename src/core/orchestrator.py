"""
Turn Orchestrator - Coordinates the multi-pass LLM pipeline.

Pipeline stages:
  Player Input → Interpreter → Validator → Planner → Resolver → Narrator → Commit
"""

import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol

from ..context.builder import ContextBuilder, ContextOptions
from ..db.state_store import StateStore, json_dumps, new_event_id
from ..llm.gateway import LLMGateway, MockGateway, load_schema
from ..llm.prompt_registry import PromptRegistry
from .validator import Validator
from .resolver import Resolver


DEFAULT_PROMPT_VERSIONS = {
    "interpreter": "v0",
    "planner": "v0",
    "narrator": "v0",
}


@dataclass
class TurnResult:
    """Result of a turn execution."""
    turn_no: int
    event_id: str
    final_text: str
    clarification_needed: bool = False
    clarification_question: str = ""
    suggested_actions: list = field(default_factory=list)
    clock_deltas: list = field(default_factory=list)
    debug_info: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "turn_no": self.turn_no,
            "event_id": self.event_id,
            "final_text": self.final_text,
            "clarification_needed": self.clarification_needed,
            "clarification_question": self.clarification_question,
            "suggested_actions": self.suggested_actions,
            "clock_deltas": self.clock_deltas,
        }


class Orchestrator:
    """
    Coordinates the turn pipeline.

    The orchestrator wires together all pipeline components and manages
    the flow of data through each stage.
    """

    def __init__(
        self,
        state_store: StateStore,
        llm_gateway: LLMGateway,
        prompt_registry: PromptRegistry,
        prompt_versions: Optional[dict] = None,
        on_stage: Optional[Callable[[str], None]] = None
    ):
        self.store = state_store
        self.gateway = llm_gateway
        self.prompts = prompt_registry
        self.on_stage = on_stage

        self.versions = DEFAULT_PROMPT_VERSIONS.copy()
        if prompt_versions:
            self.versions.update(prompt_versions)

        # Initialize pipeline components
        self.context_builder = ContextBuilder(state_store)
        self.validator = Validator(state_store)
        self.resolver = Resolver(state_store)

    def _notify(self, stage: str):
        """Notify observer of current pipeline stage."""
        if self.on_stage:
            self.on_stage(stage)

    @staticmethod
    def _compute_period(hour: int) -> str:
        """Map hour-of-day to a named period."""
        if 5 <= hour < 6:
            return "pre_dawn"
        elif 6 <= hour < 8:
            return "dawn"
        elif 8 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 20:
            return "evening"
        else:
            return "night"

    def _advance_scene_time(self, minutes: int) -> dict:
        """Advance scene time by estimated minutes. Returns change info."""
        if minutes <= 0:
            return {}
        scene = self.store.get_scene()
        if not scene:
            return {}
        current_time = scene.get("time", {})
        old_hour = current_time.get("hour", 0)
        old_minute = current_time.get("minute", 0)
        old_period = current_time.get("period", self._compute_period(old_hour))

        total_minutes = old_hour * 60 + old_minute + minutes
        new_hour = (total_minutes // 60) % 24
        new_minute = total_minutes % 60
        new_period = self._compute_period(new_hour)

        updated_time = dict(current_time)  # preserves weather etc.
        updated_time["hour"] = new_hour
        updated_time["minute"] = new_minute
        updated_time["period"] = new_period
        self.store.update_scene_time(updated_time)

        return {
            "old_period": old_period,
            "new_period": new_period,
            "new_hour": new_hour,
            "new_minute": new_minute,
            "period_changed": old_period != new_period,
        }

    def run_turn(
        self,
        campaign_id: str,
        player_input: str,
        options: Optional[dict] = None
    ) -> TurnResult:
        """
        Execute one complete turn through the pipeline.

        Args:
            campaign_id: Campaign to run turn for
            player_input: The player's action text
            options: Optional configuration (force_roll, etc.)

        Returns:
            TurnResult with final text and metadata
        """
        options = options or {}
        timings = {}
        t0 = time.monotonic()

        # Stage 1: Build context
        self._notify("Building context")
        context_options = ContextOptions(
            include_world_facts=options.get("include_world_facts", False)
        )
        context_packet = self.context_builder.build_context(
            campaign_id, player_input, context_options
        )

        # Add player input to context for LLM stages
        context_packet["player_input"] = player_input

        # Stage 2: Interpreter (LLM)
        self._notify("Interpreting")
        t_stage = time.monotonic()
        interpreter_output = self._run_interpreter(context_packet)
        timings["interpreter_ms"] = int((time.monotonic() - t_stage) * 1000)

        # Stage 3: Validator (deterministic)
        self._notify("Validating")
        validator_output = self.validator.validate(
            interpreter_output,
            context_packet
        )

        # Check if clarification needed
        if validator_output.clarification_needed:
            result = self._create_clarification_result(
                campaign_id,
                player_input,
                context_packet,
                interpreter_output,
                validator_output.to_dict()
            )
            result.debug_info = {
                "interpreter": interpreter_output,
                "validator": validator_output.to_dict(),
                "timings": timings,
                "total_ms": int((time.monotonic() - t0) * 1000),
            }
            return result

        # Stage 4: Planner (LLM)
        self._notify("Planning")
        t_stage = time.monotonic()
        planner_output = self._run_planner(
            context_packet,
            interpreter_output,
            validator_output.to_dict()
        )
        timings["planner_ms"] = int((time.monotonic() - t_stage) * 1000)

        # Stage 5: Resolver (deterministic)
        self._notify("Resolving")
        resolver_output = self.resolver.resolve(
            context_packet,
            validator_output.to_dict(),
            planner_output,
            options
        )

        # Stage 5.5: Apply state diff early to capture clock triggers for narrator
        turn_no = self.store.get_next_turn_no(campaign_id)
        state_diff = resolver_output.to_dict().get("state_diff", {})

        # Snapshot clock values before applying state diff
        clocks_before = {c["id"]: c for c in self.store.get_all_clocks()}

        triggers = self.store.apply_state_diff(state_diff, turn_no)

        # Snapshot clock values after applying state diff, compute deltas
        clocks_after = {c["id"]: c for c in self.store.get_all_clocks()}
        clock_deltas = []
        for clock_id, after in clocks_after.items():
            before = clocks_before.get(clock_id)
            if before and before["value"] != after["value"]:
                # Check sources of this clock's changes to determine if consequence-driven
                sources = {
                    e.get("source", "unknown")
                    for e in state_diff.get("clocks", [])
                    if e["id"] == clock_id
                }
                clock_deltas.append({
                    "id": clock_id,
                    "name": after.get("name", clock_id),
                    "old": before["value"],
                    "new": after["value"],
                    "consequence": bool(sources - {"cost"}),
                })

        # Inject clock triggers as engine events so narrator can reference them
        for trigger_msg in triggers:
            resolver_output.engine_events.append({
                "type": "clock_triggered",
                "details": {"message": trigger_msg},
                "tags": ["clock", "trigger"]
            })

        # Stage 5.6: Advance fictional scene time
        time_change = self._advance_scene_time(resolver_output.total_estimated_minutes)
        if time_change.get("period_changed"):
            resolver_output.engine_events.append({
                "type": "time_period_changed",
                "details": {
                    "old_period": time_change["old_period"],
                    "new_period": time_change["new_period"],
                    "new_hour": time_change["new_hour"],
                    "new_minute": time_change["new_minute"],
                },
                "tags": ["time", "atmosphere"]
            })

        # Stage 6: Narrator (LLM)
        self._notify("Narrating")
        t_stage = time.monotonic()
        narrator_output = self._run_narrator(
            context_packet,
            validator_output.to_dict(),
            planner_output,
            resolver_output.to_dict()
        )
        timings["narrator_ms"] = int((time.monotonic() - t_stage) * 1000)

        # Stage 7: Commit - Log event and apply narrator-declared state
        self._notify("Committing")
        turn_result = self._commit_turn(
            campaign_id,
            player_input,
            context_packet,
            interpreter_output,
            validator_output.to_dict(),
            planner_output,
            resolver_output.to_dict(),
            narrator_output,
            turn_no=turn_no,
            state_diff_applied=True,
            clock_deltas=clock_deltas
        )

        turn_result.debug_info = {
            "interpreter": interpreter_output,
            "validator": validator_output.to_dict(),
            "planner": planner_output,
            "resolver": resolver_output.to_dict(),
            "narrator": narrator_output,
            "timings": timings,
            "total_ms": int((time.monotonic() - t0) * 1000),
        }

        return turn_result

    def _run_interpreter(self, context_packet: dict) -> dict:
        """Run the interpreter LLM stage."""
        prompt_id = "interpreter"
        version = self.versions['interpreter']
        schema = load_schema("interpreter_output")

        try:
            prompt_template = self.prompts.get_prompt(prompt_id, version)
            response = self.gateway.run_structured(
                prompt=prompt_template.template,
                input_data={
                    "context_packet": context_packet,
                    "player_input": context_packet["player_input"]
                },
                schema=schema
            )
            return response.content
        except Exception as e:
            print(f"[engine] Interpreter LLM failed ({type(e).__name__}: {e}), using stub", file=sys.stderr)
            return self._stub_interpreter_output(context_packet)

    def _run_planner(
        self,
        context_packet: dict,
        interpreter_output: dict,
        validator_output: dict
    ) -> dict:
        """Run the planner LLM stage."""
        prompt_id = "planner"
        version = self.versions['planner']
        schema = load_schema("planner_output")

        try:
            prompt_template = self.prompts.get_prompt(prompt_id, version)
            response = self.gateway.run_structured(
                prompt=prompt_template.template,
                input_data={
                    "context_packet": context_packet,
                    "validator_output": validator_output
                },
                schema=schema
            )
            return response.content
        except Exception as e:
            print(f"[engine] Planner LLM failed ({type(e).__name__}: {e}), using stub", file=sys.stderr)
            return self._stub_planner_output()

    def _run_narrator(
        self,
        context_packet: dict,
        validator_output: dict,
        planner_output: dict,
        resolver_output: dict
    ) -> dict:
        """Run the narrator LLM stage."""
        prompt_id = "narrator"
        version = self.versions['narrator']
        schema = load_schema("narrator_output")

        try:
            prompt_template = self.prompts.get_prompt(prompt_id, version)
            response = self.gateway.run_structured(
                prompt=prompt_template.template,
                input_data={
                    "context_packet": context_packet,
                    "engine_events": resolver_output.get("engine_events", []),
                    "planner_output": planner_output,
                    "blocked_actions": validator_output.get("blocked_actions", [])
                },
                schema=schema
            )
            return response.content
        except Exception as e:
            print(f"[engine] Narrator LLM failed ({type(e).__name__}: {e}), using stub", file=sys.stderr)
            return self._stub_narrator_output(resolver_output)

    def _stub_interpreter_output(self, context_packet: dict) -> dict:
        """Generate stub interpreter output for testing."""
        player_input = context_packet.get("player_input", "")
        present = context_packet.get("present_entities", [])

        # Simple action extraction
        action = "examine"
        target = present[0] if present else "scene"

        if any(word in player_input.lower() for word in ["attack", "hit", "fight"]):
            action = "attack"
        elif any(word in player_input.lower() for word in ["talk", "ask", "speak"]):
            action = "talk"
        elif any(word in player_input.lower() for word in ["look", "examine", "search"]):
            action = "examine"

        return {
            "intent": f"Player wants to {action}",
            "referenced_entities": [target],
            "proposed_actions": [
                {"action": action, "target_id": target, "details": player_input}
            ],
            "assumptions": [],
            "risk_flags": ["violence"] if action == "attack" else [],
            "perception_flags": []
        }

    def _stub_planner_output(self) -> dict:
        """Generate stub planner output for testing."""
        return {
            "beats": ["Acknowledge the action", "Describe the result"],
            "tension_move": "",
            "clarification_question": "",
            "next_suggestions": []
        }

    def _stub_narrator_output(self, resolver_output: dict) -> dict:
        """Generate stub narrator output for testing."""
        events = resolver_output.get("engine_events", [])

        # Build narrative from events
        text_parts = []
        for event in events:
            event_type = event.get("type", "")
            details = event.get("details", {})

            if event_type == "action_succeeded":
                action = details.get("action", "act")
                text_parts.append(f"You successfully {action}.")
            elif event_type == "action_failed":
                action = details.get("action", "act")
                consequence = details.get("consequence", "Things don't go as planned.")
                text_parts.append(f"Your attempt to {action} fails. {consequence}")
            elif event_type == "action_partial":
                action = details.get("action", "act")
                complication = details.get("complication", "There's a catch.")
                text_parts.append(f"You {action}, but {complication}")

        final_text = " ".join(text_parts) if text_parts else "The scene unfolds before you."

        return {
            "final_text": final_text,
            "next_prompt": "what_do_you_do",
            "suggested_actions": []
        }

    def _create_clarification_result(
        self,
        campaign_id: str,
        player_input: str,
        context_packet: dict,
        interpreter_output: dict,
        validator_output: dict
    ) -> TurnResult:
        """Create a result that requests clarification."""
        turn_no = self.store.get_next_turn_no(campaign_id)
        event_id = new_event_id()

        # Log the partial turn
        pass_outputs = {
            "interpreter": interpreter_output,
            "validator": validator_output,
            "planner": {},
            "narrator": {}
        }

        event_record = {
            "id": event_id,
            "campaign_id": campaign_id,
            "turn_no": turn_no,
            "player_input": player_input,
            "context_packet_json": json_dumps(context_packet),
            "pass_outputs_json": json_dumps(pass_outputs),
            "engine_events_json": json_dumps([]),
            "state_diff_json": json_dumps({}),
            "final_text": validator_output["clarification_question"],
            "prompt_versions_json": json_dumps(self.versions),
        }
        self.store.append_event(event_record)

        return TurnResult(
            turn_no=turn_no,
            event_id=event_id,
            final_text=validator_output["clarification_question"],
            clarification_needed=True,
            clarification_question=validator_output["clarification_question"],
            suggested_actions=[]
        )

    def _commit_turn(
        self,
        campaign_id: str,
        player_input: str,
        context_packet: dict,
        interpreter_output: dict,
        validator_output: dict,
        planner_output: dict,
        resolver_output: dict,
        narrator_output: dict,
        turn_no: Optional[int] = None,
        state_diff_applied: bool = False,
        clock_deltas: Optional[list] = None
    ) -> TurnResult:
        """Apply state changes and log the complete turn."""
        if turn_no is None:
            turn_no = self.store.get_next_turn_no(campaign_id)

        # Apply state diff (unless already applied before narrator)
        state_diff = resolver_output.get("state_diff", {})
        if not state_diff_applied:
            self.store.apply_state_diff(state_diff, turn_no)

        # Commit narrator-established facts to state
        established_facts = narrator_output.get("established_facts", [])
        for ef in established_facts:
            subject = ef.get("subject", "scene")
            detail = ef.get("detail", "")
            if detail:
                fact_id = f"narrator_t{turn_no}_{new_event_id()[:8]}"
                self.store.create_fact(
                    fact_id=fact_id,
                    subject_id=subject,
                    predicate="narrator_established",
                    obj=detail,
                    visibility="known",
                    tags=["narrator", f"turn_{turn_no}"]
                )

        # Commit narrator-introduced items as real game entities
        introduced_items = narrator_output.get("introduced_items", [])
        for item in introduced_items:
            item_name = item.get("name", "")
            if not item_name:
                continue
            item_id = item_name.lower().replace(" ", "_").replace("'", "")
            role = item.get("narrative_role", "flavor")
            tags = ["introduced", role, f"turn_{turn_no}"]

            # Only create if entity doesn't already exist
            existing = self.store.get_entity(item_id)
            if not existing:
                self.store.create_entity(
                    entity_id=item_id,
                    entity_type="item",
                    name=item_name,
                    attrs={
                        "description": item.get("description", ""),
                        "narrative_role": role,
                        "found_on": item.get("found_on", ""),
                    },
                    tags=tags
                )
            # Add to player inventory (add_inventory handles stacking)
            self.store.add_inventory(owner_id="player", item_id=item_id, qty=1)

            # Clue items get a fact linking them to narrative significance
            if role == "clue" and item.get("description"):
                self.store.create_fact(
                    fact_id=f"clue_{item_id}_{new_event_id()[:8]}",
                    subject_id=item_id,
                    predicate="clue_significance",
                    obj=item.get("description", ""),
                    visibility="known",
                    tags=["clue", f"turn_{turn_no}"]
                )

        # Commit narrator-declared scene transitions
        scene_transition = narrator_output.get("scene_transition")
        if scene_transition:
            location_id = scene_transition["location_id"]
            location_name = scene_transition.get("location_name", location_id)
            description = scene_transition.get("description", "")
            present_entities = scene_transition.get("present_entities", ["player"])

            # Ensure player is always present
            if "player" not in present_entities:
                present_entities.insert(0, "player")

            # Create the location entity if it doesn't exist
            existing_location = self.store.get_entity(location_id)
            if not existing_location:
                self.store.create_entity(
                    entity_id=location_id,
                    entity_type="location",
                    name=location_name,
                    attrs={
                        "description": description,
                        "name": location_name,
                    },
                    tags=["location", f"turn_{turn_no}"]
                )

            # Update the scene, preserving current time/constraints
            current_scene = self.store.get_scene()
            self.store.set_scene(
                location_id=location_id,
                present_entity_ids=present_entities,
                time=current_scene.get("time") if current_scene else None,
                constraints=current_scene.get("constraints") if current_scene else None,
            )

        # Record planner tension moves as pending threats for escalation tracking
        tension_move = planner_output.get("tension_move", "")
        if tension_move:
            self.store.create_fact(
                fact_id=f"threat_t{turn_no}_{new_event_id()[:8]}",
                subject_id="scene",
                predicate="pending_threat",
                obj={
                    "description": tension_move,
                    "threat_type": "soft",
                    "turn_issued": turn_no
                },
                visibility="known",
                tags=["pending_threat", f"turn_{turn_no}"]
            )

        # Commit narrator-introduced NPCs as tracked game entities
        introduced_npcs = narrator_output.get("introduced_npcs", [])
        for npc in introduced_npcs:
            npc_id = npc.get("entity_id", "")
            npc_name = npc.get("name", "")
            if not npc_id or not npc_name:
                continue

            existing = self.store.get_entity(npc_id)
            if not existing:
                npc_attrs = {
                    "description": npc.get("description", ""),
                    "role": npc.get("role", ""),
                }
                # Store capability fields if provided by narrator
                if npc.get("threat_level"):
                    npc_attrs["threat_level"] = npc["threat_level"]
                if npc.get("capabilities"):
                    npc_attrs["capabilities"] = npc["capabilities"]
                if npc.get("equipment"):
                    npc_attrs["equipment"] = npc["equipment"]
                if npc.get("limitations"):
                    npc_attrs["limitations"] = npc.get("limitations", [])
                if npc.get("escalation_profile"):
                    npc_attrs["escalation_profile"] = npc["escalation_profile"]
                self.store.create_entity(
                    entity_id=npc_id,
                    entity_type="npc",
                    name=npc_name,
                    attrs=npc_attrs,
                    tags=["introduced", f"turn_{turn_no}"]
                )

            # Add NPC to current scene
            current_scene = self.store.get_scene()
            if current_scene:
                present = list(current_scene["present_entity_ids"])
                if npc_id not in present:
                    present.append(npc_id)
                    self.store.update_scene_entities(present)

            # Create initial neutral relationship with player
            existing_rel = self.store.get_relationship("player", npc_id, "contact")
            if not existing_rel:
                self.store.create_relationship(
                    "player", npc_id, "contact", intensity=0
                )

        # Commit narrator-declared thread updates
        thread_updates = narrator_output.get("thread_updates", [])
        for tu in thread_updates:
            thread_id = tu.get("thread_id")
            new_status = tu.get("status")
            if thread_id and new_status:
                existing_thread = self.store.get_thread(thread_id)
                if existing_thread:
                    self.store.update_thread(thread_id, status=new_status)

        event_id = new_event_id()

        pass_outputs = {
            "interpreter": interpreter_output,
            "validator": validator_output,
            "planner": planner_output,
            "resolver": resolver_output,
            "narrator": narrator_output
        }

        event_record = {
            "id": event_id,
            "campaign_id": campaign_id,
            "turn_no": turn_no,
            "player_input": player_input,
            "context_packet_json": json_dumps(context_packet),
            "pass_outputs_json": json_dumps(pass_outputs),
            "engine_events_json": json_dumps(resolver_output.get("engine_events", [])),
            "state_diff_json": json_dumps(state_diff),
            "final_text": narrator_output["final_text"],
            "prompt_versions_json": json_dumps(self.versions),
        }
        self.store.append_event(event_record)

        return TurnResult(
            turn_no=turn_no,
            event_id=event_id,
            final_text=narrator_output["final_text"],
            clarification_needed=False,
            clarification_question="",
            suggested_actions=narrator_output.get("suggested_actions", []),
            clock_deltas=clock_deltas or []
        )


def run_turn(
    state_store: StateStore,
    campaign_id: str,
    player_input: str,
    prompt_versions: Optional[dict] = None,
    llm_gateway: Optional[LLMGateway] = None,
    prompt_registry: Optional[PromptRegistry] = None
) -> dict:
    """
    Convenience function to run a single turn.

    This function provides backwards compatibility and a simpler interface
    for running turns without creating an Orchestrator instance.
    """
    from pathlib import Path

    # Use mock gateway if not provided
    if llm_gateway is None:
        llm_gateway = MockGateway()

    # Use default prompts directory if not provided
    if prompt_registry is None:
        prompts_dir = Path(__file__).parent.parent / "prompts"
        prompt_registry = PromptRegistry(prompts_dir)

    orchestrator = Orchestrator(
        state_store=state_store,
        llm_gateway=llm_gateway,
        prompt_registry=prompt_registry,
        prompt_versions=prompt_versions
    )

    result = orchestrator.run_turn(campaign_id, player_input)
    return result.to_dict()
