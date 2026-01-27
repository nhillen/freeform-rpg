# PRD: Freeform RPG Engine

## Vision

A virtual Game Master that runs tabletop-style RPG sessions. The experience should feel like a prepared GM running a game night — with session structure, scene-based pacing, and deep world knowledge drawn from sourcebook-scale content packs. Not a chatbot, not a choose-your-own-adventure. A freeform narrative engine that mirrors traditional RPG and nightly game sessions.

Content packs are the GM's shelf of sourcebooks — large-scale authored worlds (hundreds of locations, NPCs, factions, histories) retrieved via RAG when the GM needs them. Multiple packs load simultaneously (core rules + setting guide + regional supplement + homebrew overlay), supporting both custom worlds and licensed game settings.

The long-term goal is shared evolving worlds where multiple groups play in the same setting and their collective actions change the baseline reality between sessions.

## Product goals

- **Feel like a good GM**: continuity, fair pushback, momentum, strong voice, session structure.
- **Deep worlds on demand**: sourcebook-scale content available through RAG retrieval, surfaced at session and scene boundaries — not every turn.
- **Content as product**: content packs are authorable, distributable, composable. Licensed game worlds can be packaged and sold. Custom worlds can be built and shared.
- **Fast iteration**: run and replay turns quickly, swap prompt versions, diff outputs.
- **Flexible direction**: keep a stable core while allowing inspiration-driven changes without losing progress.

## Non-goals (v0)

- Deep tactical combat.
- Large open world or travel simulation.
- Procedural city generation beyond authored locations.
- Fully autonomous self-modifying prompts.

## Design principles

- Consequences are real and tracked (clocks, inventory, location).
- Clarify rarely; default to conservative outcomes.
- Voice is consistent with the chosen setting.
- Engine is authoritative; LLM narrates from given facts only.
- Core state is stable while prompts and policies are swappable.
- Content packs are immutable; campaign play creates overlay state, never modifies pack content.
- All state tracks provenance (pack-authored vs campaign-emerged vs world-canonical).

## v0 scope (COMPLETE)

Single playable case in a compact setting. Cyberpunk noir, 2-4 hours gameplay.

- 3-5 locations, 6-10 NPCs, 3 factions.
- One main thread, 2-3 side threads.
- 10-20 key items and info objects.
- Full turn pipeline: interpret → validate → plan → resolve → narrate → commit.
- Clock mechanics: Heat, Time, Cred, Harm, Rep.
- 2d6 dice rolls with consequence escalation.
- Interactive CLI with guided setup, REPL, debug panel.
- Evaluation framework with A/B testing harness.
- One complete scenario (Dead Drop).

## v1 scope: Content packs and session lifecycle

**Content pack system:**
- Authored content packs in markdown + YAML frontmatter format.
- Directory structure: locations, NPCs, factions, culture, history, technology.
- Pack manifest with metadata, version, genre, dependencies, layer designation.
- Indexing pipeline: parse, chunk by section, extract metadata, build FTS5 + vector index.
- Hybrid retrieval: structured metadata filter → semantic ranking → token budget cap.
- ChromaDB for vector store (embedded, no server, persists to disk).

**Session lifecycle:**
- Sessions as first-class records grouping turns within a campaign.
- Session-start lore retrieval: campaign-level context, "previously on" summary.
- Scene-transition lore retrieval: location + present NPC + active thread lore cached per scene.
- Mid-scene incremental fetch only when narrator introduces new NPCs.
- Turn-level: no retrieval, reads from materialized scene lore cache.
- Session-end summary generation for next session's recap.

**Scene lore materialization:**
- Atmosphere/setting — serves narrator voice.
- NPC briefings — dispositions, knowledge, withheld info — serves interpreter and planner.
- Discoverable content — what can be found here — serves resolver.
- Thread connections — how this scene connects to active plots — serves planner tension moves.

## v2 scope: Multi-pack and licensed content

- Multiple packs loaded simultaneously with layering/priority model.
- Pack layers: core → setting → regional → adventure → homebrew (higher overrides lower).
- Cross-pack entity references via namespaced IDs.
- Unified index across all loaded packs with provenance metadata.
- Pack conflict resolution (same entity defined in multiple packs).
- Pack manifest with license metadata, publisher info, dependencies.
- Content authoring tooling and validation.

## v3 scope: Shared evolving worlds

- Multiple campaigns running in parallel in the same world.
- World-level state layer (shared canonical entities, facts, clocks, timeline) separate from campaign state.
- World ticker: between-session process that collects world-affecting events and extrapolates macro consequences.
- Event propagation: campaign events tagged as world-affecting get consumed by the ticker.
- Conflict resolution when campaigns produce contradictory world events.
- Emergent history as RAG content: auto-generated world history documents from play, served alongside authored pack content.
- World-canonical fact promotion: campaign-discovered facts can be promoted to shared world truth.

## Core mechanics

- Clocks: Heat, Time, Cred, Harm, Rep.
- Tags on entities and facts for retrieval.
- 2d6 dice rolls with banded outcomes (6- fail, 7-9 mixed, 10+ success).
- Hard constraints: inventory, presence, location, time.
- Loop: player input → interpret → validate → plan → resolve → narrate → commit.
- Content packs: RAG-retrieved world lore at session/scene boundaries.

## Target users

- Players who want narrative freedom with meaningful consequences in rich, authored worlds.
- Content creators who want to build and distribute world sourcebooks.
- Developers who need a fast iteration loop for prompts and rules.
- (Future) Groups who want persistent shared worlds that evolve across sessions.

## User stories

### Player
- As a player, I can attempt any action and get a believable outcome or pushback.
- As a player, I can rely on the game to remember people, places, and promises.
- As a player, I experience a world with depth — the GM knows the history, culture, and politics of the setting.
- As a player, starting a new session feels like returning to a game night — recap, scene-setting, then play.

### Content creator
- As a content creator, I can author a world sourcebook as markdown files with structured metadata.
- As a content creator, I can package and distribute my world as a content pack.
- As a content creator, I can define pack dependencies and layering so supplements build on base settings.

### Developer
- As a developer, I can replay a transcript with a new prompt and compare outputs.
- As a developer, I can see context packets, state diffs, and retrieved lore per turn.
- As a developer, I can test content packs by running scenarios against them and reviewing what lore surfaces.

## Functional requirements (v0 — complete)

- Turn orchestrator executes passes in order and logs all artifacts.
- State store (SQLite) is canonical and an append-only event log is kept.
- Context packet builder is entity/thread/clock aware and capped.
- LLM gateway uses structured outputs, validates schema, retries on errors.
- Prompt registry stores versioned prompt templates and pins per campaign.
- Validator enforces presence, location, inventory, and contradiction checks.
- Resolver applies clock deltas, rolls, and emits engine events.
- Narrator uses context + engine events only; introduces items/NPCs/facts that persist.
- Commit writes event record, applies state diff, updates summaries.
- Orchestrator supports swapping prompts and optional passes without breaking state.

## Functional requirements (v1 — content packs)

- Content pack loader parses markdown + YAML frontmatter directory structure.
- Indexer chunks content by section, extracts metadata, builds searchable index.
- Retriever supports hybrid query: metadata filter + semantic ranking + budget cap.
- Context builder integrates retrieved lore into context packet at scene boundaries.
- Session records track turn ranges, materialized lore cache, and end-of-session summaries.
- Scenarios reference content packs; loader resolves and indexes at campaign init.
- All entities and facts carry origin/provenance fields (pack, campaign, world).
- Entity IDs are namespaced to prevent collisions across packs and campaigns.
- Engine events carry scope tag (campaign, world_affecting) for future world ticker.

## Dev experience requirements

- Show context packet per turn.
- Show state diff per turn.
- Show retrieved lore chunks per scene (v1).
- Rerun last turn with prompt version X.
- Rerun last N turns.
- Flag output (too permissive, contradiction, boring, stalled).
- Prompt version list and per-campaign pinning.

## Data model (high level)

- entities, facts, scene, threads, clocks, inventory, relationships, events, campaigns, summaries.
- (v1) sessions, content_packs, pack_chunks, scene_lore.

## Metrics and success criteria

- After 60-120 turns: continuity errors are rare.
- Invalid actions get believable pushback or cost.
- Clocks create rising tension without feeling gamey.
- Voice remains consistent and scenes move forward.
- Dev loop: single-turn replay under a few seconds, with usable diffs.
- (v1) Retrieved lore is relevant to current scene >80% of the time.
- (v1) Session start/end feel like natural game night boundaries.

## Decisions

- Initial LLM provider: Claude via gateway adapter.
- UI form factor: CLI-first for fast iteration; thin web UI is optional later.
- Content pack format: markdown + YAML frontmatter (human-authorable, version-controllable).
- Vector store: ChromaDB (embedded, Python-native, no server dependency).
- Authored content over procedural generation: content packs are hand-crafted sourcebooks, not AI-generated filler. The engine retrieves and narrates from authored material.

## Risks and mitigations

- Hallucinated facts: enforce validator and narrator constraints, use schema validation.
- Stalling via clarifications: strict 1-question rule with conservative default.
- Slow iteration: cache context packets, keep replay lightweight, minimal UI.
- Overfitting to one prompt: prompt registry and replay harness to compare versions.
- Irrelevant lore retrieval: hybrid retrieval (structured + semantic), token budget cap, scene-boundary caching prevents mid-scene drift.
- Content pack scale: chunking strategy and budget caps keep context manageable regardless of pack size.
- Shared world conflicts: world ticker with editorial control, first-to-commit resolution, conflict detection.

## Resolved questions

- **Authored scenarios vs. full procedural generation**: Content packs are the answer. Authored world sourcebooks provide depth and quality. Scenarios define adventures within those worlds. The engine retrieves from authored content — it doesn't generate worlds from scratch. Content packs are distributable and composable, and can be built for licensed game settings.
