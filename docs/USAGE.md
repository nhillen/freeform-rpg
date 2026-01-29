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

# Set up your API key (interactive)
freeform-rpg login
```

## Quick Start

The fastest way to start playing:

```bash
pip install -e .
freeform-rpg
```

Running `freeform-rpg` with no arguments launches a guided flow that:
1. Checks for an API key (prompts interactive login if missing)
2. Creates the game database automatically
3. Shows your saved games, or walks you through starting a new one
4. Drops you into the interactive play REPL

### Manual Setup (power users)

```bash
# Initialize a new game database
freeform-rpg init-db

# Start a new game with the included scenario
freeform-rpg new-game --scenario dead_drop

# Enter interactive play mode
freeform-rpg play
```

All subcommands also work via `python3 -m src.cli.main` if you haven't installed the package.

## Authentication

The engine requires an Anthropic API key to run. You can set this up in two ways:

### Interactive Login (Recommended)
```bash
freeform-rpg login
```

This will:
1. Prompt you for your API key
2. Validate it against the Anthropic API
3. Store it securely in `~/.config/freeform-rpg/config.json`

### Environment Variable
Alternatively, set the `ANTHROPIC_API_KEY` environment variable:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

The environment variable takes precedence over the stored config.

### Logout
To remove your stored API key:
```bash
freeform-rpg logout
```

## CLI Commands

### Authentication

| Command | Description |
|---------|-------------|
| `login` | Interactive API key setup |
| `logout` | Remove stored API key |

### Database & Game Setup

| Command | Description |
|---------|-------------|
| `init-db` | Initialize the SQLite schema |
| `new-game` | Start a new game |
| `list-scenarios` | List available scenarios |

#### new-game options
```bash
freeform-rpg new-game [OPTIONS]

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
freeform-rpg run-turn [OPTIONS]

--input, -i INPUT              # Player input text (required)
--prompt-versions VERSIONS     # JSON object, e.g. {"interpreter":"v1"}
--json                         # Output JSON instead of narrative
```

### Content Packs

| Command | Description |
|---------|-------------|
| `install-pack` | Install a content pack from a directory |
| `list-packs` | List installed content packs |
| `pack-ingest` | Convert a PDF sourcebook to a content pack (interactive) |
| `promote-draft` | Promote a draft pack to content_packs/ |
| `list-systems` | List available system extraction configs |

#### install-pack options
```bash
freeform-rpg install-pack PATH

PATH    # Path to content pack directory (must contain pack.yaml)
```

#### pack-ingest
Interactive guided flow that converts PDF sourcebooks into content packs:
1. Dependency check (pymupdf, optional pytesseract for OCR)
2. API key verification
3. PDF file selection
4. Pack metadata prompts (id, name, version, layer, author)
5. Options (OCR, image extraction, systems extraction)
6. Output directory selection
7. 8-stage pipeline execution with progress display
8. Validation and optional install

```bash
# Interactive mode
freeform-rpg pack-ingest

# Direct mode with system hint and draft output
freeform-rpg pack-ingest input.pdf \
  --system-hint world_of_darkness \
  --draft \
  -o output_dir/
```

**pack-ingest options:**
| Option | Description |
|--------|-------------|
| `--system-hint SYSTEM` | Use system-specific extraction patterns (e.g., `world_of_darkness`) |
| `--draft` | Output to draft mode with review markers |
| `-o, --output DIR` | Output directory |
| `--from-stage STAGE` | Resume from a specific stage |
| `--skip-systems` | Skip systems extraction phase |
| `--ocr` | Enable OCR for scanned PDFs |

#### promote-draft
Promote a reviewed draft pack to the content_packs/ directory:
```bash
freeform-rpg promote-draft draft/mage_traditions
```

#### list-systems
List available system extraction configurations:
```bash
freeform-rpg list-systems
```

See `docs/TDD.md` → "PDF Ingest Pipeline" and "System Extraction Configuration" for technical details.

### Evaluation & Debugging

| Command | Description |
|---------|-------------|
| `eval` | Show evaluation report for current game |
| `show-event` | Show a stored event by turn number |
| `replay` | Replay turns for A/B testing |

#### eval options
```bash
freeform-rpg eval [OPTIONS]

--json    # Output as JSON
```

#### show-event options
```bash
freeform-rpg show-event [OPTIONS]

--turn TURN           # Turn number to show (required)
--field FIELD         # Specific field to display (e.g., final_text, context_packet_json)
```

#### replay options
```bash
freeform-rpg replay [OPTIONS]

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
freeform-rpg init-db --db my_game.db
freeform-rpg --db my_game.db new-game --scenario dead_drop --preset noir_standard

# Play interactively
freeform-rpg --db my_game.db play

# Or run individual turns
freeform-rpg --db my_game.db run-turn -i "I examine the body carefully"
freeform-rpg --db my_game.db run-turn -i "I search his pockets"
```

## Content Packs

Content packs are sourcebook-scale world content (locations, NPCs, factions, history) that the engine retrieves via RAG during play.

### Installing Content Packs

```bash
# Install the included Undercity Sourcebook
freeform-rpg --db my_game.db install-pack content_packs/undercity_sourcebook

# List installed packs
freeform-rpg --db my_game.db list-packs
```

### Creating Content Packs from PDFs

The ingest pipeline converts existing PDF sourcebooks into content packs:

```bash
freeform-rpg pack-ingest
```

This launches an interactive flow that extracts text, detects structure, classifies content, and generates the pack directory.

### Authoring Content Packs

Content packs are directories with markdown files and YAML frontmatter:

```
my_pack/
  pack.yaml           # Manifest (id, name, version, description)
  locations/
    tavern.md         # Location with frontmatter
  npcs/
    bartender.md      # NPC with frontmatter
  factions/
    guild.md          # Faction with frontmatter
```

See `docs/TDD.md` → "Content pack authoring spec" for the full format.

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
freeform-rpg list-scenarios
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
freeform-rpg eval

# View specific event
freeform-rpg show-event 5
```

### A/B Testing Prompts

Use replay to test different prompt versions against the same inputs:

```bash
# Replay turns 1-5 with narrator v2
freeform-rpg replay --start-turn 1 --end-turn 5 --prompt-overrides '{"narrator":"v2"}'
```

## Troubleshooting

### "No module named src"
Make sure you've installed the package:
```bash
pip install -e .
```

### "No API key found" or authentication errors
Run the login command:
```bash
freeform-rpg login
```
Or set the environment variable:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Database Errors
Re-initialize the database:
```bash
freeform-rpg init-db --db game.db
```

### Test Failures
Ensure dev dependencies are installed:
```bash
pip install -e ".[dev]"
```
