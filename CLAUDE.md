# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Freeform RPG Engine - a virtual Game Master that runs tabletop-style RPG sessions. AI-driven narrative with strong continuity mechanics, real consequences, and GM-like pacing. The experience should feel like a prepared GM running a game night, not a chatbot — with session structure, scene-based pacing, and deep world knowledge drawn from content packs.

Genre-flexible (v0 targets a cyberpunk noir case, 2-4 hours gameplay). Python 3, SQLite backend. Content packs provide large-scale world-building (sourcebook-equivalent) via RAG retrieval.

## Development Status

**v0 core: complete.** All pipeline stages implemented and working. No stubs or TODOs.

- Full 7-stage turn pipeline (Interpreter → Validator → Planner → Resolver → Narrator → Commit)
- SQLite state store with append-only event log
- 2d6 dice mechanics with consequence escalation and failure streaks
- Clock system (Heat, Time, Harm, Cred, Rep) with configurable triggers
- NPC escalation profiles and threat resolution
- Narrator-declared facts, items, NPCs, scene transitions
- Interactive CLI with guided setup, REPL, debug panel
- Evaluation framework with A/B testing harness
- Content pack system (RAG-based world sourcebooks via FTS5 + optional ChromaDB)
- Session lifecycle management
- Entity lore manifest (pre-computed entity→chunk mapping at scenario load)
- Cache-aware lore retrieval (skip re-fetch on revisits)
- One complete scenario (Dead Drop) + one setting sourcebook (Undercity Sourcebook)

## Commands

```bash
# Run the guided flow (handles API key, scenario, game setup)
freeform-rpg

# Or manual setup
freeform-rpg --db game.db --campaign default init-db
freeform-rpg --db game.db --campaign default new-game --scenario dead_drop
freeform-rpg --db game.db --campaign default play

# Content packs
freeform-rpg --db game.db install-pack content_packs/undercity_sourcebook
freeform-rpg --db game.db list-packs

# Dev tools
freeform-rpg --db game.db --campaign default show-event --turn 1 --field final_text
freeform-rpg --db game.db --campaign default replay --start-turn 1 --end-turn 5

# Tests
pytest
pytest --cov=src
```

## Architecture

**Multi-pass LLM Pipeline per turn:**
```
Player Input → Interpreter → Validator → Planner → Resolver → Narrator → Commit
```

- **Interpreter**: Maps player intent to proposed actions
- **Validator**: Enforces presence/location/inventory/contradiction rules, calculates costs
- **Planner**: Outlines narrative beats and tension moves
- **Resolver**: Executes actions, updates clocks, emits engine events
- **Narrator**: Produces final prose from validated context only

**Content hierarchy:**
```
Content Pack (the world — large, static, authored sourcebook)
  └── Scenario (an adventure — entities, clocks, threads, mechanical state)
        └── Session (one game night of play)
              └── Scene (a location/situation)
                    └── Turn (one player action)
```

**State Model**: Append-only event log pattern. All state mutations go through `state_diff` structures. Events table is immutable audit trail. Content packs are always immutable — campaign play creates overlay state, never modifies pack content.

**Key Directories:**
- `src/core/` - Turn orchestration pipeline (orchestrator, validator, resolver)
- `src/db/` - SQLite state store and schema
- `src/context/` - Context packet builder (what gets sent to LLM)
- `src/llm/` - LLM provider gateway and prompt registry
- `src/prompts/` - Versioned prompt templates (interpreter_v0.txt, etc.)
- `src/schemas/` - JSON schemas for all LLM inputs/outputs
- `src/setup/` - Session zero pipeline, scenario loader, calibration
- `src/eval/` - Replay harness, evaluation metrics, snapshots
- `src/content/` - Content pack loader, chunker, lore indexer, RAG retriever, scene cache
- `scenarios/` - Scenario YAML files
- `content_packs/` - Authored world sourcebooks for RAG retrieval
- `docs/` - HLD, PRD, TDD, and GM reference materials

## Core Data Model

SQLite tables: `entities`, `facts`, `scene`, `threads`, `clocks`, `inventory`, `relationships`, `events`, `campaigns`, `summaries`. Schema in `src/db/schema.sql`.

**v1 tables (schema_v1.sql):** `sessions`, `content_packs`, `pack_chunks`, `pack_chunks_fts` (FTS5), `scene_lore`. Provenance columns (`origin`, `pack_id`) added to entities, facts, threads, clocks, relationships. Campaign-level `pack_ids_json` and `lore_manifest_json` columns.

**Clocks**: Heat, Time, Cred, Harm, Rep - each with value/max and trigger thresholds.

## Design Constraints

1. **LLM is narrator only** - Engine is authoritative; LLM narrates from validated facts
2. **Conservative defaults** - No hallucinated facts, default to safe/believable outcomes
3. **One-question max** - At most 1 clarification question per turn to avoid stalling
4. **Immutable state** - No destructive mutations; all changes via event log append
5. **Structured outputs** - All LLM responses must conform to JSON schemas
6. **Content pack immutability** - Campaign play never modifies pack content; all play-generated state is overlay
7. **Provenance tracking** - All entities, facts, and events track their origin (pack, campaign, or world)
8. **Namespaced IDs** - Entity IDs include pack/campaign namespace to prevent collisions across shared content

## Layer 3-Forward Design (future: shared evolving worlds)

These constraints apply now to avoid costly retrofits when multi-campaign shared worlds are built:

- **Origin fields on all state**: entities, facts, events carry `origin` (pack/campaign/world) and optional `pack_id`
- **Event scope tagging**: engine events carry `scope` (campaign/world_affecting) for future world ticker consumption
- **Fact visibility is extensible**: don't hardcode to known/world — future values include `canonical` (shared world truth)
- **Sessions are first-class**: session records group turns and store materialized lore caches
- **Pack entities are seeded copies**: scenarios copy pack entities into campaign state with back-references, allowing divergence

## Documentation

- `docs/PRD.md` - Product requirements, vision, and roadmap
- `docs/HLD.md` - High-level architecture and data flow
- `docs/TDD.md` - Technical implementation details
- `docs/SESSION_ZERO_DESIGN.md` - Game setup and calibration system
- `docs/PERCEPTION_DESIGN.md` - Perception and information visibility model
- `docs/USAGE.md` - CLI commands and how to play
- `docs/gm_reference/` - GM guidance for mechanics design (clocks, NPCs, scenes, etc.)
