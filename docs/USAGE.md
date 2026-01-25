# Freeform RPG Engine - Usage Guide

## Installation

### Requirements
- Python 3.11+
- Anthropic API key

### Setup

```bash
# Clone the repository
git clone https://github.com/nhillen/freeform-rpg.git
cd freeform-rpg

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .

# For development (includes pytest)
pip install -e ".[dev]"

# Set your API key
export ANTHROPIC_API_KEY="your-key-here"
```

## Quick Start

```bash
# Initialize a new game database
python3 -m src.cli.main init-db

# Start a new game with the included scenario
python3 -m src.cli.main new-game --scenario dead_drop

# Enter interactive play mode
python3 -m src.cli.main play
```

## CLI Commands

### Database & Game Setup

| Command | Description |
|---------|-------------|
| `init-db` | Initialize the SQLite schema |
| `new-game` | Start a new game |
| `list-scenarios` | List available scenarios |

#### new-game options
```bash
python3 -m src.cli.main new-game [OPTIONS]

--scenario SCENARIO    # Scenario file to load (e.g., dead_drop)
--template TEMPLATE    # Template to use if no scenario specified
--preset PRESET        # Calibration preset: noir_standard, pulp_adventure, hard_boiled
--interactive, -i      # Interactive character creation
```

### Playing

| Command | Description |
|---------|-------------|
| `play` | Interactive play mode (recommended) |
| `run-turn` | Execute a single turn programmatically |

#### run-turn options
```bash
python3 -m src.cli.main run-turn [OPTIONS]

--input, -i INPUT              # Player input text (required)
--prompt-versions VERSIONS     # JSON object, e.g. {"interpreter":"v1"}
--json                         # Output JSON instead of narrative
```

### Evaluation & Debugging

| Command | Description |
|---------|-------------|
| `eval` | Show evaluation report for current game |
| `show-event` | Show a stored event by ID |
| `replay` | Replay turns for A/B testing |

#### eval options
```bash
python3 -m src.cli.main eval [OPTIONS]

--json    # Output as JSON
```

#### replay options
```bash
python3 -m src.cli.main replay [OPTIONS]

--start-turn START    # First turn to replay (required)
--end-turn END        # Last turn to replay (required)
--prompt-overrides    # JSON object, e.g. {"narrator":"v2"}
```

### Global Options

These options apply to all commands:

```bash
--db DB              # SQLite database path (default: game.db)
--campaign CAMPAIGN  # Campaign ID (default: default)
```

## Example Session

```bash
# Start fresh
python3 -m src.cli.main init-db --db my_game.db
python3 -m src.cli.main --db my_game.db new-game --scenario dead_drop --preset noir_standard

# Play interactively
python3 -m src.cli.main --db my_game.db play

# Or run individual turns
python3 -m src.cli.main --db my_game.db run-turn -i "I examine the body carefully"
python3 -m src.cli.main --db my_game.db run-turn -i "I search his pockets"
```

## Testing

### Run All Tests
```bash
pytest
```

### Run with Coverage
```bash
pytest --cov=src --cov-report=term-missing
```

### Run Specific Test Categories
```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_state_store.py

# Specific test
pytest tests/unit/test_state_store.py::TestStateStore::test_add_entity
```

### Test Structure
```
tests/
├── conftest.py              # Shared fixtures
├── fixtures/                # Test data factories
│   ├── contexts.py          # Context builder fixtures
│   ├── entities.py          # Entity fixtures
│   ├── facts.py             # Fact fixtures
│   └── state.py             # State fixtures
├── unit/                    # Unit tests
│   ├── test_context_builder.py
│   ├── test_orchestrator.py
│   ├── test_resolver.py
│   ├── test_snapshots.py
│   ├── test_state_store.py
│   └── test_validator.py
└── integration/             # Integration tests
    └── test_full_pipeline.py
```

## Scenarios

Scenarios are YAML files in the `scenarios/` directory that define:
- Setting and genre
- Initial NPCs and locations
- Starting facts and threads
- Clocks and calibration

### List Available Scenarios
```bash
python3 -m src.cli.main list-scenarios
```

### Current Scenarios
- **dead_drop**: A cyberpunk noir investigation. A simple courier job goes wrong when you find your contact dead.

## Calibration Presets

Presets control the tone and difficulty of the game:

| Preset | Description |
|--------|-------------|
| `noir_standard` | Classic noir - gritty, morally ambiguous |
| `pulp_adventure` | Lighter tone, more action-oriented |
| `hard_boiled` | Maximum grit, consequences hit hard |

## Development Workflow

### Running the Engine Manually

For debugging, you can run individual pipeline stages:

```python
from src.db.state_store import StateStore
from src.core.orchestrator import Orchestrator

store = StateStore("game.db")
orchestrator = Orchestrator(store)
result = orchestrator.process_turn("I search the room")
```

### Viewing Game State

```bash
# Check current evaluation metrics
python3 -m src.cli.main eval

# View specific event
python3 -m src.cli.main show-event 5
```

### A/B Testing Prompts

Use replay to test different prompt versions against the same inputs:

```bash
# Replay turns 1-5 with narrator v2
python3 -m src.cli.main replay --start-turn 1 --end-turn 5 --prompt-overrides '{"narrator":"v2"}'
```

## Troubleshooting

### "No module named src"
Make sure you've installed the package:
```bash
pip install -e .
```

### "ANTHROPIC_API_KEY not set"
Export your API key:
```bash
export ANTHROPIC_API_KEY="your-key-here"
```

### Database Errors
Re-initialize the database:
```bash
python3 -m src.cli.main init-db --db game.db
```

### Test Failures
Ensure dev dependencies are installed:
```bash
pip install -e ".[dev]"
```
