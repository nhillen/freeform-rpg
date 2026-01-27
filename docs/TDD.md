# Technical Design Document (TDD): Freeform RPG Engine

## Repository layout

```
docs/
src/
  core/           (orchestrator, validator, resolver)
  db/             (state store, schema, migrations)
  llm/            (gateway, prompt registry)
  context/        (packet builder)
  setup/          (session zero pipeline, scenario loader, calibration)
  eval/           (replay harness, metrics, snapshots)
  cli/            (main CLI, guided flow)
  content/        (v1: pack loader, lore indexer, retriever, scene cache)
  prompts/        (versioned prompt files)
  schemas/        (JSON schemas for all LLM inputs/outputs)
scenarios/        (scenario YAML files)
content_packs/    (v1: authored world sourcebooks)
tests/
```

---

## v0 Data Types (implemented)

### ContextPacket
```json
{
  "scene": {"location_id": "", "time": {}, "constraints": {}},
  "present_entities": ["entity_id"],
  "entities": [{"id": "", "type": "", "name": "", "attrs": {}, "tags": []}],
  "facts": [{"id": "", "subject_id": "", "predicate": "", "object": {}, "visibility": "", "confidence": 0, "tags": []}],
  "threads": [{"id": "", "title": "", "status": "", "stakes": {}, "related_entity_ids": [], "tags": []}],
  "clocks": [{"id": "", "name": "", "value": 0, "max": 0, "triggers": {}, "tags": []}],
  "inventory": [{"owner_id": "", "item_id": "", "qty": 0, "flags": {}}],
  "relationships": [{"a_id": "", "b_id": "", "rel_type": "", "intensity": 0, "notes": {}}],
  "summary": {"scene": "", "threads": ""},
  "recent_events": [{"turn_no": 0, "text": ""}],
  "npc_agendas": {},
  "npc_capabilities": {},
  "investigation_progress": {},
  "pending_threats": [],
  "active_situations": [],
  "failure_streak": {},
  "calibration": {},
  "lore_context": {}
}
```

Note: `lore_context` is a reserved field for v1. Empty object in v0.

### InterpreterOutput
```json
{
  "intent": "",
  "referenced_entities": ["entity_id"],
  "proposed_actions": [{"action": "", "target_id": "", "details": "", "estimated_minutes": 0}],
  "assumptions": [""],
  "risk_flags": ["violence", "sensitive", "contested", "dangerous", "pursuit", "hostile_present"],
  "perception_flags": []
}
```

### ValidatorOutput
```json
{
  "allowed_actions": [{"action": "", "target_id": "", "details": "", "costs": {"heat": 0, "time": 0, "cred": 0, "harm": 0, "rep": 0}}],
  "blocked_actions": [{"action": "", "reason": ""}],
  "clarification_needed": false,
  "clarification_question": ""
}
```

### PlannerOutput
```json
{
  "beats": [""],
  "tension_move": "",
  "tension_move_type": "",
  "clarification_question": "",
  "next_suggestions": [""]
}
```

### EngineEvent
```json
{
  "type": "",
  "details": {},
  "tags": [""],
  "scope": "campaign"
}
```

Note: `scope` field added for Layer 3-forward compatibility. Values: `campaign` (default), `world_affecting`.

### StateDiff
```json
{
  "clocks": [{"id": "", "delta": 0}],
  "facts_add": [{"subject_id": "", "predicate": "", "object": {}, "tags": [], "origin": "campaign"}],
  "facts_update": [{"id": "", "object": {}}],
  "inventory_changes": [{"owner_id": "", "item_id": "", "delta": 0}],
  "scene_update": {"location_id": "", "present_entity_ids": []},
  "threads_update": [{"id": "", "status": "", "stakes": {}}]
}
```

### NarratorOutput
```json
{
  "final_text": "",
  "next_prompt": "",
  "suggested_actions": [""],
  "established_facts": [{"subject_id": "", "predicate": "", "detail": ""}],
  "introduced_items": [{"id": "", "name": "", "description": "", "location": ""}],
  "introduced_npcs": [{"id": "", "name": "", "description": "", "type": "", "tags": []}],
  "scene_transition": {"location_id": "", "name": "", "description": "", "present_entities": []},
  "thread_updates": [{"id": "", "status": "", "reason": ""}]
}
```

---

## v0 Module Interfaces (implemented)

### StateStore
- `getState(campaignId)` -> GameState
- `applyStateDiff(campaignId, stateDiff)` -> void
- `appendEvent(eventRecord)` -> eventId
- `getEvents(campaignId, range)` -> Event[]
- `getSummary(scope, scopeId)` -> Summary

### ContextBuilder
- `buildContext(state, playerInput, options)` -> ContextPacket

### PromptRegistry
- `getPrompt(promptId, versionId)` -> PromptTemplate
- `listPromptVersions(promptId)` -> Version[]
- `pinPromptVersion(campaignId, promptId, versionId)` -> void

### LLMGateway
- `runStructured(prompt, input, schema, options)` -> LLMResponse

### Validator
- `validate(interpreterOutput, state)` -> ValidatorOutput

### Resolver
- `resolve(state, validatorOutput, plannerOutput, options)` -> {engine_events, state_diff, rolls}

### Orchestrator
- `runTurn(playerInput, campaignId, options)` -> TurnResult
- `rerunTurn(turnNo, overridePromptVersions)` -> TurnResult
- `rerunTurns(range, overridePromptVersions)` -> TurnResult[]

---

## v1 Data Types (planned: content packs and sessions)

### ContentPackManifest
```yaml
id: neo_seattle
name: "Neo-Seattle Sourcebook"
version: "1.0.0"
genre: cyberpunk
layer: setting               # core | setting | regional | adventure | homebrew
depends_on:
  - id: cyberpunk_core
    version: ">=1.0.0"
provides:
  locations: 54
  npcs: 112
  factions: 8
  chunks: ~2400
license:
  type: commercial            # commercial | cc-by | cc-by-sa | custom
  publisher: "Example Games"
  sku: "EG-2091-NS"
```

### ContentPackChunk
```json
{
  "id": "neo_seattle:neon_dragon:history",
  "pack_id": "neo_seattle",
  "file_path": "locations/neon_dragon.md",
  "section_path": "The Neon Dragon > History",
  "chunk_text": "The Neon Dragon opened in 2087...",
  "metadata": {
    "type": "location",
    "location_ids": ["neon_dragon"],
    "entity_ids": ["viktor"],
    "faction_ids": [],
    "thread_ids": [],
    "tags": ["history", "social_hub", "criminal_element"],
    "token_count": 342
  },
  "embedding_id": "chroma-abc123"
}
```

### Content file format (markdown + YAML frontmatter)
```markdown
---
id: neon_dragon
type: location
district: undercity
tags: [bar, social_hub, criminal_element]
related_entities: [viktor, jin]
related_factions: [night_market_guild]
---

# The Neon Dragon

A dive bar wedged between a defunct laundromat and a
ripperdoc clinic on Sub-Level 3...

## Atmosphere
Persistent haze of synth-tobacco and cheap cooling fluid...

## History
Viktor won the place in a card game from a Zenith
middle-manager named Ota in late 2087...

## Regulars
The Dragon draws couriers, fixers, and off-shift dock
workers...
```

### LoreRetrievalQuery
```json
{
  "location_id": "neon_dragon",
  "entity_ids": ["viktor", "player"],
  "thread_ids": ["main_case"],
  "thread_tags": ["investigation", "corporate"],
  "keywords": "ask about Jin's last delivery",
  "corpus": "all",
  "max_tokens": 3000
}
```

`corpus` values: `authored` (pack content only), `history` (play events/summaries only), `all`.

### LoreRetrievalResult
```json
{
  "chunks": [
    {
      "chunk_id": "neo_seattle:neon_dragon:history",
      "text": "Viktor won the place...",
      "relevance_score": 0.87,
      "source": "authored",
      "pack_id": "neo_seattle",
      "metadata": {}
    }
  ],
  "total_tokens": 1842,
  "query_time_ms": 45
}
```

### SceneLoreCache
```json
{
  "scene_id": "scene_001",
  "session_id": "session_abc",
  "retrieved_at": "2091-03-15T20:30:00Z",
  "atmosphere": [
    "Persistent haze of synth-tobacco...",
    "The ventilation hasn't worked since 2091..."
  ],
  "npc_briefings": {
    "viktor": {
      "disposition": "Nervous tonight. He's heard Chen is in the district.",
      "knows": ["Jin's last delivery route", "Chen's employer"],
      "withholds": ["His own debt to Zenith"],
      "capabilities": "Low threat. Fixer, not fighter. Fixed location."
    }
  },
  "discoverable": [
    {"trigger": "search behind bar", "content": "Jin's backup comm unit, stashed last week"}
  ],
  "thread_connections": {
    "main_case": "Viktor is the last person who spoke to Jin alive"
  }
}
```

### Session
```json
{
  "id": "session_abc",
  "campaign_id": "campaign_001",
  "started_at": "2091-03-15T19:00:00Z",
  "ended_at": null,
  "turn_range_start": 1,
  "turn_range_end": null,
  "session_lore": {},
  "summary": null,
  "world_events_pending": []
}
```

`world_events_pending` is a Layer 3-forward field. Empty in v1, populated by the world ticker in v3.

---

## v1 Module Interfaces (planned)

### PackLoader
- `loadPack(packPath)` -> ContentPackManifest
- `listPacks()` -> ContentPackManifest[]
- `validatePack(packPath)` -> ValidationResult
- `parseFrontmatter(filePath)` -> {metadata, content}

### LoreIndexer
- `indexPack(pack, options)` -> IndexResult
- `indexChunk(chunk)` -> chunkId
- `reindex(packId)` -> IndexResult
- `getIndexStats(packId)` -> {chunks, totalTokens, lastIndexed}

### LoreRetriever
- `query(signals, corpus, maxTokens)` -> LoreRetrievalResult
- `buildQuery(scene, entities, threads, playerInput)` -> LoreRetrievalQuery
- `retrieveForScene(sceneState, activeThreads)` -> SceneLoreCache
- `retrieveForEntity(entityId)` -> LoreRetrievalResult
- `retrieveForSession(campaignId)` -> SessionLoreContext

### SceneLoreCacheManager
- `materialize(retrievalResult, sceneId, sessionId)` -> SceneLoreCache
- `appendNPC(sceneId, npcLore)` -> void
- `get(sceneId)` -> SceneLoreCache
- `invalidate(sceneId)` -> void

### SessionManager
- `startSession(campaignId)` -> Session
- `endSession(sessionId)` -> Session (with summary generated)
- `getActiveSession(campaignId)` -> Session | null
- `generateRecap(sessionId)` -> string
- `getSessionHistory(campaignId)` -> Session[]

---

## v0 SQLite Schema (implemented)

```sql
CREATE TABLE campaigns (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  calibration_json TEXT NOT NULL DEFAULT '{}',
  system_json TEXT NOT NULL DEFAULT '{}',
  genre_rules_json TEXT NOT NULL DEFAULT '{}',
  current_turn INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE entities (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  type TEXT NOT NULL,
  name TEXT NOT NULL,
  attrs_json TEXT NOT NULL,
  tags TEXT NOT NULL,
  FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE facts (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  predicate TEXT NOT NULL,
  object_json TEXT NOT NULL,
  visibility TEXT NOT NULL,
  confidence REAL NOT NULL,
  tags TEXT NOT NULL,
  discovered_turn INTEGER,
  discovery_method TEXT,
  FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE scene (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  location_id TEXT NOT NULL,
  present_entity_ids_json TEXT NOT NULL,
  time_json TEXT NOT NULL,
  constraints_json TEXT NOT NULL DEFAULT '{}',
  visibility_conditions TEXT DEFAULT NULL,
  noise_level TEXT DEFAULT NULL,
  obscured_entities_json TEXT DEFAULT '[]',
  FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE threads (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  stakes_json TEXT NOT NULL,
  related_entity_ids_json TEXT NOT NULL,
  tags TEXT NOT NULL,
  FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE clocks (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  name TEXT NOT NULL,
  value INTEGER NOT NULL,
  max INTEGER NOT NULL,
  triggers_json TEXT NOT NULL,
  tags TEXT NOT NULL,
  FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE inventory (
  owner_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  campaign_id TEXT NOT NULL,
  qty INTEGER NOT NULL,
  flags_json TEXT NOT NULL,
  PRIMARY KEY (owner_id, item_id, campaign_id),
  FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE relationships (
  a_id TEXT NOT NULL,
  b_id TEXT NOT NULL,
  campaign_id TEXT NOT NULL,
  rel_type TEXT NOT NULL,
  intensity INTEGER NOT NULL,
  notes_json TEXT NOT NULL,
  PRIMARY KEY (a_id, b_id, rel_type, campaign_id),
  FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
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
  prompt_versions_json TEXT NOT NULL,
  FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
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
CREATE INDEX idx_facts_visibility ON facts (visibility);
CREATE INDEX idx_entities_type ON entities (type);
CREATE INDEX idx_relationships_a ON relationships (a_id);
CREATE INDEX idx_relationships_b ON relationships (b_id);
```

## v1 SQLite Schema Additions (planned)

### New tables

```sql
CREATE TABLE sessions (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  turn_range_start INTEGER,
  turn_range_end INTEGER,
  session_lore_json TEXT NOT NULL DEFAULT '{}',
  summary TEXT,
  world_events_pending TEXT NOT NULL DEFAULT '[]',
  FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE content_packs (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  genre TEXT,
  layer TEXT NOT NULL DEFAULT 'setting',
  depends_on_json TEXT NOT NULL DEFAULT '[]',
  path TEXT NOT NULL,
  license_json TEXT NOT NULL DEFAULT '{}',
  installed_at TEXT NOT NULL
);

CREATE TABLE pack_chunks (
  id TEXT PRIMARY KEY,
  pack_id TEXT NOT NULL,
  file_path TEXT NOT NULL,
  section_path TEXT NOT NULL,
  chunk_text TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  embedding_id TEXT,
  FOREIGN KEY (pack_id) REFERENCES content_packs(id)
);

CREATE TABLE scene_lore (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  scene_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  lore_json TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
  FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX idx_sessions_campaign ON sessions (campaign_id);
CREATE INDEX idx_pack_chunks_pack ON pack_chunks (pack_id);
CREATE INDEX idx_pack_chunks_metadata ON pack_chunks (metadata_json);
CREATE INDEX idx_scene_lore_scene ON scene_lore (scene_id);
```

### FTS5 virtual table for keyword search

```sql
CREATE VIRTUAL TABLE pack_chunks_fts USING fts5(
  chunk_text,
  content='pack_chunks',
  content_rowid='rowid',
  tokenize='porter unicode61'
);
```

### Layer 3-forward additions to existing tables

```sql
-- Provenance tracking on all state tables
ALTER TABLE entities ADD COLUMN origin TEXT NOT NULL DEFAULT 'campaign';
ALTER TABLE entities ADD COLUMN pack_id TEXT;
ALTER TABLE entities ADD COLUMN pack_entity_id TEXT;

ALTER TABLE facts ADD COLUMN origin TEXT NOT NULL DEFAULT 'campaign';
ALTER TABLE facts ADD COLUMN pack_id TEXT;

ALTER TABLE threads ADD COLUMN origin TEXT NOT NULL DEFAULT 'campaign';
ALTER TABLE threads ADD COLUMN pack_id TEXT;

ALTER TABLE clocks ADD COLUMN origin TEXT NOT NULL DEFAULT 'campaign';
ALTER TABLE clocks ADD COLUMN pack_id TEXT;

ALTER TABLE relationships ADD COLUMN origin TEXT NOT NULL DEFAULT 'campaign';
ALTER TABLE relationships ADD COLUMN pack_id TEXT;
```

`origin` values: `pack` (seeded from content pack), `campaign` (created during play), `world` (future: shared world truth).

`pack_entity_id` on entities: back-reference to the original pack entity, enabling Layer 3's world ticker to track divergence from baseline.

---

## Scenario ↔ Content Pack integration

Scenarios reference content packs. The scenario loader resolves packs and indexes them at campaign init.

```yaml
# scenarios/dead_drop.yaml
id: dead_drop
name: "Dead Drop"
content_pack: neo_seattle          # references installed pack
content_packs:                     # v2: multiple packs
  - neo_seattle
  - cyberpunk_core

# Entities in the scenario seed from the pack
entities:
  - id: neo_seattle:viktor         # namespaced to pack
    type: npc
    name: Viktor
    # ... attrs, tags
```

At campaign init:
1. Scenario loader reads the scenario YAML.
2. Pack loader finds and validates referenced content packs.
3. Lore indexer indexes all pack content (chunks + embeddings).
4. Scenario entities are copied into campaign state with `origin: pack` and `pack_entity_id` back-reference.
5. Campaign state can now diverge from pack content during play.

---

## Content pack authoring spec

### Directory structure

```
content_packs/
  neo_seattle/
    pack.yaml                    # manifest
    locations/
      neon_dragon.md
      datahaven.md
      zenith_tower.md
      ...
    npcs/
      viktor.md
      mira.md
      agent_chen.md
      ...
    factions/
      zenith_industries.md
      ghost_collective.md
      ...
    culture/
      street_slang.md
      social_strata.md
      ...
    history/
      corporate_wars.md
      shimizu_accords.md
      ...
    technology/
      neural_interfaces.md
      ar_overlay.md
      ...
```

### Frontmatter schema

All content files use YAML frontmatter:

```yaml
---
id: string                       # unique within pack, becomes pack_name:id
type: location | npc | faction | culture | history | technology | item | event
tags: [string]                   # freeform tags for retrieval
related_entities: [string]       # entity IDs this content relates to
related_factions: [string]       # faction IDs
related_locations: [string]      # location IDs
related_threads: [string]        # thread IDs (adventure-specific)
---
```

### Chunking strategy

Content is chunked by markdown headers:
- H1 = document-level chunk (full intro/overview)
- H2 = section-level chunk (Atmosphere, History, Regulars, etc.)
- H3+ = subsection, merged into parent H2 chunk

Each chunk inherits the frontmatter metadata from its parent file plus its section path. Typical chunk size: 200-500 tokens.

### ID namespacing

All entity IDs from content packs are namespaced: `pack_id:entity_id`.
- `neo_seattle:neon_dragon` — a location from the Neo-Seattle pack
- `neo_seattle:viktor` — an NPC from the Neo-Seattle pack
- `campaign_abc:informant_3` — an NPC created during campaign play

The context builder, validator, and resolver all work with fully-qualified IDs internally. Display names remain human-readable. Cross-pack references use the full namespace.

---

## Indexing pipeline spec

At pack install / campaign init:

1. **Parse**: walk pack directory, parse all .md files, extract frontmatter + body.
2. **Chunk**: split by H2 headers, preserving hierarchy metadata (file → section).
3. **Metadata extraction**: merge frontmatter fields into chunk metadata (entity IDs, location IDs, faction IDs, tags, type).
4. **FTS5 indexing**: insert chunk text into SQLite FTS5 virtual table for keyword search.
5. **Embedding generation**: call embedding model (Voyage, OpenAI ada-002, or local nomic-embed-text) for each chunk. Store embedding ID in chunk record.
6. **ChromaDB indexing**: insert embeddings with metadata into ChromaDB collection. One collection per campaign (unified across all loaded packs).

### Embedding model selection

| Model | Pros | Cons |
|-------|------|------|
| Voyage (Anthropic) | Same ecosystem as Claude | API dependency |
| OpenAI ada-002 | Well-tested, cheap | Cross-provider dependency |
| nomic-embed-text | Self-hosted, no API costs | Local compute, setup complexity |

Default recommendation: Voyage for API-based, nomic-embed-text for self-hosted.

---

## Retrieval strategy spec

### Three-stage hybrid retrieval

**Stage 1 — Metadata filter (structured)**:
```python
filter = {
    "$or": [
        {"location_ids": {"$contains": scene.location_id}},
        {"entity_ids": {"$contains": any_of(scene.present_entity_ids)}},
        {"faction_ids": {"$contains": any_of(active_faction_ids)}},
        {"thread_ids": {"$contains": any_of(active_thread_ids)}},
        {"tags": {"$contains": any_of(relevant_tags)}}
    ]
}
```

**Stage 2 — Semantic ranking (vector)**:
```python
query_text = build_retrieval_query(scene, entities, threads, player_input)
results = chromadb.query(
    query_texts=[query_text],
    where=filter,
    n_results=top_k * 2  # over-fetch for reranking
)
```

**Stage 3 — Budget cap**:
```python
selected = []
token_budget = max_tokens  # configurable, default 3000
for chunk in ranked_results:
    if token_budget - chunk.token_count >= 0:
        selected.append(chunk)
        token_budget -= chunk.token_count
    else:
        break
```

### Query construction

```python
def build_retrieval_query(scene, player_input, active_threads, recent_events):
    parts = [
        f"Location: {scene['location_id']}",
        f"Present: {', '.join(scene['present_entity_ids'])}",
        f"Player action: {player_input}",
        f"Active threads: {', '.join(t['title'] for t in active_threads)}",
        f"Recent: {recent_events[-1]['summary'] if recent_events else ''}",
    ]
    return "\n".join(parts)
```

### Retrieval corpus separation

The retriever queries two conceptually separate corpora:

| Corpus | Content | Source | Mutability |
|--------|---------|--------|------------|
| `authored` | Content pack chunks | Pack markdown files | Immutable (static sourcebook) |
| `history` | Campaign event summaries, session summaries, established facts | Play-generated state | Grows over time |

Both may live in the same ChromaDB collection with a `corpus` metadata field. The retriever API accepts a `corpus` parameter to filter.

In v3 (shared worlds), `history` expands to include cross-campaign world history generated by the world ticker.

---

## v0 Validator rules (implemented)

- Presence check: referenced entities must exist and be in scene if required.
- Location check: actions must be feasible from current location or nearby.
- Inventory check: required items must be in inventory and available.
- Contradiction check: actions that violate known facts are blocked.
- Clarification policy: ask only when the outcome changes meaningfully; 1 question max.
- Cost assignment: apply Heat, Time, Cred, Harm, Rep deltas on attempts.

## v0 Resolver rules (implemented)

- Apply costs from validator regardless of success, if attempt is made.
- 2d6 banded system: 6- = fail, 7-9 = mixed, 10+ = success, 12 = critical.
- Emit engine_events for concrete outcomes and state changes.
- Failure consequence tiers: Tier 0 (safe), Tier 1 (risky), Tier 2 (dangerous).
- Failure streak tracking with binding consequences at threshold.
- NPC escalation profiles (soft → hard → lethal).
- Produce state diff for commit.

## Prompt templates (spec)

- `interpreter_vX.txt`: inputs {context_packet, player_input} -> InterpreterOutput JSON.
- `planner_vX.txt`: inputs {context_packet, validator_output} -> PlannerOutput JSON.
- `narrator_vX.txt`: inputs {context_packet, engine_events, planner_output, blocked_actions} -> NarratorOutput JSON.
- v1: narrator prompt gains `{{lore_context}}` section for scene lore injection.

## Replay harness spec

- Inputs: campaignId, turn range, prompt overrides, seed.
- Steps: load events, rebuild state, run pipeline with overrides, compare outputs.
- Outputs: diff report, metrics, and optional side-by-side narrator text.

## Metrics definitions

- `contradiction_rate` = contradictions / total turns.
- `invalid_action_acceptance` = invalid actions accepted / total invalid actions.
- `clarification_rate` = clarification turns / total turns.
- `length_stats` = min, avg, max of narrator output length.
- v1: `lore_relevance_rate` = relevant chunks / total chunks retrieved per scene.
- v1: `lore_cache_hit_rate` = turns using cached lore / total turns.

## Testing plan

- Unit tests: validator rules, context builder selection, resolver clock updates. (implemented)
- Integration tests: golden transcripts through full pipeline. (implemented)
- Regression tests: replay harness with pinned prompt versions. (implemented)
- v1: content pack loading and validation tests.
- v1: indexing pipeline tests (chunking, metadata extraction, FTS5 insertion).
- v1: retrieval accuracy tests (known-good queries against test pack).
- v1: scene lore cache lifecycle tests.
- v1: session start/end lifecycle tests.

## LLM provider (v0)

- Initial provider: Claude via gateway adapter (currently claude-sonnet-4-20250514).
- Provider-agnostic gateway interface for future additions.
- MockGateway for testing without API calls.
