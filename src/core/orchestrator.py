"""
Turn Orchestrator - Coordinates the multi-pass LLM pipeline.

Pipeline stages:
  Player Input → Interpreter → Validator → Planner → Resolver → Narrator → Commit
"""

from dataclasses import dataclass, field
from typing import Optional, Protocol

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

    def to_dict(self) -> dict:
        return {
            "turn_no": self.turn_no,
            "event_id": self.event_id,
            "final_text": self.final_text,
            "clarification_needed": self.clarification_needed,
            "clarification_question": self.clarification_question,
            "suggested_actions": self.suggested_actions,
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
        prompt_versions: Optional[dict] = None
    ):
        self.store = state_store
        self.gateway = llm_gateway
        self.prompts = prompt_registry

        self.versions = DEFAULT_PROMPT_VERSIONS.copy()
        if prompt_versions:
            self.versions.update(prompt_versions)

        # Initialize pipeline components
        self.context_builder = ContextBuilder(state_store)
        self.validator = Validator(state_store)
        self.resolver = Resolver(state_store)

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

        # Stage 1: Build context
        context_options = ContextOptions(
            include_world_facts=options.get("include_world_facts", False)
        )
        context_packet = self.context_builder.build_context(
            campaign_id, player_input, context_options
        )

        # Add player input to context for LLM stages
        context_packet["player_input"] = player_input

        # Stage 2: Interpreter (LLM)
        interpreter_output = self._run_interpreter(context_packet)

        # Stage 3: Validator (deterministic)
        validator_output = self.validator.validate(
            interpreter_output,
            context_packet
        )

        # Check if clarification needed
        if validator_output.clarification_needed:
            return self._create_clarification_result(
                campaign_id,
                player_input,
                context_packet,
                interpreter_output,
                validator_output.to_dict()
            )

        # Stage 4: Planner (LLM)
        planner_output = self._run_planner(
            context_packet,
            interpreter_output,
            validator_output.to_dict()
        )

        # Stage 5: Resolver (deterministic)
        resolver_output = self.resolver.resolve(
            context_packet,
            validator_output.to_dict(),
            planner_output,
            options
        )

        # Stage 6: Narrator (LLM)
        narrator_output = self._run_narrator(
            context_packet,
            validator_output.to_dict(),
            planner_output,
            resolver_output.to_dict()
        )

        # Stage 7: Commit - Apply state changes and log event
        turn_result = self._commit_turn(
            campaign_id,
            player_input,
            context_packet,
            interpreter_output,
            validator_output.to_dict(),
            planner_output,
            resolver_output.to_dict(),
            narrator_output
        )

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
                    "context": context_packet,
                    "player_input": context_packet["player_input"]
                },
                schema=schema
            )
            return response.content
        except Exception as e:
            # Fallback to stub output on error
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
                    "context": context_packet,
                    "interpreter": interpreter_output,
                    "validator": validator_output
                },
                schema=schema
            )
            return response.content
        except Exception as e:
            # Fallback to stub output on error
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
                    "context": context_packet,
                    "validator": validator_output,
                    "planner": planner_output,
                    "resolver": resolver_output
                },
                schema=schema
            )
            return response.content
        except Exception as e:
            # Fallback to stub output on error
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
        narrator_output: dict
    ) -> TurnResult:
        """Apply state changes and log the complete turn."""
        # Get turn number first
        turn_no = self.store.get_next_turn_no(campaign_id)

        # Apply state diff
        state_diff = resolver_output.get("state_diff", {})
        triggers = self.store.apply_state_diff(state_diff, turn_no)

        # Handle any triggered effects
        for trigger in triggers:
            # Could emit additional events here
            pass
        event_id = new_event_id()

        pass_outputs = {
            "interpreter": interpreter_output,
            "validator": validator_output,
            "planner": planner_output,
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
            suggested_actions=narrator_output.get("suggested_actions", [])
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
