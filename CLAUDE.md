# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Freeform RPG Engine - an AI-driven narrative RPG with strong continuity mechanics, real consequences, and GM-like pacing. Chat-first, genre-flexible (v0 targets a cyberpunk noir case, 2-4 hours gameplay). Python 3, SQLite backend.

## Commands

```bash
# Initialize database
python -m src.cli.main --db game.db --campaign default init-db

# Execute one game turn
python -m src.cli.main --db game.db --campaign default run-turn --input "I approach the bartender"

# Inspect a specific turn's output
python -m src.cli.main --db game.db --campaign default show-event --turn 1 --field final_text

# Replay turn range (for A/B testing prompts)
python -m src.cli.main --db game.db --campaign default replay --start-turn 1 --end-turn 5
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

**State Model**: Append-only event log pattern. All state mutations go through `state_diff` structures. Events table is immutable audit trail.

**Key Directories:**
- `src/core/` - Turn orchestration pipeline
- `src/db/` - SQLite state store and schema
- `src/context/` - Context packet builder (what gets sent to LLM)
- `src/llm/` - LLM provider gateway
- `src/prompts/` - Versioned prompt templates (interpreter_v0.txt, etc.)
- `src/schemas/` - JSON schemas for all LLM inputs/outputs
- `src/eval/` - Replay harness for testing
- `docs/` - HLD, PRD, TDD, and GM reference materials

## Core Data Model

Eight SQLite tables: `entities`, `facts`, `scene`, `threads`, `clocks`, `inventory`, `relationships`, `events`, `summaries`. Schema in `src/db/schema.sql`.

**Clocks**: Heat, Time, Cred, Harm, Rep - each with value/max and trigger thresholds.

## Design Constraints

1. **LLM is narrator only** - Engine is authoritative; LLM narrates from validated facts
2. **Conservative defaults** - No hallucinated facts, default to safe/believable outcomes
3. **One-question max** - At most 1 clarification question per turn to avoid stalling
4. **Immutable state** - No destructive mutations; all changes via event log append
5. **Structured outputs** - All LLM responses must conform to JSON schemas

## Documentation

- `docs/PRD.md` - Product requirements and design principles
- `docs/HLD.md` - High-level architecture and data flow
- `docs/TDD.md` - Technical implementation details
- `docs/gm_reference/` - GM guidance for mechanics design (clocks, NPCs, scenes, etc.)
