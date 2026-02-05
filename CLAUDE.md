# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Freeform RPG Engine - a virtual Game Master that runs tabletop-style RPG sessions. AI-driven narrative with strong continuity mechanics, real consequences, and GM-like pacing. Content packs provide sourcebook-scale world knowledge via RAG retrieval.

**Status**: v0 + v1 complete. See `docs/PRD.md` for detailed scope and roadmap.

## Commands

```bash
# Run the guided flow (recommended)
freeform-rpg

# Manual setup
freeform-rpg --db game.db --campaign default init-db
freeform-rpg --db game.db --campaign default new-game --scenario dead_drop
freeform-rpg --db game.db --campaign default play

# Content packs
freeform-rpg --db game.db install-pack content_packs/undercity_sourcebook
freeform-rpg --db game.db list-packs
freeform-rpg pack-ingest              # PDF → content pack (interactive)

# Dev tools
freeform-rpg --db game.db --campaign default show-event --turn 1 --field final_text
freeform-rpg --db game.db --campaign default replay --start-turn 1 --end-turn 5

# Tests
pytest
pytest --cov=src
```

See `docs/USAGE.md` for full CLI reference.

## Architecture

**Turn pipeline**: `Player Input → Interpreter → Validator → Planner → Resolver → Narrator → Commit`

**Content hierarchy**:
```
Content Pack (sourcebook-scale world content)
  └── Scenario (an adventure)
        └── Session (one game night)
              └── Scene (location/situation)
                    └── Turn (one player action)
```

See `docs/HLD.md` for full architecture details.

### Key Directories

- `src/core/` - Turn orchestration (orchestrator, validator, resolver)
- `src/db/` - SQLite state store and schema
- `src/context/` - Context packet builder
- `src/llm/` - LLM gateway and prompt registry
- `src/prompts/` - Versioned prompt templates
- `src/schemas/` - JSON schemas for LLM I/O
- `src/setup/` - Session zero, scenario loader, calibration
- `src/eval/` - Replay harness, metrics
- `src/content/` - Content pack loader, RAG retriever, lore indexer
- `src/ingest/` - PDF ingest pipeline (8 stages)
- `scenarios/` - Scenario YAML files
- `content_packs/` - Authored world sourcebooks

## Design Constraints

These constraints guide code generation and reviews:

1. **LLM is narrator only** - Engine is authoritative; LLM narrates from validated facts
2. **Conservative defaults** - No hallucinated facts, default to safe/believable outcomes
3. **One-question max** - At most 1 clarification question per turn
4. **Immutable state** - No destructive mutations; all changes via event log append
5. **Structured outputs** - All LLM responses must conform to JSON schemas
6. **Content pack immutability** - Campaign play never modifies pack content
7. **Provenance tracking** - All entities/facts track origin (pack, campaign, world)
8. **Namespaced IDs** - Entity IDs include pack/campaign namespace

See `docs/PRD.md` → "Design principles" and `docs/HLD.md` → "Layer 3-forward schema decisions" for rationale.

## Ingest Pipeline Philosophy

The PDF ingest pipeline uses **LLM-primary extraction**:

- **Heuristics pre-filter by STRUCTURE** (tables, rating scales, stat blocks) — not game-specific content
- **LLM extracts semantically** from filtered pages
- **No hardcoded game terminology** — patterns should work for any TTRPG

When adding extraction patterns to `src/ingest/systems_extract.py`:
- ✅ Detect structure: "table with numbers", "bulleted list with ratings"
- ❌ Don't detect content: "Strength, Dexterity" or "Bruised, Hurt, Wounded"

See `docs/TDD.md` → "Systems Extraction Philosophy" for full guidelines.
See `docs/BACKLOG.md` → "Ingest Pipeline — Technical Debt" for cleanup tasks.

## Documentation

- `docs/PRD.md` - Product requirements, vision, roadmap
- `docs/HLD.md` - High-level architecture and data flow
- `docs/TDD.md` - Technical implementation details, data types, schemas
- `docs/USAGE.md` - CLI commands and how to play
- `docs/BACKLOG.md` - Open issues, technical debt, planned improvements
- `docs/SESSION_ZERO_DESIGN.md` - Game setup and calibration
- `docs/PERCEPTION_DESIGN.md` - Perception and visibility model
- `docs/SYSTEM_ADAPTER_DESIGN.md` - Multi-system dice resolution
- `docs/gm_reference/` - GM guidance for mechanics design
