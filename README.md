# Freeform RPG Engine

An AI-driven narrative RPG engine that uses LLMs to create dynamic, responsive storytelling with strong continuity mechanics.

## Overview

Freeform RPG is a text-based RPG engine where an AI Game Master responds to freeform player input. Unlike traditional RPGs with dice rolls and stat sheets, this engine focuses on narrative consequences tracked through an append-only event log.

**Key Features:**
- Freeform text input (no commands or menus)
- Persistent world state with entities, facts, and relationships
- Clock-based tension mechanics (Heat, Time, Harm, etc.)
- Multi-pass LLM pipeline ensuring consistency
- Scenario-based adventures with customizable tone

## Quick Start

```bash
# Install
pip install -e .
export ANTHROPIC_API_KEY="your-key"

# Initialize and start a game
python3 -m src.cli.main init-db
python3 -m src.cli.main new-game --scenario dead_drop
python3 -m src.cli.main play
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

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# With coverage
pytest --cov=src
```

## License

MIT
