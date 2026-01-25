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

#### 0. Perception/Observation Layer (CRITICAL)
mnehmos explicitly separates "Sensory Organs" (read-only observation tools) from action tools. This prevents a common failure mode:

**The Problem:**
- LLM describes things character can't perceive
- Player acts on metagame knowledge ("I duck before the sniper shoots")
- Actions reference entities the character doesn't know exist

**Their Approach:**
- OBSERVE step comes before ORIENT/DECIDE/ACT
- Read-only tools query what character can perceive
- Separate "world state" from "character knowledge" from "current perception"

**Our Gap:** We don't have an explicit perception layer. Our Validator checks presence/location but not "does the character know this exists?"

**See:** `docs/gm_reference/PERCEPTION_DESIGN.md` for proposed implementation.

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

### Gap 0: No Perception/Observation Layer (CRITICAL)
**Problem:** No filtering between world state and character knowledge.
**Risk:** LLM describes things character can't perceive; player acts on metagame knowledge.
**Fix:** See `docs/gm_reference/PERCEPTION_DESIGN.md` — filter context, flag unknown refs in Interpreter.

### Gap 1: No Memory Anchors
**Problem:** Core facts can get pushed out of context in long sessions.
**Risk:** Character forgets their own identity/goal; narrative drift.
**Fix:** Add "essential" tier to Context Builder that's always included verbatim.

### Gap 2: No Context Priority Tiers
**Problem:** Everything competes equally for context space.
**Risk:** Background lore crowds out critical current-scene info.
**Fix:** Three tiers: Essential (always), Important (if space), Background (summarize/trim).

### Gap 3: No NPC Memory System
**Problem:** NPCs don't remember conversations or significant events.
**Risk:** NPCs feel like stateless functions, not persistent characters.
**Fix:** Add `conversation_memory` and `npc_memories` tables.

### Gap 4: No Action Significance Classification
**Problem:** All actions weighted equally through pipeline.
**Risk:** Minor actions over-processed, critical moments under-emphasized.
**Fix:** Add significance field (Minor/Standard/Major/Critical) to Interpreter output.

### Gap 5: No Token Budget Management
**Problem:** Context builder has no budget awareness.
**Risk:** Long sessions fail or truncate unpredictably.
**Fix:** Add token estimation and prioritized truncation.

### Gap 6: No Automatic Relationship Updates
**Problem:** Actions don't affect NPC relationships automatically.
**Risk:** Threatening someone with a gun doesn't change how they feel about you.
**Fix:** Resolver emits relationship deltas based on action types.

### Gap 7: No Genre/World Rules in Context
**Problem:** Genre conventions aren't passed to LLM explicitly.
**Risk:** Tone drift, genre-inappropriate responses.
**Fix:** Add world rules section to context packets.

### Gap 8: No Structured Action Choice Guidelines
**Problem:** Narrator suggests actions without guidance on what makes good suggestions.
**Risk:** Suggestions are all similar risk/reward, don't advance story.
**Fix:** Prompt guidance: mix risk levels, include thread-advancing and exploratory options.

### Gap 9: No Graceful Error Handling Pattern
**Problem:** No guidance for handling ambiguous/invalid player input.
**Risk:** Frustrating player experience, hard failures.
**Fix:** Add fuzzy matching and suggestion patterns to Interpreter.

---

## Recommendations Summary

### Tier 1: Critical (Prevents Major Failure Modes)
1. **Perception/observation layer** — Filter context to character knowledge, flag unknown refs
2. **Memory anchors** — Always include core facts verbatim every turn
3. **Context priority tiers** — Essential/Important/Background with guaranteed inclusion

### Tier 2: High Priority (Core Architecture)
4. **Add NPC memory tables** — Conversation memory + event memory per NPC
5. **Add action significance classification** — Minor/Standard/Major/Critical
6. **Implement token budgeting** — Context builder needs limits
7. **Combat/action affects relationships** — Auto-update relationships from actions

### Tier 3: Medium Priority (Quality)
8. **Add fuzzy matching / helpful errors** — Interpreter should suggest alternatives
9. **Add genre rules to context** — Explicit world/tone context
10. **Explicit proposal framing** — Schema/docs emphasize propose→validate
11. **Structured action choices** — Mix risk levels in suggestions
12. **Model-per-stage configuration** — Fast models for classification, creative for narration

### Tier 4: Lower Priority (Polish)
13. **Scenario templates** — YAML-based campaign starters
14. **Provider abstraction** — Support multiple LLM backends (if needed)
15. **Vector store for semantic memory** — Embedding-based retrieval for callbacks

---

---

## Additional Tools Analyzed (Second Pass)

### 4. AIDM (deusversus)
**Type:** Multi-agent RPG platform with ChromaDB memory
**Key Innovation:** Different models for different pipeline stages

**Architecture:**
```
Player Input → Intent Classifier → Outcome Judge → Key Animator → State Update → Response
```

**Interesting Features:**
- **Model-per-stage**: Fast model for classification, creative model for narration, high-end for planning
- **ChromaDB-backed narrative memory** — vector store for long-term memory retrieval
- **Multi-phase turn lifecycle** — explicit pipeline like ours

### 5. llm_RPG (gddickinson)
**Type:** D&D-style RPG with LLM-powered NPCs
**Key Innovation:** Multiprocess NPC architecture

**Interesting Features:**
- **Each NPC runs in separate process** with dedicated LLM instance
- **NPC memory** — stores "important events they remember"
- **Combat affects relationships** — dynamic relationship updates based on actions
- **Parallel decision-making** — prevents LLM latency from blocking game loop

### 6. role-playing-mcp-server (fritzprix)
**Type:** MCP server for RPG narration
**Key Innovation:** Delta system for state changes

**Interesting Features:**
- **Change tracking via Delta system** — nested field updates with diffs
- **Empathetic context preservation** — game over includes summary for restarts
- **Action choice prompting** — generates "2-4 options mixing positive and negative outcomes"

### 7. AI Dungeon (commercial reference)
**Key Techniques:**
- **Memory Anchors** — repeat critical facts every 5-7 exchanges verbatim
- **Plot Essentials** — persistent memory separate from context window
- **Session compilation** — compile key events at end of session for continuity

---

## Additional Techniques to Adopt (Second Pass)

### From AIDM

#### 7. Model-Per-Stage Strategy
AIDM uses different models for different pipeline stages:
- **Fast/cheap model** for Intent Classification, Outcome Judging
- **Creative model** for Narration/Animation
- **High-end model** for Director/Planning

**Our relevance:** Our pipeline has distinct stages that could benefit from different model strengths:
- Interpreter → fast model (classification task)
- Validator → deterministic (no LLM needed?)
- Planner → high-end model (requires reasoning)
- Narrator → creative model (prose generation)

**Recommendation:** Add model selection to pipeline configuration.

#### 8. Vector Store for Narrative Memory
ChromaDB enables semantic search over past events, not just recency-based context.

**Our gap:** We rely on `summaries` table and recency. No semantic retrieval.

**Recommendation:** Consider adding embedding-based retrieval for "relevant past events" beyond just recent turns. Useful for callbacks like "remember when you met Viktor?"

### From llm_RPG

#### 9. Combat Affects Relationships
When characters fight, their relationships update dynamically.

**Our gap:** We have `relationships` table but no automatic updates from actions.

**Recommendation:** Resolver should emit relationship changes based on action types:
```json
{
  "relationships_update": [
    {"a": "player", "b": "viktor", "delta": -2, "reason": "threatened with gun"}
  ]
}
```

#### 10. NPC Event Memory
Each NPC stores "important events they remember" — not just relationship scores.

**Our gap:** Same as #2 above (conversation memory), but this is per-NPC event storage.

**Recommendation:** Add `npc_memories` table:
```sql
CREATE TABLE npc_memories (
    npc_id TEXT NOT NULL,
    event_turn INTEGER NOT NULL,
    event_summary TEXT NOT NULL,
    emotional_valence TEXT,  -- positive/negative/neutral
    importance INTEGER,       -- 1-5 scale
    PRIMARY KEY (npc_id, event_turn)
);
```

### From role-playing-mcp-server

#### 11. State Change Delta Tracking
Every state change is tracked as a delta with before/after, enabling undo and audit.

**Our design already has this:** Our append-only event log with `state_diff` is similar. But we could make it more explicit with reversible deltas.

#### 12. Structured Action Choices
Generate "2-4 options mixing positive and negative outcomes" for player.

**Our gap:** Narrator outputs `suggested_actions` but no guidance on what makes good suggestions.

**Recommendation:** Add to Narrator prompt:
> "Suggested actions should include 2-4 options. Mix low-risk/low-reward options with high-risk/high-reward options. At least one option should advance the main thread, one should be exploratory."

### From AI Dungeon Research

#### 13. Memory Anchor Technique (CRITICAL)
Repeat critical facts every 5-7 exchanges using a verbatim "memory anchor" phrase.

**Our gap:** We don't have explicit memory anchoring. Long sessions may drift.

**Recommendation:** Context Builder should include a `core_facts` section that:
- Contains 5-10 most critical facts (character identity, main goal, key relationships)
- Is injected verbatim every turn, not summarized
- Example: "You are Kai Chen, a disgraced corporate investigator. Your goal is to find who killed your partner. You owe Viktor 5000 credits."

#### 14. Plot Essentials / Persistent Memory
Separate "always included" facts from context window that can be pushed out.

**Our gap:** Everything competes for context space. No "always include" tier.

**Recommendation:** Add priority tiers to Context Builder:
1. **Essential** (always include): Character identity, active goal, core relationships
2. **Important** (include if space): Active threads, recent events, present NPCs
3. **Background** (summarize/trim): Historical events, distant NPCs, resolved threads

#### 15. Session Compilation
At end of session, compile key events into a summary for next session.

**Our design has this:** The `summaries` table. But we should be explicit about triggering compilation at natural breakpoints (scene changes, major events).

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
