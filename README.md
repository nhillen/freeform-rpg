# Freeform RPG Engine

A virtual Game Master that runs tabletop-style RPG sessions with AI-driven narrative, real consequences, and deep world knowledge.

## Vision

Freeform RPG recreates the experience of a prepared GM running a game night. Not a chatbot — a game engine that understands session structure, scene-based pacing, and world lore at sourcebook depth. The GM preps before the session, sets the stage when a scene opens, and runs the table from memory during play.

**Content packs** are the GM's sourcebooks — large-scale authored world content (locations, NPCs, factions, history, culture, technology) retrieved via RAG at session and scene boundaries. Multiple packs can be loaded simultaneously (core rules + setting + supplement + homebrew overlay), supporting both custom worlds and licensed game settings.

The long-term goal is **shared evolving worlds** where multiple groups play in the same setting and their collective actions change the baseline reality between sessions.

## Overview

Freeform RPG is a text-based RPG engine where an AI Game Master responds to freeform player input. The engine tracks world state through an append-only event log, enforces narrative consistency through a multi-pass pipeline, and uses 2d6 dice mechanics for uncertain outcomes.

**Key Features:**
- Freeform text input — describe what you want to do in plain English
- Persistent world state with entities, facts, relationships, and narrator-established details
- Clock-based tension mechanics (Heat, Time, Harm, Cred, Rep)
- 2d6 dice rolls for risky actions, with visible outcomes
- Multi-pass LLM pipeline (Interpreter → Validator → Planner → Resolver → Narrator)
- Guided setup flow with scenario selection and character introduction
- Narrative yes-and: the narrator can introduce items and facts that persist to game state

## Status

**v0 core: complete.** All pipeline stages implemented and working (~8,300 lines production Python, ~4,300 lines tests). One playable scenario (Dead Drop — cyberpunk noir, 2-4 hours).

**Roadmap:**
- **v1** — Content pack system (RAG-based world sourcebooks) and session lifecycle
- **v2** — Multi-pack support, licensed content format, pack layering
- **v3** — Shared evolving worlds (multi-campaign, world ticker, event propagation)

## Quick Start

```bash
# Set up virtual environment and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Run the guided flow (handles API key, scenario, and game setup)
freeform-rpg
```

The guided flow will walk you through API key setup, scenario selection, and character introduction. Once in the game, type your actions in plain English.

### REPL Commands

While playing, these commands are available:

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/status` | Show character status (harm, cred) |
| `/clocks` | Show all clocks |
| `/scene` | Show current scene info |
| `/inventory` | Show inventory |
| `/debug` | Toggle debug panel (pipeline internals, dice rolls, timing) |
| `/quit` | Exit the game |

### Fresh Start

To clear your game state and start over:

```bash
# Remove existing database
rm -f game.db

# Set your API key (if not using the guided login flow)
export ANTHROPIC_API_KEY="your-key-here"

# Option 1: Guided flow (handles everything)
freeform-rpg

# Option 2: Manual setup
freeform-rpg --db game.db --campaign default new-game --scenario dead_drop
freeform-rpg --db game.db --campaign default play
```

### Direct CLI

For advanced use or scripting:

```bash
freeform-rpg --db game.db --campaign default init-db
freeform-rpg --db game.db --campaign default new-game --scenario dead_drop
freeform-rpg --db game.db --campaign default play
freeform-rpg --db game.db --campaign default show-event --turn 1 --field final_text
```

## Documentation

| Document | Description |
|----------|-------------|
| [USAGE.md](docs/USAGE.md) | CLI commands, testing, and how to play |
| [PRD.md](docs/PRD.md) | Product requirements, vision, and roadmap |
| [HLD.md](docs/HLD.md) | High-level architecture and data flow |
| [TDD.md](docs/TDD.md) | Technical design details |
| [SESSION_ZERO_DESIGN.md](docs/SESSION_ZERO_DESIGN.md) | Game setup and calibration system |
| [PERCEPTION_DESIGN.md](docs/PERCEPTION_DESIGN.md) | Perception and information visibility model |

## Architecture

**Content hierarchy:**
```
Content Pack (the world — sourcebook-scale authored content, retrieved via RAG)
  └── Scenario (an adventure — entities, clocks, threads, mechanical state)
        └── Session (one game night of play)
              └── Scene (a location/situation, lore cached at boundary)
                    └── Turn (one player action)
```

**Turn pipeline:**
```
Player Input
     ↓
┌─────────────┐
│ Interpreter │ → Parse intent, identify entities
└─────────────┘
     ↓
┌─────────────┐
│  Validator  │ → Check against world state
└─────────────┘
     ↓
┌─────────────┐
│   Planner   │ → Determine consequences, select GM moves
└─────────────┘
     ↓
┌─────────────┐
│  Resolver   │ → Compute state changes
└─────────────┘
     ↓
┌─────────────┐
│  Narrator   │ → Generate prose output
└─────────────┘
     ↓
┌─────────────┐
│   Commit    │ → Persist to event log
└─────────────┘
```

## Development

```bash
# Set up environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# With coverage
pytest --cov=src

# Source changes take effect immediately (editable install)
# No need to reinstall after modifying Python files
```

## License

MIT
