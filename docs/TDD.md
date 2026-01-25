# Technical Design Document (TDD): Freeform RPG Engine v0

## Repository layout (proposed)
- docs/
- src/
  - core/ (orchestrator, validator, resolver)
  - db/ (state store, migrations)
  - llm/ (gateway, prompt registry)
  - context/ (packet builder)
  - eval/ (replay harness, metrics)
  - ui/ (dev UI)
  - prompts/ (versioned prompt files)

## Data types (JSON shapes)
ContextPacket
```
{
  "scene": {"location_id":"", "time":{}, "constraints":{}},
  "present_entities": ["entity_id"],
  "entities": [{"id":"","type":"","name":"","attrs":{},"tags":[]}],
  "facts": [{"id":"","subject_id":"","predicate":"","object":{},"visibility":"","confidence":0,"tags":[]}],
  "threads": [{"id":"","title":"","status":"","stakes":{},"related_entity_ids":[],"tags":[]}],
  "clocks": [{"id":"","name":"","value":0,"max":0,"triggers":{},"tags":[]}],
  "inventory": [{"owner_id":"","item_id":"","qty":0,"flags":{}}],
  "summary": {"scene":"","threads":""},
  "recent_events": [{"turn_no":0,"text":""}]
}
```

InterpreterOutput
```
{
  "intent":"",
  "referenced_entities":["entity_id"],
  "proposed_actions":[{"action":"","target_id":"","details":""}],
  "assumptions":[""],
  "risk_flags":["violence","sensitive"]
}
```

ValidatorOutput
```
{
  "allowed_actions":[{"action":"","target_id":"","details":""}],
  "blocked_actions":[{"action":"","reason":""}],
  "clarification_needed":false,
  "clarification_question":"",
  "costs":{"heat":0,"time":0,"cred":0,"harm":0,"rep":0}
}
```

PlannerOutput
```
{
  "beats":[""],
  "tension_move":"",
  "clarification_question":"",
  "next_suggestions":["","","" ]
}
```

EngineEvent
```
{
  "type":"",
  "details":{},
  "tags":["" ]
}
```

StateDiff
```
{
  "clocks":[{"id":"","delta":0}],
  "facts_add":[{"subject_id":"","predicate":"","object":{},"tags":[]}],
  "facts_update":[{"id":"","object":{}}],
  "inventory_changes":[{"owner_id":"","item_id":"","delta":0}],
  "scene_update":{"location_id":"","present_entity_ids":[]},
  "threads_update":[{"id":"","status":"","stakes":{}}]
}
```

NarratorOutput
```
{
  "final_text":"",
  "next_prompt":"",
  "suggested_actions":["","","" ]
}
```

## Module interfaces (language-agnostic)
StateStore
- getState(campaignId) -> GameState
- applyStateDiff(campaignId, stateDiff) -> void
- appendEvent(eventRecord) -> eventId
- getEvents(campaignId, range) -> Event[]
- getSummary(scope, scopeId) -> Summary

ContextBuilder
- buildContext(state, playerInput, options) -> ContextPacket

PromptRegistry
- getPrompt(promptId, versionId) -> PromptTemplate
- listPromptVersions(promptId) -> Version[]
- pinPromptVersion(campaignId, promptId, versionId) -> void

LLMGateway
- runStructured(prompt, input, schema, options) -> output

Validator
- validate(interpreterOutput, state) -> ValidatorOutput

Planner
- plan(context, validatorOutput) -> PlannerOutput

Resolver
- resolve(state, validatorOutput, plannerOutput, options) -> {engine_events, state_diff, rolls}

Narrator
- narrate(context, engine_events, plannerOutput, options) -> NarratorOutput

Orchestrator
- runTurn(playerInput, campaignId, options) -> TurnResult
- rerunTurn(turnNo, overridePromptVersions) -> TurnResult
- rerunTurns(range, overridePromptVersions) -> TurnResult[]

## LLM provider (v0)
- Initial provider: Claude via gateway adapter.
- Keep the LLM gateway interface provider-agnostic for future additions.

## SQLite schema (v0)
```sql
CREATE TABLE entities (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  name TEXT NOT NULL,
  attrs_json TEXT NOT NULL,
  tags TEXT NOT NULL
);

CREATE TABLE facts (
  id TEXT PRIMARY KEY,
  subject_id TEXT NOT NULL,
  predicate TEXT NOT NULL,
  object_json TEXT NOT NULL,
  visibility TEXT NOT NULL,
  confidence REAL NOT NULL,
  tags TEXT NOT NULL
);

CREATE TABLE scene (
  id TEXT PRIMARY KEY,
  location_id TEXT NOT NULL,
  present_entity_ids_json TEXT NOT NULL,
  time_json TEXT NOT NULL,
  constraints_json TEXT NOT NULL
);

CREATE TABLE threads (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  stakes_json TEXT NOT NULL,
  related_entity_ids_json TEXT NOT NULL,
  tags TEXT NOT NULL
);

CREATE TABLE clocks (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  value INTEGER NOT NULL,
  max INTEGER NOT NULL,
  triggers_json TEXT NOT NULL,
  tags TEXT NOT NULL
);

CREATE TABLE inventory (
  owner_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  qty INTEGER NOT NULL,
  flags_json TEXT NOT NULL,
  PRIMARY KEY (owner_id, item_id)
);

CREATE TABLE relationships (
  a_id TEXT NOT NULL,
  b_id TEXT NOT NULL,
  rel_type TEXT NOT NULL,
  intensity INTEGER NOT NULL,
  notes_json TEXT NOT NULL,
  PRIMARY KEY (a_id, b_id, rel_type)
);

CREATE TABLE events (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  turn_no INTEGER NOT NULL,
  player_input TEXT NOT NULL,
  context_packet_json TEXT NOT NULL,
  pass_outputs_json TEXT NOT NULL,
  engine_events_json TEXT NOT NULL,
  state_diff_json TEXT NOT NULL,
  final_text TEXT NOT NULL,
  prompt_versions_json TEXT NOT NULL
);

CREATE TABLE summaries (
  id TEXT PRIMARY KEY,
  scope TEXT NOT NULL,
  scope_id TEXT NOT NULL,
  text TEXT NOT NULL,
  turn_no_range TEXT NOT NULL
);

CREATE INDEX idx_events_campaign_turn ON events (campaign_id, turn_no);
CREATE INDEX idx_facts_subject ON facts (subject_id);
CREATE INDEX idx_relationships_a ON relationships (a_id);
CREATE INDEX idx_relationships_b ON relationships (b_id);
```

## Validator rules (v0)
- Presence check: referenced entities must exist and be in scene if required.
- Location check: actions must be feasible from current location or nearby.
- Inventory check: required items must be in inventory and available.
- Contradiction check: actions that violate known facts are blocked.
- Clarification policy: ask only when the outcome changes meaningfully; 1 question max.
- Cost assignment: apply Heat, Time, Cred, Harm, Rep deltas on attempts.

## Resolver rules (v0)
- Apply costs from validator regardless of success, if attempt is made.
- If a roll is required, use a banded system:
  - 2d6: 6- = fail, 7-9 = mixed, 10+ = success.
  - d20: 1-9 = fail, 10-14 = mixed, 15+ = success.
- Emit engine_events for concrete outcomes and state changes.
- Produce a state diff for commit.

## Prompt templates (spec)
- interpreter_vX.txt: inputs {context_packet, player_input} -> InterpreterOutput JSON.
- planner_vX.txt: inputs {context_packet, validator_output} -> PlannerOutput JSON.
- narrator_vX.txt: inputs {context_packet, engine_events, summary, policy} -> NarratorOutput JSON.

Example placeholder header
```
You are the Interpreter.
CONTEXT:
{{context_packet}}
PLAYER_INPUT:
{{player_input}}
OUTPUT_JSON:
```

## Replay harness spec
- Inputs: campaignId, turn range, prompt overrides, seed.
- Steps: load events, rebuild state, run pipeline with overrides, compare outputs.
- Outputs: diff report, metrics, and optional side-by-side narrator text.

## Metrics definitions
- contradiction_rate = contradictions / total turns.
- invalid_action_acceptance = invalid actions accepted / total invalid actions.
- clarification_rate = clarification turns / total turns.
- length_stats = min, avg, max of narrator output length.

## Testing plan
- Unit tests: validator rules, context builder selection, resolver clock updates.
- Integration tests: 3 to 5 golden transcripts through full pipeline.
- Regression tests: replay harness with pinned prompt versions.
