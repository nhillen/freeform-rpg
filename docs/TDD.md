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
  cli/            (main CLI, guided flow, ingest flow)
  content/        (pack loader, chunker, lore indexer, retriever, scene cache, session manager, vector store)
  ingest/         (PDF ingest pipeline: extract, structure, segment, classify, enrich, assemble, validate, systems)
  prompts/        (versioned prompt files: turn pipeline + ingest pipeline)
  schemas/        (JSON schemas for all LLM inputs/outputs: turn pipeline + ingest pipeline)
scenarios/        (scenario YAML files)
content_packs/    (authored world sourcebooks)
tests/
  unit/           (per-module tests including ingest stages)
  integration/    (end-to-end pipeline tests)
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

## v1 Data Types (implemented: content packs and sessions)

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

## v1 Module Interfaces (implemented)

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

## v1 SQLite Schema Additions (implemented)

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

## Scenario ↔ Content Pack integration (implemented)

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

## Content pack authoring spec (implemented)

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

## Indexing pipeline spec (implemented)

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

## Retrieval strategy spec (implemented)

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

## PDF Ingest Pipeline (implemented)

### Overview

8-stage pipeline converting PDF sourcebooks into content packs. Each stage writes checkpoint metadata (`stage_meta.json`) enabling resume from any stage.

```
PDF → Extract → Structure → Segment → Classify → Enrich → Assemble → Validate → [Systems]
                                                                                      ↓
                                                                              Content Pack
```

### Pipeline stages

| # | Stage | Module | Purpose | LLM? |
|---|-------|--------|---------|------|
| 1 | Extract | `ingest/extract.py` | PDF text extraction with OCR fallback | No |
| 2 | Structure | `ingest/structure.py` | Document hierarchy and chapter intent detection | Fallback |
| 3 | Segment | `ingest/segment.py` | Split into RAG-optimized chunks | Fallback |
| 4 | Classify | `ingest/classify.py` | Content type + route classification | Verification |
| 5 | Enrich | `ingest/enrich.py` | Entity extraction, frontmatter, tags | Yes (Sonnet + Haiku) |
| 6 | Assemble | `ingest/assemble.py` | Build pack directory structure | No |
| 7 | Validate | `ingest/validate.py` | Structural, installation, retrieval checks | No |
| S1-S3 | Systems | `ingest/systems_extract.py`, `systems_assemble.py`, `systems_validate.py` | Game mechanics extraction | Yes |

### Stage 1: Extract (PDFExtractor)

- **Library**: PyMuPDF (fitz) with optional Tesseract OCR fallback
- **Features**: multi-column layout detection, header/footer stripping (samples ~10% of pages), image extraction, configurable page ranges
- **Outputs**: `pages/page_*.md`, `page_map.json`, `stage_meta.json`

### Stage 2: Structure (StructureDetector)

Four detection methods in priority order:
1. Font-size analysis from PDF metadata
2. Table of Contents parsing (regex: `Title...PageNum`)
3. Text heuristics (ALL-CAPS, markdown headers, numbered patterns)
4. LLM fallback (Haiku) for ambiguous documents

Chapter intent classification (9 types): SETTING, FACTIONS, MECHANICS, CHARACTERS, NARRATIVE, REFERENCE, META, EQUIPMENT, BESTIARY.

**Outputs**: `structure.json`, `chapters/*.md`, `stage_meta.json`

### Stage 3: Segment (ContentSegmenter)

Configurable chunk sizes: 150-2000 words, target 600. Segmentation strategies (in order):
1. Header-boundary splitting (H2/H3)
2. Size enforcement (merge small, split large)
3. Paragraph-boundary splitting (fallback)
4. LLM splitting (for mixed content)

Filters META intent sections (copyright, TOC, credits).

**Outputs**: `segment_manifest.json`, `segments/*.md`, `stage_meta.json`

### Stage 4: Classify (ContentClassifier)

Two-axis classification:
- **Content type** (10 types): LOCATION, NPC, FACTION, CULTURE, ITEM, EVENT, HISTORY, RULES, TABLE, GENERAL
- **Route**: LORE, SYSTEMS, or BOTH

Rule-based first (22 mechanical indicator patterns: dice notation, DC, HP, modifiers, thresholds, clocks, escalation). Chapter intent biases route decision. Low-confidence (<0.7) segments verified via LLM in batches of 10.

**Outputs**: updated `segment_manifest.json`, `stage_meta.json`

### Stage 5: Enrich (LoreEnricher)

Processes lore-routed segments through 4 sub-stages:
- **5a**: Entity extraction (Sonnet, batches of 15, deduplication by entity ID)
- **5b**: Per-segment enrichment with YAML frontmatter (related entities, tags, source tracking)
- **5c**: Size validation (warns on oversized files)
- **5d**: Batch tag generation (Haiku)

**Outputs**: `enriched/{type}/*.md`, `entity_registry.json`, `stage_meta.json`

### Stage 6: Assemble (PackAssembler)

Organizes enriched files into pack directory structure:
```
{pack_id}/
  pack.yaml           # Manifest (id, name, version, description, layer, author, tags)
  locations/
  npcs/
  factions/
  culture/
  items/
```

### Stage 7: Validate (PackValidator)

Three-phase validation:
1. **Structural**: pack.yaml existence, YAML validity, manifest fields, markdown formatting
2. **Installation test**: in-memory DB instantiation via PackLoader/Chunker/LoreIndexer
3. **Retrieval spot-checks**: FTS5 queries against indexed content

Returns `ValidationReport` with errors, warnings, and stats.

### Stages S1-S3: Systems Extraction (optional)

**S1 Extract**: 7 sub-extractors on systems-routed segments:
- Resolution (dice, outcome bands, modifiers)
- Clocks (types, thresholds, triggers)
- Entity stats (NPC blocks, threat levels)
- Conditions (status effects, states)
- Calibration (difficulty presets)
- Action types (available actions, costs)
- Escalation (profiles, trigger chains)

Combines heuristic patterns + LLM extraction, written to `{key}.yaml`.

**S2 Assemble**: Merges into engine configs (`scenario_fragment.yaml`, `entity_templates.yaml`, `calibration_preset.yaml`, `conditions_config.yaml`, `resolution_mapping.yaml`).

**S3 Validate**: Validates configs against entity registry and engine schema.

### Ingest data models

Defined in `src/ingest/models.py`:

```python
PageEntry              # Single extracted page
ExtractionResult       # Stage 1 output
ChapterIntent          # 9-valued enum (SETTING, FACTIONS, MECHANICS, ...)
SectionNode            # Hierarchical document tree node
DocumentStructure      # Stage 2 output
ContentType            # 10-valued enum (LOCATION, NPC, FACTION, ...)
Route                  # Routing enum (LORE, SYSTEMS, BOTH)
SegmentEntry           # Individual segment with metadata
SegmentManifest        # Collection of segments with statistics
EntityEntry            # Named entity with type, aliases, relationships
EntityRegistry         # Global entity index built during enrichment
SystemsExtractionManifest  # Extracted mechanical data
IngestConfig           # Full pipeline configuration
```

### Ingest prompt templates

12 versioned prompt templates in `src/prompts/`:

| Template | Model | Purpose |
|----------|-------|---------|
| `structure_v0.txt` | Haiku | Document structure detection fallback |
| `segment_v0.txt` | Haiku | LLM-assisted segmentation |
| `classify_v0.txt` | Haiku | Segment classification verification |
| `enrich_entities_v0.txt` | Sonnet | Entity extraction from segments |
| `enrich_segment_v0.txt` | Sonnet | Per-segment enrichment |
| `enrich_tags_v0.txt` | Haiku | Batch tag generation |
| `systems_resolution_v0.txt` | Sonnet | Resolution mechanics extraction |
| `systems_clocks_v0.txt` | Sonnet | Clock system extraction |
| `systems_entity_stats_v0.txt` | Sonnet | Entity stat block extraction |
| `systems_conditions_v0.txt` | Sonnet | Status effect extraction |
| `systems_calibration_v0.txt` | Sonnet | Difficulty preset extraction |
| `systems_action_types_v0.txt` | Sonnet | Action type extraction |

### Ingest JSON schemas

12 schemas in `src/schemas/`:
- `segment_output.schema.json` — Segmentation output
- `structure_output.schema.json` — Hierarchical section list
- `classify_output.schema.json` — Classification results (batch)
- `enrich_entities_output.schema.json` — Entity extraction
- `enrich_segment_output.schema.json` — Segment enrichment
- `enrich_tags_output.schema.json` — Tag generation
- `systems_resolution_output.schema.json` — Resolution mechanics
- `systems_clocks_output.schema.json` — Clock definitions
- `systems_entity_stats_output.schema.json` — Entity stat blocks
- `systems_conditions_output.schema.json` — Status effects
- `systems_calibration_output.schema.json` — Difficulty presets
- `systems_action_types_output.schema.json` — Action types

### Ingest CLI flow

Interactive guided pipeline via `freeform-rpg pack-ingest`:
1. Dependency check (pymupdf, optional pytesseract)
2. API key prompt/retrieval
3. PDF file selection
4. Pack metadata (id, name, version, layer, author, description)
5. Options (OCR, image extraction, systems extraction)
6. Output directory selection
7. Confirmation summary
8. Pipeline execution with per-stage spinners and progress
9. Validation results display
10. Install offer for completed pack

LLM configuration: Sonnet for quality-critical stages (entity extraction, enrichment), Haiku for cheap stages (structure, classification, tagging).

---

## Systems Extraction Philosophy

The systems extraction pipeline (stages S1-S3) extracts game-mechanical data from PDFs. This section documents the architectural philosophy and guidelines for contributors.

### LLM-Primary Architecture

**Core principle**: LLM is the primary extractor. Heuristics pre-filter content to reduce context size and cost, NOT to extract specific patterns.

```
Raw PDF Pages
    ↓
Stage 1: Structural Pre-filter (Heuristics)
    - Detect pages with tables, rating scales, stat blocks
    - Identify mechanical vs narrative content by STRUCTURE
    - NO hardcoded game terminology
    ↓
Stage 2: LLM Extraction (Primary)
    - Send filtered mechanical pages to LLM
    - Generic schema: "extract game mechanics you find"
    - LLM understands semantically, returns structured data
    ↓
Stage 3: System Detection (Optional, Modular)
    - If system family detected (WoD, d20, PbtA, etc.)
    - Load system-specific post-processing config
    - Enhance/validate extracted data
    ↓
Output: Generic mechanical data + optional system-specific enrichment
```

### What Heuristics Should Do

**DO**: Detect structural patterns that indicate mechanical content:
- Multi-column tables with numbers
- Bulleted lists with rating scales (•, ••, •••)
- Section headers followed by stat-like terms
- Penalty ladders (lists of states with modifiers)
- Dice notation anywhere (XdY patterns)

**DON'T**: Look for specific game terminology:
- "Strength, Dexterity, Constitution" (D&D attributes)
- "Bruised, Hurt, Wounded" (WoD health levels)
- "Correspondence, Entropy, Forces" (Mage spheres)
- "Revolver, Pistol, Rifle" (specific weapon names)

### Adding New Extractors

When adding extraction patterns to `systems_extract.py`:

1. **Ask**: "Would this pattern work for a completely different TTRPG?"
2. **If no**: Refactor to detect structure, not content
3. **Example transformation**:
   - ❌ `r"bruised|hurt|wounded|mauled|crippled"` (WoD-specific)
   - ✅ `r"^\s*\w+\s*:\s*-?\d+\s*penalty"` (detects penalty ladder structure)

### Known Technical Debt

The current implementation has some hardcoded patterns that need refactoring. See `docs/BACKLOG.md` → "Ingest Pipeline — Technical Debt" for the full tracked list.

Summary of issues:
- `_extract_equipment()` — hardcoded weapon names
- `_extract_health()` — WoD health level names
- `sphere_extract.py` — hardcoded Mage sphere names
- `systems_refine.py` — only refines 2 of 9 extractors

### System-Specific Post-Processing (Future)

When a game system is detected or specified, the pipeline can apply system-specific validation and enrichment. This is separate from extraction:

```yaml
# Future: src/ingest/system_configs/wod.yaml
system_family: wod
validates:
  - attributes use 1-5 dot scale
  - abilities use 1-5 dot scale
  - special traits can go to 10
enriches:
  - map detected health track to WoD health levels
  - identify Disciplines/Spheres from ranked ability patterns
```

---

## System Extraction Configuration (implemented)

The pipeline now supports system-specific extraction configuration via YAML files in `systems/`. This provides reusable patterns for known game systems while maintaining generic structural detection as the baseline.

### Directory Structure

```
systems/
  _base.yaml                    # Generic TTRPG patterns (always loaded)
  world_of_darkness.yaml        # WoD family (Vampire, Werewolf, Mage)
  pbta.yaml                     # Powered by the Apocalypse (future)
  osr.yaml                      # Old School Revival (future)

content_packs/
  mage_traditions/
    pack.yaml                   # system: world_of_darkness
    extraction.yaml             # OPTIONAL: Pack-specific overrides
```

### Inheritance Chain

Configs are merged in order: `_base.yaml → system.yaml → pack/extraction.yaml`

```
_base.yaml (generic structure detection)
    ↓
world_of_darkness.yaml (WoD-specific patterns)
    ↓
pack/extraction.yaml (pack-specific tweaks)
```

### System Config Schema

```yaml
# systems/world_of_darkness.yaml
id: world_of_darkness
name: "World of Darkness"
inherits: _base               # Config to inherit from

# Runtime resolution (used by game engine)
resolution:
  method: dice_pool           # dice_pool | sum_bands | target_number
  die_type: 10
  difficulty_range: [3, 10]
  difficulty_default: 6
  ones_cancel_successes: true
  botch_on_ones: true
  pool_outcome_thresholds:
    botch: 0
    failure: 0
    mixed: 1
    success: 2
    critical: 4

# Stat schema for this system
stat_schema:
  attributes:
    physical: [strength, dexterity, stamina]
    social: [charisma, manipulation, appearance]
    mental: [perception, intelligence, wits]
  abilities:
    talents: [alertness, athletics, awareness, ...]
    skills: [crafts, drive, etiquette, ...]
    knowledges: [academics, computer, finance, ...]
  special_traits:
    willpower: {min: 1, max: 10}

# Extraction configuration (used by ingest pipeline)
extraction:
  # Indicators that a page has mechanical content
  mechanical_indicators:
    - pattern: "●+"
      meaning: rating_dots
      confidence: 0.9
    - pattern: "^(Strength|Dexterity|Stamina|...)"
      meaning: attribute_name
      confidence: 0.95
    - pattern: "(Bruised|Hurt|Injured|...)"
      meaning: health_track
      confidence: 0.95

  # Section detection for hierarchical content
  section_patterns:
    spheres:
      header_pattern: "^(Correspondence|Entropy|Forces|...)$"
      content_type: ranked_ability
      rating_type: dots
    disciplines:
      header_pattern: "^(Animalism|Auspex|Celerity|...)$"
      content_type: ranked_ability
      rating_type: dots

  # How to interpret rating scales
  rating_scales:
    dots:
      symbol: "●"
      empty_symbol: "○"
      max: 5
      descriptions:
        1: "Poor"
        5: "Outstanding"
    difficulty:
      range: [3, 10]
      default: 6

  # Health track configuration
  health:
    track_type: levels
    levels:
      - {name: "Bruised", penalty: 0}
      - {name: "Hurt", penalty: -1}
      - {name: "Injured", penalty: -1}
      - {name: "Wounded", penalty: -2}
      - {name: "Mauled", penalty: -2}
      - {name: "Crippled", penalty: -5}
      - {name: "Incapacitated", penalty: null}
    damage_types: [bashing, lethal, aggravated]

  # GM Guidance detection
  gm_guidance:
    chapter_indicators:
      - "Storytelling"
      - "Chronicle"
      - "Running the Game"
    content_patterns:
      - pattern: "(Storyteller|ST)\\s+(should|can|might)"
        meaning: gm_technique
        confidence: 0.9
    categories: [pacing, scene_types, tone, player_agency, npc_portrayal]
```

### Pack Override Example

```yaml
# content_packs/mage_traditions/extraction.yaml
extends: world_of_darkness    # Inherit from this system

extraction:
  section_patterns:
    # Add Mage-specific sections
    paradigm:
      header_pattern: "^Paradigm$"
      content_type: philosophical_framework
    foci:
      header_pattern: "^(Unique )?Foci$"
      content_type: equipment_list
    rotes:
      header_pattern: "^Rotes$"
      content_type: spell_list
```

### Using System Configs

**CLI flag:**
```bash
freeform-rpg pack-ingest --system-hint world_of_darkness input.pdf
```

**Pack manifest:**
```yaml
# pack.yaml
id: mage_traditions
name: "Traditions Sourcebook"
system: world_of_darkness     # Links to systems/world_of_darkness.yaml
```

**Programmatic:**
```python
from src.ingest.systems_config import load_extraction_config

# Load with system hint
config = load_extraction_config(system_hint="world_of_darkness")

# Load from pack (reads pack.yaml's system field)
config = load_extraction_config(pack_path=Path("content_packs/mage_traditions"))
```

### ExtractionConfig Data Model

```python
@dataclass
class ExtractionConfig:
    id: str                           # Config ID (e.g., "world_of_darkness")
    name: str                         # Human-readable name
    inherits: Optional[str]           # Parent config to inherit from
    extraction: ExtractionHints       # Extraction patterns and hints
    sources: list[str]                # Config files that were merged

@dataclass
class ExtractionHints:
    mechanical_indicators: list[MechanicalIndicator]
    section_patterns: dict[str, SectionPattern]
    rating_scales: dict[str, RatingScale]
    stat_blocks: StatBlockHints
    health: HealthConfig
    gm_guidance: GuidanceConfig
```

### GM Guidance Extraction

The pipeline extracts storytelling advice from sourcebooks, categorizing it as:

1. **Universal** — Applicable to any RPG (candidates for core prompt refinement)
2. **Genre-specific** — Tied to this game/setting (stays in pack's `storytelling/` directory)

**Output structure:**
```
draft/pack_id/
  storytelling/
    pacing.md            # Pacing advice extracted
    tone.md              # Tone/mood guidance
    scene_types.md       # Scene archetype advice
    npc_portrayal.md     # NPC portrayal techniques
  gm_guidance_review.md  # Universal candidates for manual review
```

**Review workflow:**
1. Pipeline extracts GM guidance chunks
2. Classifier tags each as universal or genre-specific
3. `gm_guidance_review.md` lists universal candidates
4. Human reviews and optionally adds to core prompts (`narrator_v0.txt`, etc.)

### Draft Output Mode

When using `--draft` flag, output goes to `draft/{pack_id}/` with review markers:

```bash
freeform-rpg pack-ingest --draft --system-hint world_of_darkness input.pdf
```

**Draft structure:**
```
draft/mage_traditions/
  pack.yaml
  REVIEW_NEEDED.md          # Items requiring manual review
  DRAFT_README.md           # Instructions for review
  locations/
  npcs/
  factions/
  culture/
  storytelling/             # GM guidance content
  gm_guidance_review.md     # Universal candidates
```

**Promotion:**
```bash
freeform-rpg promote-draft draft/mage_traditions
# → Copies to content_packs/mage_traditions/ (excluding review markers)
```

### Confidence Scoring

Each extraction includes confidence metadata:

```yaml
# In systems/extract/health.yaml
health_levels:
  - name: "Bruised"
    dice_penalty: 0
  - name: "Hurt"
    dice_penalty: -1
_extraction_metadata:
  confidence: 0.85              # 0.0-1.0
  config_patterns_matched: 7    # How many config patterns hit
```

The `EXTRACTION_REPORT.md` summarizes confidence across extractors:

```markdown
## Extractor Results

| Extractor | Confidence | Fields |
|-----------|------------|--------|
| resolution | 78% | 5 |
| health | 85% | 3 |
| magic | 45% (low) | 2 |
```

### Available System Configs

List available system configs:
```bash
freeform-rpg list-systems
```

Current configs:
- `_base` — Generic TTRPG structural patterns (always applied)
- `world_of_darkness` — WoD family (Vampire, Werewolf, Mage, etc.)

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

### Turn pipeline prompts
- `interpreter_vX.txt`: inputs {context_packet, player_input} -> InterpreterOutput JSON.
- `planner_vX.txt`: inputs {context_packet, validator_output} -> PlannerOutput JSON.
- `narrator_vX.txt`: inputs {context_packet, engine_events, planner_output, blocked_actions} -> NarratorOutput JSON. Includes `{{lore_context}}` section for scene lore injection.

### Ingest pipeline prompts
- `structure_vX.txt`: document structure detection fallback (Haiku).
- `segment_vX.txt`: LLM-assisted content segmentation (Haiku).
- `classify_vX.txt`: segment classification verification (Haiku).
- `enrich_entities_vX.txt`: entity extraction from segments (Sonnet).
- `enrich_segment_vX.txt`: per-segment enrichment with frontmatter (Sonnet).
- `enrich_tags_vX.txt`: batch tag generation (Haiku).
- `systems_resolution_vX.txt`: resolution mechanics extraction (Sonnet).
- `systems_clocks_vX.txt`: clock system extraction (Sonnet).
- `systems_entity_stats_vX.txt`: entity stat block extraction (Sonnet).
- `systems_conditions_vX.txt`: status effect extraction (Sonnet).
- `systems_calibration_vX.txt`: difficulty preset extraction (Sonnet).
- `systems_action_types_vX.txt`: action type extraction (Sonnet).

## Replay harness spec

- Inputs: campaignId, turn range, prompt overrides, seed.
- Steps: load events, rebuild state, run pipeline with overrides, compare outputs.
- Outputs: diff report, metrics, and optional side-by-side narrator text.

## Metrics definitions

- `contradiction_rate` = contradictions / total turns.
- `invalid_action_acceptance` = invalid actions accepted / total invalid actions.
- `clarification_rate` = clarification turns / total turns.
- `length_stats` = min, avg, max of narrator output length.
- `lore_relevance_rate` = relevant chunks / total chunks retrieved per scene.
- `lore_cache_hit_rate` = turns using cached lore / total turns.

## Testing plan

### v0 (implemented)
- Unit tests: validator rules, context builder selection, resolver clock updates.
- Integration tests: golden transcripts through full pipeline.
- Regression tests: replay harness with pinned prompt versions.

### v1 content packs (implemented)
- Content pack loading and validation tests.
- Indexing pipeline tests (chunking, metadata extraction, FTS5 insertion).
- Retrieval accuracy tests (known-good queries against test pack).
- Scene lore cache lifecycle tests.
- Session start/end lifecycle tests.

### v1 ingest pipeline (implemented)
13 unit test files + 1 integration test covering all 8 stages:
- `test_ingest_pipeline.py` — Config, stage constants, from_stage clearing, resume logic.
- `test_ingest_extract.py` — PDF extraction, header/footer stripping (mocked fitz).
- `test_ingest_structure.py` — Font detection, text heuristics, TOC parsing, intent classification.
- `test_ingest_segment.py` — Header-boundary splitting, size enforcement, LLM splitting fallback.
- `test_ingest_classify.py` — Location/NPC/faction/rules classification, routing, mechanical patterns.
- `test_ingest_enrich.py` — Entity extraction, frontmatter generation, tag generation.
- `test_ingest_assemble.py` — Pack directory creation, manifest writing.
- `test_ingest_validate.py` — Structural validation, installation test.
- `test_ingest_models.py` — Model instantiation, enum conversions.
- `test_ingest_utils.py` — Slugify, word count, page range parsing, markdown I/O.
- `test_ingest_systems_extract.py` — Systems extraction sub-extractors.
- `test_ingest_systems_assemble.py` — Systems config assembly.
- `test_ingest_systems_validate.py` — Systems config validation.
- `tests/integration/test_ingest_pipeline.py` — Full pipeline end-to-end.

Test patterns: mocked fitz for PDF testing, parametrized classification tests, tmp_path fixtures, output file validation.

## LLM provider (v0)

- Initial provider: Claude via gateway adapter (currently claude-sonnet-4-20250514).
- Provider-agnostic gateway interface for future additions.
- MockGateway for testing without API calls.
