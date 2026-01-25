# GM Reference Material Audit

Comprehensive audit of all GM guidance material, organized by pipeline phase and use case to inform development.

---

## Document Inventory

### Core Extractions (`docs/gm_reference/extracted/`)

| Document | Source | Primary Focus | Size |
|----------|--------|---------------|------|
| `lazy_dungeon_master.md` | Sly Flourish (epub) | Session prep, secrets/clues, strong starts | Large |
| `dungeon_world_gm_extracted.md` | Dungeon World SRD | GM moves, principles, fronts | Medium |
| `three_clue_extracted.md` | The Alexandrian | Information redundancy, revelation design | Small |
| `node_based_extracted.md` | The Alexandrian | Scenario structure, proactive nodes | Medium |
| `dont_prep_plots_extracted.md` | The Alexandrian | Situation vs plot philosophy | Small |
| `robins_laws_extracted.md` | Robin D. Laws | Player types, improvisation | Medium |
| `game_structures_extracted.md` | The Alexandrian | Game structure theory | Small |
| `prep_tips_extracted.md` | The Alexandrian | Prep philosophy | Small |

### Design Documents (`docs/gm_reference/`)

| Document | Focus |
|----------|-------|
| `PERCEPTION_DESIGN.md` | Character knowledge vs world state |

### Analysis Documents (`docs/`)

| Document | Focus |
|----------|-------|
| `GM_KNOWLEDGE_COVERAGE.md` | Knowledge domain mapping |
| `GM_WORKFLOW_COVERAGE.md` | Workflow-centric gap analysis |
| `GM_GUIDANCE_GAPS.md` | Per-stage gap identification |
| `COMPETITIVE_ANALYSIS.md` | Competitive tool analysis |
| `SESSION_ZERO_DESIGN.md` | First session setup architecture |

---

## Coverage by Pipeline Phase

### Phase 0: Session Zero / Calibration

**What We Need:** Tone calibration, theme selection, risk settings, character creation, NPC population, case structure generation.

| Concept | Source | Coverage | Notes |
|---------|--------|----------|-------|
| **Session Zero Process** | `lazy_dungeon_master.md` | Good | 8-step checklist, "review characters" |
| **Tone/Theme Calibration** | `SESSION_ZERO_DESIGN.md` | Good | New calibration framework |
| **Character Questions** | `SESSION_ZERO_DESIGN.md` | Good | 7 core questions + theme questions |
| **NPC Creation** | `robins_laws_extracted.md` | Partial | Names/personalities, but not agenda design |
| **Agenda Design** | `dont_prep_plots_extracted.md` | Good | Goal-oriented opponents |
| **Stakes Questions** | `dungeon_world_gm_extracted.md` | Good | Fronts with stakes questions |

**Gaps:**
- No explicit guidance on balancing character backstory depth
- No framework for integrating player answers with scenario content

---

### Phase 1: Context Building

**What We Need:** What information to include, priority tiers, token management, perception filtering.

| Concept | Source | Coverage | Notes |
|---------|--------|----------|-------|
| **Perception Filtering** | `PERCEPTION_DESIGN.md` | Good | World/known/perceived distinction |
| **Memory Anchors** | `COMPETITIVE_ANALYSIS.md` | Good | Always-include core facts |
| **Priority Tiers** | `COMPETITIVE_ANALYSIS.md` | Good | Essential/Important/Background |
| **What to Include** | `prep_tips_extracted.md` | Partial | "Essential + awesome details" |
| **Token Budgeting** | `COMPETITIVE_ANALYSIS.md` | Noted | Gap identified, no technique |

**Gaps:**
- No guidance on summarization technique (how to compress without losing meaning)
- No specific rules for what counts as "essential" vs "important"

---

### Phase 2: Interpreter (Understanding Intent)

**What We Need:** How to parse player input, recognize intent, handle ambiguity.

| Concept | Source | Coverage | Notes |
|---------|--------|----------|-------|
| **"To do it, do it"** | `dungeon_world_gm_extracted.md` | Good | Action triggers consequences |
| **Permissive Clue-Finding** | `three_clue_extracted.md` | Good | Reward clever approaches |
| **Player Types** | `robins_laws_extracted.md` | Good | Understanding what players want |
| **Flag Unknown Refs** | `PERCEPTION_DESIGN.md` | Good | perception_flags in output |
| **Graceful Errors** | `COMPETITIVE_ANALYSIS.md` | Noted | Gap identified |

**Gaps:**
- No fuzzy matching technique for ambiguous input
- No framework for distinguishing player intent vs character intent

---

### Phase 3: Validator (Adjudicating Actions)

**What We Need:** When to say yes/no, how to calculate costs, how to determine stakes.

| Concept | Source | Coverage | Notes |
|---------|--------|----------|-------|
| **Perception Rules** | `PERCEPTION_DESIGN.md` | Good | Block unknown targets |
| **Say Yes Philosophy** | `GM_WORKFLOW_COVERAGE.md` | Referenced | Links to Alexandrian article |
| **Position/Effect** | `SESSION_ZERO_DESIGN.md` | Good | In game system YAML |
| **Consequence Types** | `SESSION_ZERO_DESIGN.md` | Good | In game system YAML |
| **No Single Points of Failure** | `robins_laws_extracted.md` | Good | Multiple paths to success |

**Gaps:**
- **CRITICAL:** No decision framework for difficulty/stakes/costs
- No guidance on when partial success vs full failure
- Need Blades in the Dark Position/Effect deep-dive

---

### Phase 4: Planner (Structuring Response)

**What We Need:** How to select narrative beats, pace tension, weave themes.

| Concept | Source | Coverage | Notes |
|---------|--------|----------|-------|
| **GM Moves** | `dungeon_world_gm_extracted.md` | Excellent | 12 moves, soft/hard distinction |
| **Soft→Hard Escalation** | `dungeon_world_gm_extracted.md` | Good | Ignored soft moves become hard |
| **The Choice Method** | `robins_laws_extracted.md` | Good | Obvious/Challenging/Surprising/Pleasing |
| **Structure Pacing** | `game_structures_extracted.md` | Good | Early/middle/late rhythms |
| **Proactive Nodes** | `node_based_extracted.md` | Good | Things that come to player |
| **Push vs Pull** | `node_based_extracted.md` | Good | Balance attraction and pressure |
| **Fronts/Grim Portents** | `dungeon_world_gm_extracted.md` | Good | NPC timeline escalation |

**Gaps:**
- **CRITICAL:** No pacing math (when to advance clocks, how fast)
- No guidance on beat length/density
- Need Hamlet's Hit Points upward/downward beat theory

---

### Phase 5: Resolver (Executing Actions)

**What We Need:** How to determine outcomes, apply consequences, update state.

| Concept | Source | Coverage | Notes |
|---------|--------|----------|-------|
| **Consequence Types** | `SESSION_ZERO_DESIGN.md` | Good | 5 types in YAML |
| **Clock Mechanics** | `SESSION_ZERO_DESIGN.md` | Partial | Structure exists, no theory |
| **Relationship Updates** | `COMPETITIVE_ANALYSIS.md` | Noted | Gap identified |
| **Partial Success** | `robins_laws_extracted.md` | Good | Always accomplish something |

**Gaps:**
- **CRITICAL:** No clock theory (when to tick, how many segments, trigger design)
- No resistance mechanics (player agency over consequences)
- Need Blades in the Dark progress clocks deep-dive

---

### Phase 6: Narrator (Generating Prose)

**What We Need:** How to describe scenes, write dialogue, maintain voice, manage length.

| Concept | Source | Coverage | Notes |
|---------|--------|----------|-------|
| **Stay in POV** | `PERCEPTION_DESIGN.md` | Good | Sensory, character-limited |
| **Don't Name Your Move** | `dungeon_world_gm_extracted.md` | Critical | No mechanical leakage |
| **Name Every Person** | `dungeon_world_gm_extracted.md` | Good | Instant NPC naming |
| **End with "What do you do?"** | `dungeon_world_gm_extracted.md` | Good | Prompt player action |
| **Suggested Actions** | `COMPETITIVE_ANALYSIS.md` | Noted | Mix risk levels |

**Gaps:**
- **CRITICAL:** No prose craft guidance (description technique, dialogue)
- No genre voice guide (cyberpunk noir style)
- No guidance on response length calibration
- Need Rule of Three for descriptions, noir writing guide

---

### Phase 7: Commit (State Updates)

**What We Need:** What to record, how to structure diffs, when to summarize.

| Concept | Source | Coverage | Notes |
|---------|--------|----------|-------|
| **Revelation Tracking** | `three_clue_extracted.md` | Good | Clues available vs discovered |
| **Discovery Events** | `PERCEPTION_DESIGN.md` | Good | How facts become known |
| **Event Memory** | `COMPETITIVE_ANALYSIS.md` | Noted | NPC memories table |
| **Session Compilation** | `COMPETITIVE_ANALYSIS.md` | Noted | End-of-session summary |

**Gaps:**
- No guidance on what to store vs what to derive
- No summarization technique for long sessions

---

## Coverage by GM Workflow

### 1. Understanding Intent
**Status:** Good coverage

| Source | Key Concepts |
|--------|--------------|
| `robins_laws_extracted.md` | Player types, what they want |
| `dungeon_world_gm_extracted.md` | "To do it, do it" |
| `PERCEPTION_DESIGN.md` | Flag unknown references |

### 2. Adjudicating Actions
**Status:** WEAK - Major gap

| Source | Key Concepts |
|--------|--------------|
| `GM_WORKFLOW_COVERAGE.md` | References external articles |
| `SESSION_ZERO_DESIGN.md` | Position/Effect structure |

**Missing:** Concrete decision framework for yes/no/yes-but/no-and

### 3. Managing Information
**Status:** Strong coverage

| Source | Key Concepts |
|--------|--------------|
| `three_clue_extracted.md` | Redundancy, revelation tracking |
| `node_based_extracted.md` | Clue distribution, proactive delivery |
| `PERCEPTION_DESIGN.md` | Knowledge filtering |

### 4. Running the World
**Status:** Good coverage

| Source | Key Concepts |
|--------|--------------|
| `dont_prep_plots_extracted.md` | Situation-based, goal-oriented NPCs |
| `dungeon_world_gm_extracted.md` | Think offscreen, fronts |
| `node_based_extracted.md` | Proactive nodes, triggers |

### 5. Creating Tension
**Status:** WEAK - Theory without mechanics

| Source | Key Concepts |
|--------|--------------|
| `dungeon_world_gm_extracted.md` | Soft/hard moves |
| `game_structures_extracted.md` | Structure pacing |
| `SESSION_ZERO_DESIGN.md` | Clock structure (no theory) |

**Missing:** Clock math, pacing formulas, beat rhythm

### 6. Portraying the Fiction
**Status:** WEAK - Almost no coverage

| Source | Key Concepts |
|--------|--------------|
| `dungeon_world_gm_extracted.md` | "Don't name your move" |
| `PERCEPTION_DESIGN.md` | POV constraints |

**Missing:** Description craft, dialogue, genre voice

### 7. Improvising
**Status:** Good coverage

| Source | Key Concepts |
|--------|--------------|
| `robins_laws_extracted.md` | The Choice Method |
| `dungeon_world_gm_extracted.md` | Ask questions, use answers |
| `dont_prep_plots_extracted.md` | Toys not scripts |

---

## Key Concepts Index

Quick reference for finding specific concepts.

### Philosophy / Principles

| Concept | Primary Source | Also In |
|---------|----------------|---------|
| "Play to find out" | `dungeon_world_gm_extracted.md` | `dont_prep_plots_extracted.md` |
| Situations vs Plots | `dont_prep_plots_extracted.md` | - |
| The Power Fantasy | `robins_laws_extracted.md` | - |
| Be a Fan of Characters | `dungeon_world_gm_extracted.md` | - |
| Don't Name Your Move | `dungeon_world_gm_extracted.md` | - |
| Essential + Awesome Details | `prep_tips_extracted.md` | - |

### Structural Patterns

| Concept | Primary Source | Also In |
|---------|----------------|---------|
| Three Clue Rule | `three_clue_extracted.md` | `node_based_extracted.md` |
| Node-Based Design | `node_based_extracted.md` | - |
| Proactive Nodes | `node_based_extracted.md` | `three_clue_extracted.md` |
| Fronts / Grim Portents | `dungeon_world_gm_extracted.md` | `lazy_dungeon_master.md` |
| Puzzle-Piece Structure | `robins_laws_extracted.md` | - |
| Fractal Nodes | `node_based_extracted.md` | - |

### GM Moves / Actions

| Concept | Primary Source | Also In |
|---------|----------------|---------|
| 12 GM Moves | `dungeon_world_gm_extracted.md` | - |
| Soft vs Hard Moves | `dungeon_world_gm_extracted.md` | - |
| The Choice Method | `robins_laws_extracted.md` | - |
| Push vs Pull | `node_based_extracted.md` | - |

### Player Understanding

| Concept | Primary Source | Also In |
|---------|----------------|---------|
| 7 Player Types | `robins_laws_extracted.md` | - |
| Session Zero | `lazy_dungeon_master.md` | `SESSION_ZERO_DESIGN.md` |
| Character Questions | `SESSION_ZERO_DESIGN.md` | - |

### Information Design

| Concept | Primary Source | Also In |
|---------|----------------|---------|
| World/Known/Perceived | `PERCEPTION_DESIGN.md` | - |
| Revelation List | `three_clue_extracted.md` | `node_based_extracted.md` |
| Memory Anchors | `COMPETITIVE_ANALYSIS.md` | - |
| Context Priority Tiers | `COMPETITIVE_ANALYSIS.md` | - |

### Mechanical Systems

| Concept | Primary Source | Also In |
|---------|----------------|---------|
| Clocks | `SESSION_ZERO_DESIGN.md` | `COMPETITIVE_ANALYSIS.md` |
| Position/Effect | `SESSION_ZERO_DESIGN.md` | - |
| Consequences | `SESSION_ZERO_DESIGN.md` | - |
| Calibration Settings | `SESSION_ZERO_DESIGN.md` | - |

---

## Critical Gaps Summary

### Tier 1: Must Add (Blocks Core Functionality)

1. **Adjudication Framework**
   - When to say yes/no/yes-but
   - How to assess difficulty and stakes
   - **Recommended:** Blades in the Dark Position/Effect SRD

2. **Clock/Pacing Theory**
   - When to advance clocks
   - How many segments for what
   - Pacing math and beat rhythm
   - **Recommended:** Blades clocks + Hamlet's Hit Points

3. **Prose Craft / Narrative Voice**
   - How to describe scenes
   - Dialogue technique
   - Cyberpunk noir style guide
   - **Recommended:** Rule of Three descriptions, genre writing guide

### Tier 2: Should Add (Quality Improvement)

4. **Fuzzy Input Handling**
   - Graceful error messages
   - Suggestion patterns for invalid input

5. **Summarization Technique**
   - How to compress context without losing meaning
   - What to keep verbatim vs summarize

6. **Beat Length/Density**
   - How long should narrative responses be
   - When to be terse vs elaborate

### Tier 3: Nice to Have (Polish)

7. **Character Backstory Integration**
   - How to weave player answers into scenario

8. **NPC Voice Differentiation**
   - How to make NPCs sound distinct

---

## Reorganization Recommendations

### Current Structure Problems

1. **Mixed abstraction levels** - High-level philosophy docs alongside implementation specs
2. **Redundant coverage** - Same concepts appear in multiple analysis docs
3. **No clear reading order** - New developer doesn't know where to start
4. **Extracted docs are raw** - Need synthesis into actionable guidance

### Proposed New Structure

```
docs/gm_reference/
├── README.md                      # Reading guide, links to everything
├── 00_philosophy/
│   ├── situation_vs_plot.md       # Synthesized from dont_prep_plots
│   ├── play_to_find_out.md        # From DW, core principle
│   └── power_fantasy.md           # From Robin's Laws
├── 01_session_zero/
│   ├── SESSION_ZERO_DESIGN.md     # Existing, comprehensive
│   └── calibration_guide.md       # How to use calibration settings
├── 02_context_building/
│   ├── PERCEPTION_DESIGN.md       # Existing
│   ├── memory_anchors.md          # Synthesize from competitive analysis
│   └── priority_tiers.md          # Synthesize from competitive analysis
├── 03_adjudication/
│   ├── position_effect.md         # NEW - from Blades SRD
│   ├── say_yes_carefully.md       # NEW - from Alexandrian article
│   └── consequence_types.md       # Extract from SESSION_ZERO
├── 04_planning/
│   ├── gm_moves.md                # Synthesize from DW
│   ├── soft_hard_escalation.md    # From DW
│   ├── choice_method.md           # From Robin's Laws
│   └── proactive_nodes.md         # Synthesize from node_based
├── 05_tension/
│   ├── clock_theory.md            # NEW - from Blades SRD
│   ├── pacing_beats.md            # NEW - from Hamlet's Hit Points
│   └── fronts_portents.md         # From DW
├── 06_narration/
│   ├── description_craft.md       # NEW - Rule of Three, etc.
│   ├── cyberpunk_noir_voice.md    # NEW - genre guide
│   └── dialogue_technique.md      # NEW
├── 07_information/
│   ├── three_clue_rule.md         # Existing extraction, cleaned
│   ├── node_design.md             # Existing extraction, cleaned
│   └── revelation_tracking.md     # Synthesize from both
├── extracted/                      # Raw source extractions (archive)
│   ├── lazy_dungeon_master.md
│   ├── dungeon_world_gm_extracted.md
│   └── ...
└── analysis/                       # Coverage analysis docs
    ├── GM_KNOWLEDGE_COVERAGE.md
    ├── GM_WORKFLOW_COVERAGE.md
    └── COMPETITIVE_ANALYSIS.md
```

### Benefits of Reorganization

1. **Clear reading path** - Numbered folders suggest order
2. **Phase-aligned** - Matches pipeline stages
3. **Actionable docs** - Synthesized guidance, not raw dumps
4. **Archives preserved** - Original extractions kept for reference
5. **Easy to extend** - Clear place for new content

---

## Next Steps

### Immediate (Before Implementation)

1. [ ] Add Blades in the Dark Position/Effect content → `03_adjudication/`
2. [ ] Add Blades clock theory → `05_tension/`
3. [ ] Create description craft guide → `06_narration/`
4. [ ] Create cyberpunk noir voice guide → `06_narration/`

### During Implementation

5. [ ] Synthesize GM moves from DW into actionable list
6. [ ] Create memory anchors guide from competitive analysis
7. [ ] Create reading guide/README for the reference section

### Post-Implementation

8. [ ] Review coverage against actual pipeline needs
9. [ ] Add examples from real gameplay sessions
10. [ ] Consider vector embedding the guidance for prompt retrieval

---

## Document-by-Document Summary

### `lazy_dungeon_master.md` (Sly Flourish)

**Best Used For:** Session Zero, prep philosophy, secrets/clues

**Key Concepts:**
- 8-step lazy prep checklist
- Secrets and clues as "connective tissue"
- Strong starts (in medias res)
- Session zero process
- Review characters step
- Fronts adaptation from Dungeon World

**Pipeline Relevance:**
- Session Zero: High
- Context Builder: Medium (secrets/clues)
- Planner: Medium (strong starts)
- All else: Low

### `dungeon_world_gm_extracted.md`

**Best Used For:** Planner moves, moment-to-moment GMing

**Key Concepts:**
- Agenda: Portray world, fill lives with adventure, play to find out
- Principles: Leave blanks, address characters, never name your move
- 12 GM Moves: The palette for what can happen
- Soft/Hard move distinction
- Fronts with grim portents
- "What do you do?"

**Pipeline Relevance:**
- Planner: Excellent (moves, escalation)
- Narrator: High (principles)
- Context Builder: Medium (fronts)
- All else: Low-Medium

### `three_clue_extracted.md`

**Best Used For:** Information design, revelation tracking

**Key Concepts:**
- 3+ clues per revelation
- The four chokepoints (find, recognize, interpret, deduce)
- Proactive clue delivery (bash them on the head)
- Revelation tracking schema

**Pipeline Relevance:**
- Session Zero: High (designing case structure)
- Context Builder: Medium (what's discovered)
- Planner: Medium (when to deliver clues)
- Commit: High (tracking discoveries)

### `node_based_extracted.md`

**Best Used For:** Scenario structure, navigation design

**Key Concepts:**
- Nodes as points of interest (locations, people, events)
- Inverted Three Clue Rule
- Proactive nodes (come to player)
- Push vs pull navigation
- Fractal node design (zoom in/out)
- Dead ends are okay

**Pipeline Relevance:**
- Session Zero: High (case structure)
- Planner: High (what happens next)
- Context Builder: Medium (what's nearby/active)

### `dont_prep_plots_extracted.md`

**Best Used For:** Foundational philosophy

**Key Concepts:**
- Situations vs plots (core philosophy)
- Goal-oriented opponents
- NPCs as "tools" (what they're useful for)
- Non-specific contingency planning

**Pipeline Relevance:**
- Philosophy: Foundational
- Session Zero: High (NPC design)
- Planner: Medium (NPC agency)
- All stages: Conceptual foundation

### `robins_laws_extracted.md`

**Best Used For:** Understanding players, improvisation

**Key Concepts:**
- 7 player types (what they want)
- The Choice Method (4 options when stuck)
- Plot hooks start with verbs
- Victory conditions matter
- Power fantasy principle
- Puzzle-piece structure for mysteries

**Pipeline Relevance:**
- Session Zero: Medium (player type calibration)
- Planner: High (Choice Method)
- Narrator: Medium (power fantasy)

### `game_structures_extracted.md`

**Best Used For:** Understanding genre pacing

**Key Concepts:**
- What do characters do / how do players do it
- Different structures = different rhythms
- Noir mystery: early/middle/late pattern
- Skilled play varies by structure

**Pipeline Relevance:**
- Session Zero: Medium (structure selection)
- Planner: High (pacing by structure phase)

### `prep_tips_extracted.md`

**Best Used For:** Philosophy of detail level

**Key Concepts:**
- Essential + awesome details (skip the rest)
- Trust instincts over specification
- Players add their own complexity

**Pipeline Relevance:**
- Context Builder: Medium (what to include)
- Session Zero: Low (we have more detailed guidance)

### `PERCEPTION_DESIGN.md`

**Best Used For:** Information filtering, POV constraints

**Key Concepts:**
- World State / Character Knowledge / Current Perception
- Discovery events and methods
- Perception flags in Interpreter
- Validator blocks unknown targets
- Narrator stays in POV

**Pipeline Relevance:**
- Context Builder: Critical
- Interpreter: High
- Validator: High
- Narrator: High
