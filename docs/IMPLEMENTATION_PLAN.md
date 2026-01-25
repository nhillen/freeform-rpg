# Implementation Plan: Testability-First Build Order

## Current State Assessment

### What Exists (Scaffolding)
| Component | Status | Testable? |
|-----------|--------|-----------|
| Schema + State Store | Full CRUD | ✅ Yes - pure DB ops |
| Context Builder | Implemented | ✅ Yes - deterministic |
| Validator | Implemented | ✅ Yes - deterministic |
| Resolver | Implemented | ✅ Yes - deterministic (with seed) |
| LLM Gateway | Implemented | ✅ Yes - has MockGateway |
| Prompt Registry | Implemented | ✅ Yes - file loading |
| Orchestrator | **Stub only** | ❌ Not wired up |
| Session Zero | **Not built** | ❌ Doesn't exist |

### The Problem with Manual Scenarios
The `dead_drop.yaml` scenario is a shortcut that:
- Skips Session Zero (the generation path)
- Creates untested state (we assume the YAML is valid)
- Doesn't validate the full pipeline

### Dependency Graph

```
                    ┌─────────────────┐
                    │   Session Zero  │ (generates initial state)
                    └────────┬────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      Turn Pipeline                          │
│  ┌──────────┐   ┌───────────┐   ┌─────────┐   ┌──────────┐ │
│  │Interpreter│ → │ Validator │ → │ Planner │ → │ Resolver │ │
│  │  (LLM)   │   │ (Engine)  │   │  (LLM)  │   │ (Engine) │ │
│  └──────────┘   └───────────┘   └─────────┘   └──────────┘ │
│                                       │                     │
│                                       ▼                     │
│                               ┌──────────┐                  │
│                               │ Narrator │                  │
│                               │  (LLM)   │                  │
│                               └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   State Store   │ (commits changes)
                    └─────────────────┘
```

**Key Insight:** Engine components (Validator, Resolver) are deterministic. LLM components have variability. Test engine first, then LLM integration.

---

## Testability Layers

### Layer 0: Pure Functions (No Dependencies)
- Dice rolling with seeded RNG
- Cost calculation
- State diff merging
- JSON schema validation

### Layer 1: Database Operations
- State store CRUD
- In-memory SQLite for tests
- No external dependencies

### Layer 2: Engine Components (State Store + Logic)
- Context Builder: state → context packet
- Validator: interpreter output + state → validation result
- Resolver: validator output → state diff + events

**Test strategy:** Create minimal fixtures (not full scenarios), verify outputs

### Layer 3: LLM Integration (Mock First)
- Prompt rendering
- Schema validation of LLM output
- MockGateway with canned responses

**Test strategy:** Verify prompts render correctly, outputs parse correctly

### Layer 4: Full Pipeline (Orchestrator)
- Wire all components together
- Test with MockGateway end-to-end
- Then test with real LLM

### Layer 5: Session Zero (Dynamic Generation)
- Template + questions → state
- Uses LLM for generation
- Validates generated state

---

## Implementation Order

### Phase 1: Test Infrastructure
**Goal:** Set up pytest, fixtures, test database pattern

```
tests/
├── conftest.py          # Shared fixtures
├── fixtures/            # Test data (NOT scenarios)
│   ├── entities.py      # Factory functions for test entities
│   ├── facts.py         # Factory functions for test facts
│   └── contexts.py      # Pre-built context packets
├── unit/                # Pure function tests
├── integration/         # Component integration tests
└── e2e/                 # End-to-end tests
```

**Deliverables:**
- [ ] pytest configuration
- [ ] In-memory SQLite fixture
- [ ] Entity/fact factory functions
- [ ] Context packet builders for tests

**Why first:** Everything else needs test infrastructure

### Phase 2: State Store Tests
**Goal:** Verify all CRUD operations work correctly

**Tests:**
- [ ] Create/read/update/delete for each table
- [ ] `apply_state_diff()` correctly updates state
- [ ] Clock triggers fire at correct thresholds
- [ ] Perception queries (known facts, visible entities)

**Why second:** State store is foundation for everything

### Phase 3: Engine Component Tests
**Goal:** Test deterministic components in isolation

**Context Builder tests:**
- [ ] Empty state → minimal valid packet
- [ ] Perception filtering (obscured entities excluded)
- [ ] Known facts only (world facts excluded)
- [ ] Calibration injection

**Validator tests:**
- [ ] Valid action passes
- [ ] Unknown entity blocked
- [ ] Entity not in scene blocked
- [ ] Missing inventory blocked
- [ ] Contradiction detected
- [ ] Costs calculated correctly
- [ ] Perception flags handled

**Resolver tests:**
- [ ] Success outcome with seeded roll
- [ ] Mixed outcome with seeded roll
- [ ] Failure outcome with seeded roll
- [ ] Costs applied to clocks
- [ ] State diff generated correctly
- [ ] Tension move applied

**Why third:** These are deterministic, can be fully tested without LLM

### Phase 4: LLM Integration Tests (Mock)
**Goal:** Test prompt rendering and output parsing without real LLM

**Tests:**
- [ ] Prompt templates render with context data
- [ ] MockGateway returns configured responses
- [ ] Output validates against schema
- [ ] Invalid output triggers retry

**Interpreter mock tests:**
- [ ] Given context + input, returns valid InterpreterOutput
- [ ] Perception flags populated for unknown entities

**Planner mock tests:**
- [ ] Given context + validator output, returns valid PlannerOutput
- [ ] Clarification handling (validator takes precedence)

**Narrator mock tests:**
- [ ] Given context + events + planner output, returns valid NarratorOutput
- [ ] final_text is non-empty

**Why fourth:** Validates the LLM interface before using real LLM

### Phase 5: Orchestrator Integration
**Goal:** Wire all components, test full turn with mocks

**Refactor orchestrator to:**
- [ ] Use real Context Builder (not stub)
- [ ] Call LLM for Interpreter
- [ ] Use real Validator
- [ ] Call LLM for Planner
- [ ] Use real Resolver
- [ ] Call LLM for Narrator
- [ ] Apply state diff
- [ ] Record event

**Tests:**
- [ ] Full turn with MockGateway
- [ ] State correctly updated after turn
- [ ] Event correctly recorded
- [ ] Multiple turns in sequence

**Why fifth:** Orchestrator is integration point

### Phase 6: Session Zero Implementation
**Goal:** Dynamic state generation from templates + player input

**Components:**
- [ ] Scenario template schema (structure without content)
- [ ] Character question flow
- [ ] NPC generation from roles
- [ ] Fact/clue distribution
- [ ] State initialization

**Tests:**
- [ ] Template loads and validates
- [ ] Character questions → character entity
- [ ] NPC roles → NPC entities with relationships
- [ ] Generated state passes validation
- [ ] All revelations have 3+ clues (Three Clue Rule)

**Why sixth:** Now we can generate test data dynamically instead of hardcoding

### Phase 7: Real LLM Integration
**Goal:** Test with actual Claude API

**Tests:**
- [ ] Single turn with real LLM
- [ ] Output conforms to schema
- [ ] Generated content is coherent
- [ ] Multiple turns maintain consistency

**Evaluation criteria:**
- [ ] No hallucinated entities
- [ ] Stays in POV
- [ ] Costs/consequences applied correctly

**Why seventh:** Real LLM is the final integration step

### Phase 8: Replay & Regression
**Goal:** Record sessions for regression testing

**Components:**
- [ ] Session recording (inputs + outputs)
- [ ] Replay with different prompt versions
- [ ] Diff comparison for regression detection
- [ ] Metrics calculation

**Why last:** Requires everything else to work

---

## Fixture Strategy (Replacing Manual Scenarios)

Instead of `dead_drop.yaml` as a scenario, create **test fixtures**:

```python
# tests/fixtures/entities.py

def make_player(name="Kira", **overrides):
    """Factory for player entity."""
    return {
        "id": "player",
        "type": "pc",
        "name": name,
        "attrs": {"background": "test character", **overrides.get("attrs", {})},
        "tags": ["player"]
    }

def make_npc(id, name, role="generic", **overrides):
    """Factory for NPC entity."""
    return {
        "id": id,
        "type": "npc",
        "name": name,
        "attrs": {"role": role, **overrides.get("attrs", {})},
        "tags": overrides.get("tags", [])
    }

def make_location(id, name, **overrides):
    """Factory for location entity."""
    return {
        "id": id,
        "type": "location",
        "name": name,
        "attrs": {"description": f"A {name}", **overrides.get("attrs", {})},
        "tags": overrides.get("tags", [])
    }
```

```python
# tests/fixtures/contexts.py

def minimal_context(player_name="Test Player"):
    """Minimal valid context packet for testing."""
    return {
        "scene": {"location_id": "test_loc", "time": {}, "constraints": {}},
        "present_entities": ["player"],
        "entities": [make_player(player_name)],
        "facts": [],
        "threads": [],
        "clocks": [],
        "inventory": [],
        "summary": {"scene": "", "threads": ""},
        "recent_events": [],
        "calibration": {"tone": {}, "themes": {}, "risk": {}},
        "genre_rules": {}
    }

def combat_context():
    """Context with player and hostile NPC for combat testing."""
    return {
        **minimal_context(),
        "present_entities": ["player", "hostile_npc"],
        "entities": [
            make_player(),
            make_npc("hostile_npc", "Goon", role="enemy", tags=["hostile"])
        ]
    }
```

**Benefits:**
- Composable - build exactly the state you need for each test
- Explicit - test knows exactly what's in the fixture
- No hidden assumptions - unlike YAML that might have subtle dependencies

---

## What Happens to dead_drop.yaml?

**Option A: Delete it**
It's scaffolding that served its purpose. Tests use fixtures instead.

**Option B: Convert to template**
Strip out specific content, keep structure:
```yaml
# templates/noir_investigation.yaml
id: noir_investigation
name: "Noir Investigation Template"
structure:
  required_roles: ["victim", "suspect", "ally", "threat"]
  required_clocks: ["heat", "time", "harm"]
  revelation_count: {min: 3, max: 7}
  # ... structure, not content
```

**Option C: Keep as smoke test**
One golden scenario that validates "the whole thing works" after all unit/integration tests pass.

**Recommendation:** Option B + C. Convert to template for Session Zero, keep one instance as smoke test.

---

## Immediate Next Steps

1. **Create test infrastructure** (Phase 1)
   - `tests/conftest.py` with DB fixture
   - `tests/fixtures/` with factory functions

2. **Write State Store tests** (Phase 2)
   - Validates the foundation works

3. **Write Engine Component tests** (Phase 3)
   - Context Builder, Validator, Resolver
   - Uses fixtures, no LLM needed

4. **Refactor Orchestrator** (Phase 5, partial)
   - Wire up real components
   - Keep MockGateway for now

5. **Decide on dead_drop.yaml fate**
   - Convert to template or delete

This order means we're always testing what we just built, and each layer validates the layer below it.
