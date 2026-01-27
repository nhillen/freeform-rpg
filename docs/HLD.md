# High-Level Design (HLD): Freeform RPG Engine

## System context

```
Content Packs (authored world sourcebooks)
     ↓ [indexed at campaign init]
Lore Index (ChromaDB + FTS5)
     ↓ [queried at session/scene boundaries]
Player <-> UI <-> Turn Orchestrator <-> (State Store, Context Builder, Lore Retriever, LLM Gateway, Validator/Resolver) <-> Prompt Registry
```

## Key objectives

- Feel like a prepared GM running a game night — session structure, scene pacing, world depth.
- Deep world knowledge from sourcebook-scale content packs, retrieved via RAG at scene boundaries.
- Fast replay and iteration for prompts and rules.
- Modular components that allow inspiration-driven changes without losing state.
- Genre-flexible engine with setting defined by content packs and prompts.
- Forward-compatible with shared evolving worlds (multi-campaign, world ticker).

## Content hierarchy

```
Content Pack (the world — sourcebook-scale authored content)
  └── Scenario (an adventure — entities, clocks, threads, mechanical state)
        └── Session (one game night of play)
              └── Scene (a location/situation, lore cached at boundary)
                    └── Turn (one player action)
```

Content packs are immutable sourcebooks. Scenarios seed campaign state from packs. Sessions group turns into game nights. Scenes are the unit of lore retrieval. Turns never hit the lore index directly.

## Components

### Existing (v0 — complete)
- **Turn Orchestrator**: executes pipeline, enforces 1-question policy, logs artifacts.
- **State Store (SQLite)**: canonical entities, facts, scene, etc; append-only events.
- **Context Packet Builder**: deterministic selection and cap of relevant state.
- **LLM Gateway**: structured outputs, schema validation, retries, prompt version tagging.
- **Validator**: code-first constraints and contradiction checks.
- **Planner (LLM)**: optional beat outline and tension move.
- **Resolver**: deterministic application of rules, clock deltas, consequence escalation.
- **Narrator (LLM)**: final prose, introduces items/NPCs/facts/scene transitions.
- **Prompt Registry**: versioned prompt templates, pin per campaign.
- **Replay Harness**: rerun transcripts, compare outputs, compute metrics.
- **Evaluation Tracker**: per-turn metrics, player feedback, quality signals.
- **Setup Pipeline**: session zero, scenario loading, calibration, character creation.

### Planned (v1 — content packs and sessions)
- **Content Pack Loader**: parses markdown + YAML frontmatter directory structure into indexed chunks.
- **Lore Indexer**: chunks content by section, extracts metadata, builds FTS5 + vector index (ChromaDB).
- **Lore Retriever**: hybrid query (metadata filter → semantic ranking → budget cap). Queries two corpora: authored lore (from packs) and play history (from campaign events/summaries).
- **Scene Lore Cache**: materializes retrieved lore at scene boundaries. Structured sections: atmosphere, NPC briefings, discoverable content, thread connections.
- **Session Manager**: session start/end lifecycle, lore caching, "previously on" summary generation.

### Future (v3 — shared worlds)
- **World State Store**: shared canonical state separate from campaign state.
- **World Ticker**: between-session reconciliation of world-affecting events.
- **Event Propagator**: tags and routes world-affecting events from campaigns to world ticker.
- **Conflict Resolver**: handles contradictory world events from concurrent campaigns.

## Turn pipeline (v0 — implemented)

1. Load state, build context packet.
2. Interpreter LLM: intent, entities, actions, assumptions, risk flags.
3. Validator: allowed/blocked actions, clarification need, costs.
4. Planner LLM: beats, tension move, optional clarifying question.
5. Resolver: apply deltas, rolls, emit engine_events, state diff.
6. Narrator LLM: prose outcome, established facts, introduced items/NPCs, scene transitions.
7. Commit: write events, apply state diff, persist narrator introductions, update summaries.

## Lore retrieval lifecycle (v1 — planned)

Mirrors GM prep: heavy at boundaries, silent during play.

**Session start:**
- Retrieve campaign-level lore (faction summaries, world state, setting overview).
- Generate "previously on" summary from last session's events.
- Cache as session-level lore context.

**Scene transition** (triggered by narrator's `scene_transition`):
- Retrieve location-specific lore, backstories for present NPCs, relevant thread lore.
- Materialize into structured scene lore cache:
  - `atmosphere`: setting details for narrator voice
  - `npc_briefings`: dispositions, knowledge, withheld info for interpreter/planner
  - `discoverable`: what can be found here for resolver
  - `thread_connections`: plot relevance for planner tension moves

**Mid-scene NPC introduction** (triggered by narrator's `introduced_npcs`):
- Incremental fetch for newly introduced NPC's lore only.
- Append to scene lore cache.

**Turn-level:**
- No retrieval. Context builder reads from materialized scene lore cache.

## Hybrid retrieval strategy

Three-stage query:
1. **Metadata filter**: narrow to chunks matching location, entity IDs, faction, thread tags from loaded packs.
2. **Semantic ranking**: within filtered set, rank by embedding similarity to a query constructed from scene context + player action + active threads.
3. **Token budget cap**: take top-K chunks within budget (configurable, default ~2-4K tokens of lore per scene).

Query construction uses structured signals (not just raw player input):
- Current location ID
- Present entity IDs
- Active thread titles and tags
- Recent event summary
- Player input text

## Data model summary

### Existing (v0)
- entities(id, type, name, attrs_json, tags)
- facts(id, subject_id, predicate, object_json, visibility, confidence, tags, discovered_turn, discovery_method)
- scene(id, location_id, present_entity_ids_json, time_json, constraints_json, visibility_conditions, noise_level, obscured_entities_json)
- threads(id, title, status, stakes_json, related_entity_ids_json, tags)
- clocks(id, name, value, max, triggers_json, tags)
- inventory(owner_id, item_id, qty, flags_json)
- relationships(a_id, b_id, rel_type, intensity, notes_json)
- events(id, campaign_id, turn_no, player_input, context_packet_json, pass_outputs_json, engine_events_json, state_diff_json, final_text, prompt_versions_json)
- campaigns(id, name, created_at, updated_at, calibration_json, system_json, genre_rules_json, current_turn)
- summaries(id, scope, scope_id, text, turn_no_range)

### Planned (v1 — Layer 3-forward fields noted)
- **sessions**(id, campaign_id, started_at, ended_at, turn_range_start, turn_range_end, session_lore_json, summary, world_events_pending)
- **content_packs**(id, name, version, genre, layer, depends_on_json, path, license_json, installed_at)
- **pack_chunks**(id, pack_id, file_path, section_path, chunk_text, metadata_json, embedding_id)
- **scene_lore**(id, campaign_id, scene_id, session_id, lore_json, retrieved_at)
- Existing tables gain: `origin` (pack/campaign/world), `pack_id`, `pack_entity_id` fields

### Layer 3-forward schema decisions (applied now)
- All state tables carry `origin` and optional `pack_id` fields
- Entity IDs are namespaced: `pack_name:entity_id`, `campaign_id:entity_id`
- Engine events carry `scope` field (campaign/world_affecting)
- Fact visibility is a text field accepting extensible values (known, world, canonical, ...)
- Session records include `world_events_pending` for future world ticker

## Context packet builder

- Inputs: scene, present entities, active threads, clocks, recent facts, inventory, **scene lore cache (v1)**.
- Selection: prioritize present entities, recent events, thread-relevant facts, tagged items.
- Enrichment: NPC agendas, investigation progress, failure streaks, pending threats, active situations.
- Lore injection (v1): materialized scene lore added as dedicated sections in context packet.
- Caps: token or byte cap with deterministic ordering and truncation.
- Output: JSON packet with clear sections for the prompts.

## Prompt registry and versioning

- Prompts stored as files with ids and versions.
- Campaign pins interpreter/planner/narrator versions.
- Replay harness can override pins without altering state.
- v1: narrator prompt gains `{{lore_context}}` template section for scene lore.

## Flexibility and inspiration

- Stable state schema is the contract; prompts and validator rules are swappable.
- Orchestrator supports optional passes (planner on or off).
- LLM gateway supports multiple providers via adapter interface; initial adapter targets Claude.
- Content packs are modular — swap worlds without changing engine code.
- Pack layering allows incremental world-building (base + supplements + homebrew).

## Observability and metrics

- Every pass output stored in events table.
- Metrics: contradictions, invalid action acceptance, clarification rate, response length.
- Flagging tool records issues for later prompt tuning.
- v1: lore retrieval metrics — chunks retrieved per scene, relevance scores, cache hit rates.

## Deployment assumptions

- Local dev mode first; CLI-first for fast iteration with optional thin web UI later.
- SQLite for persistence; logs stored on disk.
- ChromaDB embedded (no server) for vector store.
- Content packs stored as local directories; distribution mechanism TBD.
