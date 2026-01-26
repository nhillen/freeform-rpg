# Freeform RPG Engine

An AI-driven narrative RPG engine that uses LLMs to create dynamic, responsive storytelling with strong continuity mechanics.

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
| [HLD.md](docs/HLD.md) | High-level design and architecture |
| [PRD.md](docs/PRD.md) | Product requirements |
| [TDD.md](docs/TDD.md) | Technical design details |
| [SESSION_ZERO_DESIGN.md](docs/SESSION_ZERO_DESIGN.md) | Game setup and calibration system |

## Architecture

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
