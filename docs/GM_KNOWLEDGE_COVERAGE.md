# GM Knowledge Coverage Analysis

This document maps **conceptual GM knowledge domains** against **pipeline stages** and shows where existing docs provide coverage vs where additional source material would help.

---

## Knowledge Domains Needed

| Domain | What It Covers | Which Pipeline Stages Need It |
|--------|----------------|-------------------------------|
| **Player Psychology** | What players want, player types, satisfaction signals | Interpreter, Planner, Narrator |
| **Information Design** | Clues, revelations, redundancy, discovery | Context, Interpreter, Validator, Planner |
| **World Simulation** | NPC agency, off-screen time, situations vs plots | Resolver, Planner |
| **Reactive GMing** | Moves, principles, improvisation, responding to player input | Planner, Narrator |
| **Structure & Pacing** | Phases, rhythm, tension curves, push/pull balance | Planner, Narrator |
| **Narrative Voice** | Tone, genre conventions, description, dialogue | Narrator |
| **Consequence Design** | Escalation, soft→hard, fairness, meaningful failure | Validator, Resolver, Planner |
| **Resource Economy** | Clocks, costs, scarcity, pressure mechanics | Validator, Resolver |

---

## Coverage Matrix

```
                        Player   Info    World   Reactive  Structure  Narrative  Consequence  Resource
                        Psych    Design  Sim     GMing     Pacing     Voice      Design       Economy
                        ───────  ──────  ──────  ────────  ─────────  ─────────  ───────────  ────────
Robin's Laws            ████░░   ░░░░░░  ░░░░░░  ██░░░░    ██░░░░     ░░░░░░     ░░░░░░       ░░░░░░
Dungeon World           ░░░░░░   ░░░░░░  ███░░░  ██████    ██░░░░     ██░░░░     ████░░       ░░░░░░
Game Structures         ░░░░░░   ░░░░░░  ░░░░░░  ░░░░░░    ████░░     ░░░░░░     ░░░░░░       ░░░░░░
Three Clue Rule         ░░░░░░   ██████  ░░░░░░  ░░░░░░    ░░░░░░     ░░░░░░     ░░░░░░       ░░░░░░
Don't Prep Plots        ░░░░░░   ██░░░░  ██████  ░░░░░░    ░░░░░░     ░░░░░░     ░░░░░░       ░░░░░░
Node-Based Design       ░░░░░░   ████░░  ██░░░░  ░░░░░░    ██░░░░     ░░░░░░     ░░░░░░       ░░░░░░
                        ───────  ──────  ──────  ────────  ─────────  ─────────  ───────────  ────────
COVERAGE TOTAL          ████░░   ████░░  ████░░  ██████    ████░░     ██░░░░     ████░░       ░░░░░░
                        GOOD     GOOD    GOOD    STRONG    GOOD       WEAK       PARTIAL      NONE
```

Legend: `██████` = deep coverage, `████░░` = good coverage, `██░░░░` = partial, `░░░░░░` = none

---

## Domain-by-Domain Analysis

### 1. Player Psychology — GOOD ✓
**Covered by:** Robin's Laws (extensively)

**What you have:**
- 7 player types with motivations and satisfaction patterns
- Power fantasy principle
- Choice Method for improv decisions

**What's missing:**
- Detection signals (how to infer type from text input)
- Solo vs group dynamics (your refs assume table play)

**Verdict:** Solid foundation. Can proceed without more material.

---

### 2. Information Design — GOOD ✓
**Covered by:** Three Clue Rule, Node-Based Design, Don't Prep Plots

**What you have:**
- Redundancy principle (3+ paths per revelation)
- Revelation vs node distinction
- Permissive clue-finding
- Proactive clue delivery
- Inverted three clue rule

**What's missing:**
- Investigation scene structure (beat-by-beat)
- "Interviewing NPCs" patterns specifically

**Verdict:** Strong coverage. GUMSHOE material could add investigative scene structure but not essential.

---

### 3. World Simulation — GOOD ✓
**Covered by:** Don't Prep Plots, Dungeon World, Node-Based Design

**What you have:**
- Situations vs plots philosophy
- Goal-oriented opponents
- "Think offscreen too" principle
- Proactive node triggers
- Toolkit/toy concept for NPCs

**What's missing:**
- Faction clocks / advancement systems
- Timed event scheduling patterns

**Verdict:** Philosophy is covered. You might want **Blades in the Dark** for faction clock mechanics specifically.

---

### 4. Reactive GMing — STRONG ✓✓
**Covered by:** Dungeon World (extensively), Robin's Laws

**What you have:**
- 12 GM moves with clear descriptions
- Soft vs hard move framework
- Principles (be a fan, think dangerous, never name moves, etc.)
- Choice Method for improv
- "What would be entertaining?" heuristic

**What's missing:** Nothing significant

**Verdict:** Best-covered domain. Ready to implement.

---

### 5. Structure & Pacing — GOOD ✓
**Covered by:** Game Structures, Node-Based Design, Dungeon World

**What you have:**
- Structure types (mystery, heist, dungeon, etc.)
- Phase concepts (setup → rising → climax)
- Push vs pull balance
- "Always end with what do you do?"

**What's missing:**
- Beat-by-beat pacing within scenes
- Tension curve mathematics
- When to summarize vs dramatize

**Verdict:** Good high-level coverage. Could use more **scene-level pacing** guidance.

---

### 6. Narrative Voice — WEAK ⚠️
**Covered by:** Dungeon World (briefly)

**What you have:**
- "Address characters not players"
- "Never speak the name of your move"
- General genre embrace advice

**What's missing:**
- Genre-specific voice guides (cyberpunk noir specifically)
- Description techniques
- Dialogue craft
- Atmosphere/mood creation
- Prose rhythm and style

**Verdict:** SIGNIFICANT GAP. Need writing craft material, ideally genre-specific.

---

### 7. Consequence Design — PARTIAL ⚠️
**Covered by:** Dungeon World

**What you have:**
- Soft → hard move escalation concept
- "Partial success" from Robin's Laws
- "Think dangerous" principle

**What's missing:**
- Consequence severity calibration
- Fairness principles
- Recovery mechanics (how does player bounce back?)
- Death/failure spiral prevention

**Verdict:** Concept is there, calibration guidance is missing. **Blades in the Dark** has good consequence + recovery patterns.

---

### 8. Resource Economy — NONE ⚠️⚠️
**Covered by:** Nothing directly

**What you have:**
- PRD mentions 5 clocks (Heat, Time, Cred, Harm, Rep)
- General scarcity implied

**What's missing:**
- Clock design philosophy
- Cost assignment principles
- Resource tension curves
- Economy balancing
- What different clock values *mean* narratively

**Verdict:** MAJOR GAP. Clocks are central to your design but you have no theory backing them. **Blades in the Dark** is the canonical source for clock mechanics.

---

## Pipeline Coverage Rollup

| Pipeline Stage | Primary Domains | Coverage Status |
|----------------|-----------------|-----------------|
| **Context Builder** | Information Design | ✓ Good |
| **Interpreter** | Player Psychology, Information Design | ✓ Good |
| **Validator** | Consequence Design, Resource Economy | ⚠️ Partial - missing economy theory |
| **Planner** | Reactive GMing, Structure, World Sim | ✓ Strong |
| **Resolver** | World Simulation, Resource Economy | ⚠️ Partial - missing clock theory |
| **Narrator** | Narrative Voice, Structure | ⚠️ Weak - missing voice/craft |

---

## Gap Summary

### STRONG - No additional material needed
- **Reactive GMing** (Dungeon World covers this completely)
- **Player Psychology** (Robin's Laws is comprehensive)
- **Information Design** (Three Clue + Node-Based is thorough)

### GOOD - Could enhance but can proceed
- **World Simulation** (philosophy covered, faction mechanics could help)
- **Structure & Pacing** (high-level good, scene-level could be stronger)

### WEAK - Should add material before building
1. **Resource Economy / Clock Theory**
   - Why: Clocks are your core pressure mechanic but you have zero theory
   - Recommended: Blades in the Dark (clock design, faction clocks, progress clocks)

2. **Narrative Voice / Prose Craft**
   - Why: Narrator is your output layer, needs genre-specific guidance
   - Recommended: Cyberpunk fiction craft, noir writing guides

3. **Consequence Calibration**
   - Why: Knowing soft→hard isn't enough; need to calibrate severity
   - Recommended: Blades in the Dark (harm + recovery), possibly Fate (consequence ladder)

---

## Recommended Additional Sources

### Priority 1: Clock & Consequence Theory
**Blades in the Dark** (John Harper)
- Progress clocks (4/6/8 segment)
- Faction clocks and advancement
- Position & Effect framework
- Harm levels and recovery
- Devil's bargains (cost trades)

This single source would fill your biggest gap.

### Priority 2: Narrative Voice
Need genre-specific guidance. Options:
- **Cyberpunk 2020/RED GM advice** (setting-specific GMing)
- **Noir writing craft essays** (prose style for the genre)
- **The Sprawl RPG** (cyberpunk PbtA, has mission structure + tone)

### Priority 3: Investigation Scene Structure (Optional)
**GUMSHOE / Night's Black Agents** (Robin Laws, Ken Hite)
- Core clue vs floating clue design
- Investigative ability spends
- Thriller combat pacing
- Scene types for investigation

Would strengthen your mystery structure but you could proceed without it.

---

## Visual: The Venn Diagram

```
                    ┌─────────────────────────────────────────────┐
                    │              YOUR PIPELINE                  │
                    │                                             │
   ┌────────────────┼───────────────┬─────────────────────────────┤
   │                │               │                             │
   │  INTERPRETER   │   VALIDATOR   │   RESOLVER                  │
   │  ┌───────────┐ │  ┌──────────┐ │  ┌──────────────┐          │
   │  │ Player    │ │  │Conseq-   │ │  │ World Sim    │          │
   │  │ Psych ✓   │ │  │uence ⚠️  │ │  │ ✓            │          │
   │  │           │ │  │          │ │  │              │          │
   │  │ Info      │ │  │ Resource │ │  │ Resource     │          │
   │  │ Design ✓  │ │  │ Econ ❌  │ │  │ Econ ❌      │          │
   │  └───────────┘ │  └──────────┘ │  └──────────────┘          │
   │                │               │                             │
   ├────────────────┼───────────────┼─────────────────────────────┤
   │                │               │                             │
   │    PLANNER     │   NARRATOR    │   CONTEXT                   │
   │  ┌───────────┐ │  ┌──────────┐ │  ┌──────────────┐          │
   │  │ Reactive  │ │  │Narrative │ │  │ Info Design  │          │
   │  │ GMing ✓✓  │ │  │Voice ❌  │ │  │ ✓            │          │
   │  │           │ │  │          │ │  │              │          │
   │  │ Structure │ │  │Structure │ │  └──────────────┘          │
   │  │ ✓         │ │  │ ✓        │ │                             │
   │  │           │ │  └──────────┘ │                             │
   │  │ World Sim │ │               │                             │
   │  │ ✓         │ │               │                             │
   │  └───────────┘ │               │                             │
   └────────────────┴───────────────┴─────────────────────────────┘

   ✓✓ = Strong    ✓ = Good    ⚠️ = Partial    ❌ = Gap
```

---

## Action Items

1. **Must have:** Add Blades in the Dark clock/consequence theory
2. **Should have:** Add cyberpunk/noir voice & prose guidance
3. **Nice to have:** Add GUMSHOE investigation structure

With just #1, you'd have solid coverage across all pipeline stages.

---

## Appendix: Key Concepts to Extract

### From Blades in the Dark (Clocks & Consequences)

**Progress Clocks:**
- Circle divided into segments (4 = complex, 6 = complicated, 8 = daunting)
- Make clocks about obstacles, not methods ("The Guards" not "Sneak Past Guards")
- Types: Danger clocks, Racing clocks, Tug-of-war clocks, Faction clocks
- Visible clocks give GM "permission to be mean" - player was warned
- Don't run more than 3-4 campaign-scale clocks at once

**Position & Effect:**
- Position = stakes level (Controlled / Risky / Desperate)
- Effect = how much progress (Limited / Standard / Great)
- Can trade position for effect (desperate + great effect vs risky + standard)
- This replaces difficulty - consequences get worse, not more common

**Consequences:**
- Reduced effect (action less effective than hoped)
- Complication (new problem: fire, alarm, reinforcements, +heat)
- Lost opportunity (chance gone)
- Worse position (escalates to harder situation)
- Harm (lasting injury, 4 levels from Lesser to Fatal)

**Resistance:**
- Players can resist consequences by spending stress
- Converts severe consequence to moderate, etc.
- Creates player agency over harm

**Design Philosophy:**
- GM needs somewhere to put consequences besides directly on characters
- Going straight to harm = characters too fragile
- Going straight to complications = mission too zany
- Clocks provide intermediate pressure vessel

### For Cyberpunk Noir Voice

**Prose Style:**
- Fast-paced, jargon-heavy
- Don't explain technology - show context, let reader infer
- Confusion is genre-appropriate, not a bug
- Bombard with info at a pace reader can barely keep up
- Hardboiled detective language meets technical vocabulary

**Atmosphere:**
- Post-industrial dystopia with cultural ferment
- "Low life and high tech" juxtaposition
- Film noir techniques: shadow, moral ambiguity, fatalism
- "The street finds its own uses for things"

**Characters:**
- Anti-heroes, reluctant heroes, misfits, criminals
- Cynical, bitter, prefer not to get involved
- Gray-and-gray morality
- No clear good guys

**Influences to Study:**
- *Blade Runner* (visual/atmosphere codifier)
- *Neuromancer* (prose style, slang, aesthetics)
- Classic noir fiction (Chandler, Hammett)

---

## Sources for Further Research

### Clocks & Consequence Theory
- [Blades in the Dark SRD - Progress Clocks](https://bladesinthedark.com/progress-clocks)
- [Blades in the Dark SRD - Consequences & Harm](https://bladesinthedark.com/consequences-harm)
- [The Alexandrian - Blades Progress Clocks Analysis](https://thealexandrian.net/wordpress/40424/roleplaying-games/blades-in-the-dark-progress-clocks)
- [Indie Game Reading Club - Clocks as Killer App](https://www.indiegamereadingclub.com/indie-game-reading-club/clocks-forged-in-the-darks-underappreciated-killer-app/)

### Cyberpunk Writing
- [TV Tropes - How to Write Cyberpunk](https://tvtropes.org/pmwiki/pmwiki.php/SoYouWantTo/WriteACyberPunkStory)
- [Liminal Pages - How to Write Cyberpunk](https://www.liminalpages.com/how-to-write-cyberpunk/)
- [RT Book Reviews - Cyberpunk Noir Genre Explained](https://rtbookreviews.com/cyberpunk-noir-book-genre-explained/)
