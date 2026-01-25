# High-Level Design (HLD): Freeform RPG Engine v0

## System context
Player <-> UI <-> Turn Orchestrator <-> (State Store, Context Builder, LLM Gateway, Validator/Resolver) <-> Prompt Registry

## Key objectives
- Fast replay and iteration for prompts and rules.
- Modular components that allow inspiration-driven changes without losing state.
- Genre-flexible engine with setting defined by authored content and prompts.

## Components
- Turn Orchestrator: executes pipeline, enforces 1-question policy, logs artifacts.
- State Store (SQLite): canonical entities, facts, scene, etc; append-only events.
- Context Packet Builder: deterministic selection and cap of relevant state.
- LLM Gateway: structured outputs, schema validation, retries, prompt version tagging.
- Validator: code-first constraints and contradiction checks.
- Planner (LLM): optional beat outline and tension move.
- Resolver: deterministic application of rules and clock deltas.
- Narrator (LLM): final prose, no new facts.
- Prompt Registry: versioned prompt templates, pin per campaign.
- Replay Harness: rerun transcripts, compare outputs, compute metrics.
- Dev UI: CLI-first tools to show context packet, state diff, flags, prompt versions.

## Turn pipeline (v0)
1. Load state, build context packet.
2. Interpreter LLM: intent, entities, actions, assumptions, risk flags.
3. Validator: allowed/blocked actions, clarification need, costs.
4. Planner LLM: beats, tension move, optional clarifying question.
5. Resolver: apply deltas, rolls, emit engine_events, state diff.
6. Narrator LLM: prose outcome + next prompt.
7. Commit: write events, apply state diff, update summaries.

## Data model summary
- entities(id, type, name, attrs_json, tags)
- facts(id, subject_id, predicate, object_json, visibility, confidence, tags)
- scene(id, location_id, present_entity_ids_json, time_json, constraints_json)
- threads(id, title, status, stakes_json, related_entity_ids_json, tags)
- clocks(id, name, value, max, triggers_json, tags)
- inventory(owner_id, item_id, qty, flags_json)
- relationships(a_id, b_id, rel_type, intensity, notes_json)
- events(id, turn_no, player_input, context_packet_json, pass_outputs_json, engine_events_json, state_diff_json, final_text, prompt_versions_json)
- summaries(id, scope, scope_id, text, turn_no_range)

## Context packet builder
- Inputs: scene, present entities, active threads, clocks, recent facts, inventory.
- Selection: prioritize present entities, recent events, thread-relevant facts, tagged items.
- Caps: token or byte cap with deterministic ordering and truncation.
- Output: JSON packet with clear sections for the prompts.

## Prompt registry and versioning
- Prompts stored as files with ids and versions.
- Campaign pins interpreter/planner/narrator versions.
- Replay harness can override pins without altering state.

## Flexibility and inspiration
- Stable state schema is the contract; prompts and validator rules are swappable.
- Orchestrator supports optional passes (planner on or off).
- LLM gateway supports multiple providers via adapter interface; initial adapter targets Claude.

## Observability and metrics
- Every pass output stored in events table.
- Metrics: contradictions, invalid action acceptance, clarification rate, response length.
- Flagging tool records issues for later prompt tuning.

## Deployment assumptions
- Local dev mode first; CLI-first for fast iteration with optional thin web UI later.
- SQLite for persistence; logs stored on disk.
