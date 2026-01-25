# Final Consistency Audit: Ready to Build

Comprehensive audit of all documentation, architecture, and implementation scaffolding.

**Audit Date:** 2025-01-25
**Auditor:** Claude
**Status:** READY TO BUILD (with noted issues)

---

## Executive Summary

The architecture is **internally consistent** and **ready for implementation**. The core pipeline design (PRD → HLD → TDD → Schemas → Code stubs) aligns well. However, there are:

- **3 schema extensions needed** (from design docs not yet in TDD)
- **2 missing tables** (from design docs)
- **5 prompt enhancements needed** (from GM reference)
- **1 new pipeline phase** (Session Zero setup)

None of these block starting implementation—they can be added incrementally.

---

## Document Inventory Audited

### Core Architecture
- [x] `docs/PRD.md` - Product requirements
- [x] `docs/HLD.md` - High-level design
- [x] `docs/TDD.md` - Technical design

### Design Extensions
- [x] `docs/SESSION_ZERO_DESIGN.md` - Setup pipeline + calibration
- [x] `docs/COMPETITIVE_ANALYSIS.md` - Competitive analysis + gaps
- [x] `docs/gm_reference/PERCEPTION_DESIGN.md` - Perception system

### Implementation
- [x] `src/db/schema.sql` - Database schema
- [x] `src/schemas/*.json` - JSON schemas (6 files)
- [x] `src/prompts/*.txt` - Prompt templates (3 files)
- [x] `src/core/orchestrator.py` - Orchestrator stub
- [x] `src/db/state_store.py` - State store stub
- [x] `src/context/builder.py` - Context builder stub

---

## Consistency Check: PRD ↔ HLD ↔ TDD

### Pipeline Stages

| Stage | PRD | HLD | TDD | Schema | Code | Status |
|-------|-----|-----|-----|--------|------|--------|
| Context Builder | ✓ | ✓ | ✓ | ✓ | stub | **OK** |
| Interpreter | ✓ | ✓ | ✓ | ✓ | stub | **OK** |
| Validator | ✓ | ✓ | ✓ | ✓ | stub | **OK** |
| Planner | ✓ | ✓ | ✓ | ✓ | stub | **OK** |
| Resolver | ✓ | ✓ | ✓ | partial | stub | **OK** |
| Narrator | ✓ | ✓ | ✓ | ✓ | stub | **OK** |
| Commit | ✓ | ✓ | ✓ | ✓ | stub | **OK** |

### Data Model

| Table | PRD | HLD | TDD | schema.sql | Status |
|-------|-----|-----|-----|------------|--------|
| entities | ✓ | ✓ | ✓ | ✓ | **OK** |
| facts | ✓ | ✓ | ✓ | ✓ | **OK** |
| scene | ✓ | ✓ | ✓ | ✓ | **OK** |
| threads | ✓ | ✓ | ✓ | ✓ | **OK** |
| clocks | ✓ | ✓ | ✓ | ✓ | **OK** |
| inventory | ✓ | ✓ | ✓ | ✓ | **OK** |
| relationships | ✓ | ✓ | ✓ | ✓ | **OK** |
| events | ✓ | ✓ | ✓ | ✓ | **OK** |
| summaries | ✓ | ✓ | ✓ | ✓ | **OK** |

### Clocks

| Clock | PRD | HLD | TDD Schema | Status |
|-------|-----|-----|------------|--------|
| Heat | ✓ | - | ✓ (costs.heat) | **OK** |
| Time | ✓ | - | ✓ (costs.time) | **OK** |
| Cred | ✓ | - | ✓ (costs.cred) | **OK** |
| Harm | ✓ | - | ✓ (costs.harm) | **OK** |
| Rep | ✓ | - | ✓ (costs.rep) | **OK** |

**Note:** PRD mentions 5 clocks. TDD ValidatorOutput.costs has all 5. Consistent.

---

## Consistency Check: Design Docs ↔ Core Architecture

### SESSION_ZERO_DESIGN.md

| Feature | In SESSION_ZERO | In TDD/Schema | Status |
|---------|-----------------|---------------|--------|
| Calibration settings | ✓ (detailed YAML) | ✗ | **NEEDS ADDITION** |
| Game System module | ✓ (detailed YAML) | ✗ | **NEEDS ADDITION** |
| Setup Pipeline | ✓ (8 phases) | ✗ | **NEEDS ADDITION** |
| Character questions | ✓ (7 questions) | ✗ | **NEEDS ADDITION** |
| Scenario templates | ✓ (YAML format) | ✗ | **NEEDS ADDITION** |

**Impact:** Session Zero is a **separate pipeline** that runs before the turn pipeline. It needs:
- New `calibration` table or config storage
- New `game_systems` directory with YAML configs
- New `scenarios` directory with templates
- New `SetupPipeline` module

**Recommendation:** Add as Phase 2 of implementation. Turn pipeline can work with manually created initial state for Phase 1.

### PERCEPTION_DESIGN.md

| Feature | In PERCEPTION | In TDD/Schema | Status |
|---------|---------------|---------------|--------|
| visibility field on facts | ✓ | ✓ (in schema.sql) | **OK** |
| discovered_turn on facts | ✓ | ✗ | **NEEDS ADDITION** |
| discovery_method on facts | ✓ | ✗ | **NEEDS ADDITION** |
| visibility_conditions on scene | ✓ | ✗ | **NEEDS ADDITION** |
| noise_level on scene | ✓ | ✗ | **NEEDS ADDITION** |
| obscured_entities on scene | ✓ | ✗ | **NEEDS ADDITION** |
| perception_flags in Interpreter | ✓ | ✗ | **NEEDS ADDITION** |

**Impact:** Perception is a **v0 feature** per the design doc. Needs schema updates.

**Recommendation:** Add to schema.sql before implementation:
```sql
-- Extend facts
ALTER TABLE facts ADD COLUMN discovered_turn INTEGER;
ALTER TABLE facts ADD COLUMN discovery_method TEXT;

-- Extend scene
ALTER TABLE scene ADD COLUMN visibility_conditions TEXT DEFAULT 'normal';
ALTER TABLE scene ADD COLUMN noise_level TEXT DEFAULT 'normal';
ALTER TABLE scene ADD COLUMN obscured_entities_json TEXT DEFAULT '[]';
```

And extend InterpreterOutput schema:
```json
"perception_flags": {
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "entity_id": {"type": "string"},
      "issue": {"type": "string"},
      "player_assumption": {"type": "string"}
    }
  }
}
```

### COMPETITIVE_ANALYSIS.md

| Feature | In COMPETITIVE | In TDD/Schema | Status |
|---------|----------------|---------------|--------|
| Memory anchors | ✓ (Gap 1) | ✗ | **DESIGN ONLY** |
| Context priority tiers | ✓ (Gap 2) | ✗ | **DESIGN ONLY** |
| NPC memory tables | ✓ (Gap 3) | ✗ | **NEEDS ADDITION** |
| Action significance | ✓ (Gap 4) | ✗ | **NEEDS ADDITION** |
| Token budgeting | ✓ (Gap 5) | ✗ | **DESIGN ONLY** |
| Relationship auto-updates | ✓ (Gap 6) | ✗ | **DESIGN ONLY** |
| Genre rules in context | ✓ (Gap 7) | ✗ | **DESIGN ONLY** |

**Impact:** These are quality improvements identified from competitive analysis. Most are Context Builder or Resolver enhancements, not schema changes.

**Recommendation:**
- Add `conversation_memory` and `npc_memories` tables
- Add `significance` field to InterpreterOutput
- Implement memory anchors in Context Builder
- These can be Phase 2/3 enhancements

---

## Schema Alignment Check

### TDD JSON Shapes vs Actual Schemas

| Schema | TDD Spec | `src/schemas/` | Match? |
|--------|----------|----------------|--------|
| ContextPacket | ✓ | ✓ | **MATCH** |
| InterpreterOutput | ✓ | ✓ | **MATCH** |
| ValidatorOutput | ✓ | ✓ | **MATCH** |
| PlannerOutput | ✓ | ✓ | **MATCH** |
| EngineEvent | ✓ | ✗ (not in schemas/) | **MISSING** |
| StateDiff | ✓ | ✓ | **MATCH** |
| NarratorOutput | ✓ | ✓ | **MATCH** |

**Issue:** `EngineEvent` schema exists in TDD but not in `src/schemas/`.

**Fix:** Add `src/schemas/engine_event.schema.json`:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "EngineEvent",
  "type": "object",
  "required": ["type", "details", "tags"],
  "properties": {
    "type": {"type": "string"},
    "details": {"type": "object"},
    "tags": {"type": "array", "items": {"type": "string"}}
  },
  "additionalProperties": false
}
```

### schema.sql vs TDD SQL

| Difference | TDD | schema.sql | Status |
|------------|-----|------------|--------|
| CREATE TABLE | CREATE TABLE | CREATE TABLE IF NOT EXISTS | **OK** (safer) |
| PRAGMA foreign_keys | not mentioned | ON | **OK** (enhancement) |
| All tables | ✓ | ✓ | **MATCH** |
| All indexes | ✓ | ✓ | **MATCH** |

**Status:** schema.sql is consistent with TDD, with minor defensive improvements.

---

## Prompt Template Check

### Interpreter Prompt

| Requirement | In Prompt | Status |
|-------------|-----------|--------|
| Conservative interpretation | ✓ "Be conservative" | **OK** |
| No invented facts | ✓ "Do not invent facts" | **OK** |
| Unknown entity handling | ✓ "list them in assumptions" | **OK** |
| JSON only output | ✓ | **OK** |
| Perception flags | ✗ | **NEEDS ADDITION** |

**Enhancement needed:** Add perception flag instruction per PERCEPTION_DESIGN.md:
```
- If the player references an entity not in the context packet, flag it in perception_flags with issue "not_perceived".
```

### Planner Prompt

| Requirement | In Prompt | Status |
|-------------|-----------|--------|
| Beat planning | ✓ "1 to 3 beats" | **OK** |
| Clarification handling | ✓ | **OK** |
| Tension move | ✓ | **OK** |
| GM moves palette | ✗ | **NEEDS ADDITION** |

**Enhancement needed:** Add GM moves from Dungeon World per GM_REFERENCE_AUDIT.md:
```
Available tension moves (choose one):
- Reveal an unwelcome truth
- Show signs of approaching threat
- Put someone in a spot
- Offer opportunity with cost
- Use up their resources
- Turn their move back on them
```

### Narrator Prompt

| Requirement | In Prompt | Status |
|-------------|-----------|--------|
| No new facts | ✓ | **OK** |
| Voice consistency | ✓ "consistent with current setting" | **OK** |
| End with prompt | ✓ | **OK** |
| Suggested actions | ✓ "2 to 3 suggested actions" | **OK** |
| POV constraint | ✗ | **NEEDS ADDITION** |
| Genre voice | ✗ | **NEEDS ADDITION** |

**Enhancement needed:** Add per PERCEPTION_DESIGN.md and GM guidance:
```
- Only describe what the character can currently perceive. Use sensory language tied to the character's POV.
- For cyberpunk noir: Fast-paced, jargon-heavy, show context rather than explain, neon-lit shadows.
```

---

## Code Stub Check

### orchestrator.py

| Feature | Implemented | Status |
|---------|-------------|--------|
| Turn number tracking | ✓ | **OK** |
| Event recording | ✓ | **OK** |
| Prompt version tracking | ✓ | **OK** |
| All pass outputs stored | ✓ | **OK** |
| Actual LLM calls | ✗ (stub returns) | **EXPECTED** |
| Validator logic | ✗ (stub) | **EXPECTED** |
| Resolver logic | ✗ (stub) | **EXPECTED** |

**Status:** Stub is well-structured. Ready for real implementation.

### state_store.py

| Feature | Implemented | Status |
|---------|-------------|--------|
| Schema initialization | ✓ | **OK** |
| Event append | ✓ | **OK** |
| Event retrieval | ✓ | **OK** |
| Range queries | ✓ | **OK** |
| Entity CRUD | ✗ | **NEEDS ADDITION** |
| Fact CRUD | ✗ | **NEEDS ADDITION** |
| Clock updates | ✗ | **NEEDS ADDITION** |
| State diff application | ✗ | **NEEDS ADDITION** |

**Status:** Basic event store works. Need to add state mutation methods.

### context/builder.py

| Feature | Implemented | Status |
|---------|-------------|--------|
| Return valid ContextPacket | ✓ | **OK** |
| Load from state store | ✗ | **NEEDS ADDITION** |
| Perception filtering | ✗ | **NEEDS ADDITION** |
| Priority tiers | ✗ | **NEEDS ADDITION** |
| Token budgeting | ✗ | **NEEDS ADDITION** |

**Status:** Returns empty packet. Needs full implementation.

---

## Contradictions Found

### 1. Clarification Question Ownership

**Issue:** Both Validator and Planner can set `clarification_question`.

- TDD ValidatorOutput: `"clarification_needed": true, "clarification_question": ""`
- TDD PlannerOutput: `"clarification_question": ""`

**Resolution:** Per HLD, the Orchestrator enforces 1-question policy. Planner defers to Validator's question if `clarification_needed=true`. Add to Planner prompt:
```
- If validator_output.clarification_needed is true, leave clarification_question empty (Validator's question takes precedence).
```

### 2. suggested_actions Location

**Issue:** Both Planner and Narrator output suggested actions.

- PlannerOutput: `"next_suggestions": ["", "", ""]`
- NarratorOutput: `"suggested_actions": ["", "", ""]`

**Resolution:** These serve different purposes:
- Planner's `next_suggestions` are structural options for the narrative
- Narrator's `suggested_actions` are player-facing prose suggestions

Both are valid. Narrator should use Planner's suggestions as input but phrase them for player. Document this relationship.

### 3. Position/Effect Not in Core Schemas

**Issue:** SESSION_ZERO_DESIGN.md describes Position/Effect system, but it's not in TDD or schemas.

**Resolution:** Position/Effect is part of the Game System module, loaded at runtime. It affects Validator and Resolver behavior but isn't a fixed schema. This is intentional—the system is configurable.

---

## Missing Pieces for v0

### Must Have (Blocks Basic Play)

1. **LLM Gateway implementation** - Currently no actual LLM calls
2. **State store entity/fact CRUD** - Can't populate initial state
3. **Context builder state loading** - Can't build real context
4. **Validator implementation** - Currently passes everything
5. **Resolver implementation** - Currently no state changes
6. **Initial scenario data** - Need at least one playable case

### Should Have (Quality of Life)

7. **Perception filtering in Context Builder**
8. **Perception flags in Interpreter**
9. **GM moves in Planner prompt**
10. **Genre voice in Narrator prompt**

### Nice to Have (Polish)

11. **Session Zero pipeline**
12. **Game System YAML loading**
13. **NPC memory tables**
14. **Token budgeting**

---

## Recommended Implementation Order

### Phase 1: Basic Turn Loop (Minimum Viable)

1. Implement LLM Gateway with Claude adapter
2. Implement State Store entity/fact/clock CRUD
3. Implement Context Builder state loading
4. Implement Validator with basic rules (presence, inventory)
5. Implement Resolver with clock updates
6. Create one test scenario with hardcoded initial state
7. Test end-to-end turn execution

### Phase 2: Perception & Quality

8. Add perception columns to schema
9. Implement perception filtering in Context Builder
10. Add perception_flags to Interpreter schema/prompt
11. Enhance Planner prompt with GM moves
12. Enhance Narrator prompt with POV constraints
13. Add replay harness

### Phase 3: Setup & Configuration

14. Implement Session Zero pipeline
15. Add Game System YAML loading
16. Add Calibration storage
17. Create scenario templates
18. Add NPC memory tables

### Phase 4: Polish

19. Token budgeting
20. Memory anchors
21. Context priority tiers
22. Relationship auto-updates

---

## Files Needing Updates

### Schema Updates Needed

```
src/db/schema.sql:
  - ADD facts.discovered_turn
  - ADD facts.discovery_method
  - ADD scene.visibility_conditions
  - ADD scene.noise_level
  - ADD scene.obscured_entities_json
  - ADD TABLE conversation_memory (optional)
  - ADD TABLE npc_memories (optional)

src/schemas/interpreter_output.schema.json:
  - ADD perception_flags array

src/schemas/engine_event.schema.json:
  - CREATE (missing file)
```

### Prompt Updates Needed

```
src/prompts/interpreter_v0.txt:
  - ADD perception flag instruction

src/prompts/planner_v0.txt:
  - ADD GM moves palette
  - ADD clarification precedence rule

src/prompts/narrator_v0.txt:
  - ADD POV constraint
  - ADD genre voice guidance
```

### Code Additions Needed

```
src/db/state_store.py:
  - ADD get_entities()
  - ADD get_facts()
  - ADD get_clocks()
  - ADD apply_state_diff()
  - ADD update_clock()
  - etc.

src/context/builder.py:
  - IMPLEMENT state loading
  - IMPLEMENT perception filtering
  - IMPLEMENT priority tiers

src/llm/gateway.py:
  - IMPLEMENT Claude adapter
  - IMPLEMENT schema validation
  - IMPLEMENT retries

src/core/validator.py:
  - CREATE with basic rules

src/core/resolver.py:
  - CREATE with clock/state logic
```

---

## Conclusion

**Overall Status: READY TO BUILD**

The documentation suite is comprehensive and internally consistent. The core architecture (PRD → HLD → TDD → Schemas → Stubs) aligns well. The identified issues are:

1. **Extensions from design docs** not yet in core schemas (perception, NPC memory)
2. **Prompt enhancements** needed from GM guidance
3. **Session Zero** is a separate pipeline not yet in TDD
4. **Implementation** is stubbed but well-structured

**Recommendation:** Proceed with Phase 1 implementation. The architecture is sound. Add the schema extensions and prompt enhancements as you implement each component.

**Risk Level:** Low. No fundamental contradictions. All issues are additive (need to add things) rather than conflicting (need to change things).
