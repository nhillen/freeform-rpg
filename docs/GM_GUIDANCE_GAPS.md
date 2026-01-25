# GM Guidance Gaps Analysis

This document identifies where expert GM advice would most strengthen the pipeline and agent implementations.

## Executive Summary

The project has solid high-level architecture (PRD/HLD/TDD) and comprehensive GM reference materials (7 extracted guides). The critical gap is **translating GM theory into operational pipeline logic**. The reference materials explain *what* great GMs do, but we lack guidance on *how to encode those decisions* into our specific pipeline stages.

---

## Gap Analysis by Pipeline Stage

### 1. Interpreter Stage

**Current state:** 16-line minimal prompt
**Missing GM guidance:**

| Gap | Why It Matters | Source Reference |
|-----|----------------|------------------|
| No "generous clue-finding" rules | Players describe investigation loosely; interpreter should credit reasonable attempts | Three Clue Rule |
| No intent ambiguity framework | Multiple valid interpretations → need principled way to pick or clarify | Robin's Laws (Choice Method) |
| No player type signals | Can't weight responses without detecting Power Gamer vs Method Actor vs Storyteller | Robin's Laws |
| No risk assessment principles | When is an action "risky" vs "routine"? Affects downstream cost assignment | Dungeon World (stakes) |

**What expert guidance would provide:**
- Decision tree for "what counts as a valid investigation attempt"
- Framework for resolving ambiguous player intent (ask vs assume)
- Signals that indicate player type from input patterns

---

### 2. Validator Stage

**Current state:** Rules listed in TDD, no implementation or decision logic
**Missing GM guidance:**

| Gap | Why It Matters | Source Reference |
|-----|----------------|------------------|
| No contradiction detection logic | How to identify when player assumes false facts? | Conservative defaults (PRD) |
| No cost matrix | Which actions cost Heat/Time/Cred/Harm? By how much? | PRD mentions costs, no values |
| No "conservative defaults" examples | What does "default to safe/believable" look like concretely? | PRD principle |
| No pushback voice | How to say "no" without feeling punitive | Dungeon World (be a fan of characters) |
| No clarification decision tree | When to ask vs block vs allow-with-consequences | One-question-max rule (CLAUDE.md) |

**What expert guidance would provide:**
- Cost matrix for cyberpunk noir actions (bribing cops = Heat +2, Time +1)
- Examples of "fair pushback" language
- Decision tree: presence/location/inventory/contradiction → allow/block/clarify/warn

---

### 3. Planner Stage

**Current state:** 17-line minimal prompt with vague "tension move" concept
**Missing GM guidance:**

| Gap | Why It Matters | Source Reference |
|-----|----------------|------------------|
| No GM moves library | 12 concrete Dungeon World moves aren't mapped to beat selection | Dungeon World |
| No soft vs hard move tracking | Ignored soft moves should escalate to hard consequences | Dungeon World |
| No structure phase detection | Pacing differs in setup vs rising action vs climax | Game Structures |
| No Push vs Pull balance | When should world act on player vs wait for player to act? | Node-Based Design |
| No pacing curve definition | How much tension per turn? When to release pressure? | All references mention this implicitly |

**What expert guidance would provide:**
- GM moves taxonomy adapted for LLM selection (move name → when to use → output shape)
- Soft move → hard move escalation rules
- Phase detection signals (are we in "gathering info" or "confrontation"?)
- Pacing guidelines per structure type (mystery vs heist vs intrigue)

---

### 4. Resolver Stage

**Current state:** Stub, rules described but no logic
**Missing GM guidance:**

| Gap | Why It Matters | Source Reference |
|-----|----------------|------------------|
| No NPC agenda system | NPCs don't pursue goals, just react | Don't Prep Plots |
| No off-screen advancement | World doesn't change when player isn't watching | Dungeon World ("think offscreen too") |
| No clock delta logic | When do clocks advance? By how much? | PRD defines clocks, no values |
| No threshold trigger system | Clock hitting max should fire narrative consequences | Implied everywhere |
| No proactive node scheduling | "Assassin arrives Tuesday" can't be encoded | Node-Based Design |

**What expert guidance would provide:**
- NPC agenda schema (goal, resources, timeline, triggers)
- Clock advancement rules per action type
- Threshold trigger → narrative consequence mapping
- Off-screen simulation rules (what happens per time unit?)

---

### 5. Narrator Stage

**Current state:** 19-line minimal prompt
**Missing GM guidance:**

| Gap | Why It Matters | Source Reference |
|-----|----------------|------------------|
| No voice/tone enforcement | Cyberpunk noir should feel consistent | PRD mentions genre, no guidelines |
| No "never name your move" rules | Mechanical outcomes should feel organic, not gamey | Dungeon World |
| No momentum principles | Some endings should push forward, others pause | Dungeon World (end with hook) |
| No summarize vs dramatize guidance | When to montage, when to play moment-by-moment | Game Structures |

**What expert guidance would provide:**
- Cyberpunk noir voice guide (vocabulary, sentence rhythm, mood)
- Examples of mechanical outcomes narrated invisibly
- Turn ending patterns (forward momentum vs pause for choice)

---

### 6. Context Builder

**Current state:** Stub returning empty context
**Missing GM guidance:**

| Gap | Why It Matters | Source Reference |
|-----|----------------|------------------|
| No relevance weighting | What makes an entity/fact "relevant now"? | All references |
| No revelation tracking | "Has player seen this clue?" not tracked | Three Clue Rule |
| No thread salience | Which threads matter for this turn's context? | Node-Based Design |
| No proactive threat context | Context doesn't include "who's hunting you" | Don't Prep Plots |

**What expert guidance would provide:**
- Relevance scoring rubric (recency, proximity, threat level, player interest)
- Revelation state machine (unknown → clued → confirmed)
- Thread salience calculation

---

## Cross-Cutting Gaps (Affect Multiple Stages)

### A. Clue & Revelation System
**Referenced in:** Three Clue Rule, Node-Based Design
**Currently missing entirely:**
- Revelation list structure (what facts can player discover?)
- Multiple paths per revelation (redundancy)
- Discovery state tracking (unknown/hinted/confirmed)
- Stuck detection (player has all clues but hasn't connected them)
- Proactive clue delivery (NPC brings info when player stalls)

**Expert guidance needed:**
- How to structure revelations for a cyberpunk noir case
- Signals that indicate "stuck" vs "working on it"
- Proactive clue timing rules

### B. NPC Agency & Proactive Nodes
**Referenced in:** Don't Prep Plots, Node-Based Design, Dungeon World
**Currently missing entirely:**
- Goal-oriented opponent framework
- NPC resource/capability tracking
- Timeline and trigger conditions
- Off-screen action simulation

**Expert guidance needed:**
- NPC agenda template for cyberpunk noir (fixer, corp exec, street gang)
- Trigger taxonomy (time-based, player-action-based, threshold-based)
- Proactive node balancing (how many active threats at once?)

### C. Escalation & Consequence Patterns
**Referenced in:** Dungeon World (soft/hard moves), PRD (real consequences)
**Currently missing:**
- Soft move → ignored → hard move progression
- Clock trigger → narrative consequence mapping
- Threat escalation timelines

**Expert guidance needed:**
- Soft move library with escalation paths
- Clock threshold meanings (Heat 3 = police interest, Heat 7 = active pursuit, Heat 10 = cornered)
- Consequence severity calibration

### D. Structure-Aware Pacing
**Referenced in:** Game Structures, Robin's Laws
**Currently missing:**
- Game structure detection (mystery vs heist vs chase)
- Phase detection within structure (setup → development → climax)
- Pacing rules per phase

**Expert guidance needed:**
- Structure templates for cyberpunk noir scenarios
- Phase transition signals
- Pacing tempo guidelines (turns per phase, tension curve)

---

## Priority Tiers for Expert Guidance

### Tier 1: Foundational (Blocks other work)

1. **Revelation & Clue System Design**
   - How to structure the cyberpunk case as revelations + nodes
   - Discovery tracking state machine
   - Stuck detection and proactive delivery

2. **NPC Agenda Framework**
   - Goal/resource/timeline template
   - Proactive trigger conditions
   - Off-screen advancement rules

3. **Clock Meaning & Escalation**
   - What each clock value means narratively
   - Threshold trigger consequences
   - Advancement rates per action type

### Tier 2: Pipeline Decision Quality

4. **GM Moves Library for Planner**
   - Dungeon World 12 moves adapted for LLM selection
   - Soft vs hard move classification
   - Move selection criteria per situation

5. **Validator Decision Trees**
   - Contradiction detection examples
   - Cost matrix for common actions
   - Pushback language patterns

6. **Structure & Phase Awareness**
   - Phase detection signals
   - Pacing rules per phase
   - Skilled play recognition

### Tier 3: Voice & Polish

7. **Cyberpunk Noir Voice Guide**
   - Vocabulary and rhythm
   - Mood and atmosphere rules
   - Example passages at different tension levels

8. **Narrator Craft**
   - Summarize vs dramatize decision rules
   - Move invisibility examples
   - Turn ending patterns

---

## Recommended Expert Sources

To fill these gaps, consider extracting guidance from:

| Source | Best For |
|--------|----------|
| **Blades in the Dark** | Clocks, heat, faction advancement, heist structure |
| **Apocalypse World** (full text) | MC moves, threat maps, countdown clocks |
| **GUMSHOE system** (Trail of Cthulhu, Night's Black Agents) | Investigative scene structure, clue spending, thriller pacing |
| **Technoir** | Cyberpunk-specific: transmissions, verbs, connection maps |
| **The Sprawl** | Cyberpunk PbtA: mission structure, corporate clocks, legwork/action phases |
| **Leverage RPG** | Heist structure, flashback mechanics, crew dynamics |
| **Swords Without Master** | Tone-first narration, mood dice concept |

---

## Next Steps

1. **Prioritize Tier 1 gaps** - these block meaningful implementation
2. **Extract additional sources** - especially Blades in the Dark (clocks), The Sprawl (cyberpunk), GUMSHOE (investigation)
3. **Create operational guides** - translate GM theory into decision trees and examples for each pipeline stage
4. **Build test scenarios** - concrete cyberpunk case beats to validate guidance against
