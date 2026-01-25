# Competitive Analysis: AI RPG Tools

Analysis of three existing AI RPG/GM tools and techniques we can adopt.

---

## Tool Summaries

### 1. mnehmos-rpg-mcp
**Type:** Rules-enforced RPG backend (MCP server)
**Philosophy:** "LLMs propose, never execute"

**Architecture:** Event-driven agentic pattern
```
OBSERVE → ORIENT (LLM) → DECIDE (orchestrator) → ACT (tools) → VALIDATE (rules)
```

**Key Innovation:** Biological metaphor
- **Brain** = LLM (proposes actions)
- **Nervous System** = Engine (validates constraints)
- **Reflex Arc** = Validator (blocks impossible actions pre-execution)
- **Sensory Organs** = Read-only tools
- **Muscles** = Action tools

**Interesting Features:**
- D&D 5e mechanics with anti-hallucination by design
- NPC memory + relationship tracking (familiarity + disposition)
- 28 consolidated tools (down from 195) for token efficiency
- Fuzzy action matching with helpful suggestions
- Economy with heat tracking, witnesses, fences
- 2,080+ tests with deterministic reproducibility

---

### 2. Narraitor
**Type:** Web-based narrative RPG framework
**Philosophy:** "Define your world's rules, AI adapts"

**Architecture:** Domain-driven with separate stores
```
World Domain → Character Domain → Narrative Domain
     ↓              ↓                   ↓
  (rules)       (state)            (generation)
```

**Key Innovation:** Adaptive narrative engine
- World creation wizard (7 steps)
- AI learns world tone/themes/mechanics
- Decision weighting (Minor/Major/Critical)
- Token budget management with truncation

**Interesting Features:**
- Custom attributes per world (e.g., "Force Sensitivity")
- Character alignment tracking
- IndexedDB persistence with graceful fallback
- Prompt builds from: world rules + character + recent events
- Multi-model roadmap (not locked to one provider)

---

### 3. VirtualGameMaster
**Type:** LLM-based GM simulator (CLI + Web)
**Philosophy:** Simple, provider-agnostic chat + state

**Architecture:** Traditional chat with windowing
```
User Input → LLM → Response → State Update
                ↓
    [Auto-summarize when messages > threshold]
```

**Key Innovation:** Message windowing
- MAX_MESSAGES threshold triggers state summarization
- KEPT_MESSAGES preserved for recent context
- Prevents context bloat in long sessions

**Interesting Features:**
- Multi-provider abstraction (llama.cpp, OpenRouter, Anthropic, etc.)
- YAML-based scenario templates
- Dual interface (CLI + React web)
- Extensible command system

---

## Comparison Matrix

| Aspect | mnehmos | Narraitor | VirtualGameMaster | **Our Design** |
|--------|---------|-----------|-------------------|----------------|
| **Core Pattern** | Propose/Validate | Generate/Adapt | Chat/Summarize | **Multi-pass Pipeline** |
| **LLM Role** | Proposes only | Generates narrative | Full GM | **Narrates from validated context** |
| **State Model** | SQLite, deterministic | IndexedDB, domain stores | YAML/XML, windowed | **Append-only event log** |
| **Validation** | Pre-execution reflex | None (trusts LLM) | None | **Validator pass** |
| **Mechanics** | D&D 5e rules | Custom per world | None | **Clocks + soft checks** |
| **Context Mgmt** | Tool consolidation | Token budget truncation | Message windowing | **Context builder (TBD)** |
| **NPC Agency** | Memory + relationships | AI-generated | None | **TBD** |

---

## Techniques to Adopt

### From mnehmos-rpg-mcp

#### 1. "Propose/Validate" Enforcement ✓
We already have this with our Validator pass, but mnehmos makes it more explicit:
- LLM output is always a *proposal*
- Engine is sole authority on execution
- "Reflex arc" blocks impossible actions before they reach resolver

**Our gap:** We don't explicitly frame the Interpreter output as "proposals" in our schema. Consider renaming `proposed_actions` and being strict about this language.

#### 2. NPC Memory & Relationship Tracking
mnehmos tracks:
- **Familiarity** (how well NPC knows PC)
- **Disposition** (attitude toward PC)
- **Conversation memory** (what they've discussed)
- **Cross-session history**

**Our gap:** Our `relationships` table has `type, intensity, notes` but no memory of conversations or familiarity progression.

**Recommendation:** Add to our schema:
```sql
-- Extend relationships or add new table
ALTER TABLE relationships ADD COLUMN familiarity INTEGER DEFAULT 0;
ALTER TABLE relationships ADD COLUMN last_interaction TEXT;

CREATE TABLE conversation_memory (
    id INTEGER PRIMARY KEY,
    entity_a TEXT,
    entity_b TEXT,
    turn_number INTEGER,
    topic TEXT,
    revealed_facts TEXT,  -- JSON array of fact IDs
    tone TEXT
);
```

#### 3. Fuzzy Action Matching with Helpful Errors
When player input doesn't match expected actions, mnehmos:
- Attempts fuzzy matching
- Returns suggestions rather than failures
- "Did you mean X?" pattern

**Our gap:** Interpreter doesn't have guidance on handling ambiguous/invalid input gracefully.

**Recommendation:** Add to Interpreter prompt: "If action is ambiguous, return top 2-3 interpretations with confidence scores. If action seems impossible, explain why and suggest alternatives."

#### 4. Token-Efficient Tool Design
mnehmos consolidated 195 tools → 28 with action parameters.

**Our relevance:** We're not using MCP tools, but the principle applies to our context packets. Keep them lean. Don't dump everything.

---

### From Narraitor

#### 5. Decision Weighting (Minor/Major/Critical)
Narraitor classifies player decisions by weight, affecting:
- How much narrative attention they get
- How much state changes
- How serious consequences are

**Our gap:** We don't distinguish action significance. Every action goes through the same pipeline weight.

**Recommendation:** Add `significance` field to interpreter output:
```json
{
  "proposed_actions": [...],
  "significance": "minor|standard|major|critical",
  "significance_reasoning": "..."
}
```

Planner can then:
- Minor: Quick resolution, minimal narration
- Standard: Normal flow
- Major: Extended narration, multiple beats
- Critical: Maximum drama, clock triggers, permanent consequences

#### 6. Token Budget Management
Narraitor tracks token usage and truncates prompts when sessions get long.

**Our gap:** No mention of token budgets in our design. Long sessions will eventually hit context limits.

**Recommendation:** Context Builder should:
1. Track estimated tokens per context section
2. Have a budget (e.g., 8000 tokens)
3. Prioritize: current scene > recent events > active threads > background
4. Truncate or summarize lower-priority sections when over budget

#### 7. World Rules as Explicit Context
Narraitor builds prompts from:
- World rules/constraints
- Character details
- Recent story events

**Our gap:** We have `scene.constraints` but no explicit "world rules" or "genre conventions" in context.

**Recommendation:** Add a `world_rules` or `genre_context` section to context packets that includes:
- Genre conventions (cyberpunk noir rules)
- Tone guidelines
- What's possible/impossible in this world

---

### From VirtualGameMaster

#### 8. Message Windowing / Auto-Summarization
When conversation exceeds threshold:
1. Summarize older context into compressed form
2. Keep N recent messages verbatim
3. Continue with summarized + recent

**Our design already has this:** The `summaries` table and Context Builder are meant to do this. But we should be explicit about the windowing logic.

**Recommendation:** Define in Context Builder:
```python
VERBATIM_TURNS = 5      # Keep last 5 turns in full
SUMMARY_THRESHOLD = 10  # Summarize when > 10 turns old
```

#### 9. Scenario Templates
YAML-based templates for different game setups.

**Our relevance:** We could have campaign templates that pre-populate:
- Initial entities/NPCs
- Starting scene
- Active clocks
- Genre rules

**Recommendation:** Add `src/scenarios/` directory with YAML templates for v0 cyberpunk case.

---

## Architecture Gaps Identified

### Gap 1: No Explicit "Proposal" Framing
**Problem:** Our pipeline doesn't explicitly treat LLM outputs as proposals that need validation.
**Risk:** Easy to accidentally trust LLM outputs.
**Fix:** Rename schema fields, add documentation emphasizing proposal→validation flow.

### Gap 2: No NPC Conversation Memory
**Problem:** NPCs don't remember what they've discussed with player.
**Risk:** Feels artificial when NPC forgets previous conversation.
**Fix:** Add conversation memory table, include in context for NPC interactions.

### Gap 3: No Action Significance Classification
**Problem:** All actions weighted equally.
**Risk:** Minor actions get over-narrated, critical moments under-emphasized.
**Fix:** Add significance field to interpreter output, adjust downstream processing.

### Gap 4: No Token Budget Management
**Problem:** Context builder has no budget awareness.
**Risk:** Long sessions will fail or truncate unpredictably.
**Fix:** Add token estimation and prioritized truncation to context builder.

### Gap 5: No Genre/World Rules in Context
**Problem:** Genre conventions aren't passed to LLM explicitly.
**Risk:** Tone drift, genre-inappropriate responses.
**Fix:** Add world rules section to context packets.

### Gap 6: No Graceful Error Handling Pattern
**Problem:** No guidance for handling ambiguous/invalid player input.
**Risk:** Frustrating player experience, hard failures.
**Fix:** Add fuzzy matching and suggestion patterns to interpreter.

---

## Recommendations Summary

### High Priority (Core Architecture)
1. **Add conversation memory table** — NPCs should remember interactions
2. **Add action significance classification** — Minor/Standard/Major/Critical
3. **Implement token budgeting** — Context builder needs limits

### Medium Priority (Quality)
4. **Add fuzzy matching / helpful errors** — Interpreter should suggest alternatives
5. **Add genre rules to context** — Explicit world/tone context
6. **Explicit proposal framing** — Schema/docs emphasize propose→validate

### Lower Priority (Polish)
7. **Scenario templates** — YAML-based campaign starters
8. **Provider abstraction** — Support multiple LLM backends (if needed)

---

## What We Do Better

Our design has strengths these tools lack:

| Our Advantage | vs. Others |
|---------------|------------|
| **Multi-pass pipeline** | More sophisticated than single-pass (VGM) or generate-only (Narraitor) |
| **Append-only event log** | Better auditability than mutable state |
| **Explicit planning pass** | Others mix planning into generation |
| **Clock mechanics** | More flexible than D&D rules (mnehmos) or no mechanics (Narraitor) |
| **GM theory backing** | None of these cite GM craft literature |

Our architecture is sound. The gaps are mostly in **details we haven't specified yet** rather than fundamental design flaws.
