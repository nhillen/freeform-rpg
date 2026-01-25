# GM Workflow Coverage Analysis

This document maps GM reference materials to **fundamental GM workflows** - the core jobs a GM does regardless of system or implementation.

---

## The Seven GM Workflows

| # | Workflow | The Core Question |
|---|----------|-------------------|
| 1 | **Understanding Intent** | What is the player actually trying to do/experience? |
| 2 | **Adjudicating Actions** | Can they do it? What happens when they try? |
| 3 | **Managing Information** | What do they know? What should they learn? When? |
| 4 | **Running the World** | What are NPCs doing? How does time pass? What changes? |
| 5 | **Creating Tension** | How do I escalate? When do I release? What's the rhythm? |
| 6 | **Portraying the Fiction** | How do I describe, speak as NPCs, create atmosphere? |
| 7 | **Improvising** | How do I respond when they do something unexpected? |

---

## Coverage Map

```
                              Understanding  Adjudicating  Managing    Running    Creating    Portraying  Improvising
                              Intent         Actions       Information the World  Tension     Fiction
                              ─────────────  ────────────  ──────────  ─────────  ──────────  ──────────  ───────────
Robin's Laws                  ██████         ░░░░░░        ░░░░░░      ░░░░░░     ██░░░░      ░░░░░░      ████░░
Dungeon World GM              ██░░░░         ████░░        ░░░░░░      ████░░     ████░░      ██░░░░      ██████
Game Structures               ░░░░░░         ░░░░░░        ░░░░░░      ░░░░░░     ████░░      ░░░░░░      ░░░░░░
Three Clue Rule               ░░░░░░         ░░░░░░        ██████      ░░░░░░     ░░░░░░      ░░░░░░      ░░░░░░
Don't Prep Plots              ░░░░░░         ░░░░░░        ██░░░░      ██████     ░░░░░░      ░░░░░░      ████░░
Node-Based Design             ░░░░░░         ░░░░░░        ████░░      ██░░░░     ██░░░░      ░░░░░░      ░░░░░░
                              ─────────────  ────────────  ──────────  ─────────  ──────────  ──────────  ───────────
TOTAL                         ████░░         ████░░        ████░░      ████░░     ████░░      ██░░░░      ████░░
                              GOOD           PARTIAL       GOOD        GOOD       GOOD        WEAK        GOOD
```

---

## Workflow-by-Workflow Analysis

### 1. Understanding Intent — GOOD ✓
> "What is the player actually trying to do/experience?"

**Covered by:** Robin's Laws (extensively), Dungeon World (partially)

| Concept | Source | Notes |
|---------|--------|-------|
| Player types & motivations | Robin's Laws | 7 types with what satisfies each |
| "Be a fan of the characters" | Dungeon World | Assume good faith, want them to succeed |
| Power fantasy principle | Robin's Laws | Players want to feel competent |
| Reading the room | Robin's Laws | Adjust based on energy/engagement |

**Gap:** Nothing on parsing *ambiguous* intent. When player says something unclear, how does a good GM decide what they meant?

---

### 2. Adjudicating Actions — PARTIAL ⚠️
> "Can they do it? What happens when they try?"

**Covered by:** Dungeon World (moves framework)

| Concept | Source | Notes |
|---------|--------|-------|
| "To do it, do it" | Dungeon World | Fiction-first, if it makes sense it works |
| Soft vs hard consequences | Dungeon World | Graduated response to failure |
| "Be a fan" (say yes often) | Dungeon World | Bias toward allowing |

**Gaps:**
- **When to say no** - principles for blocking actions fairly
- **Difficulty/stakes calibration** - how hard should this be?
- **Cost assignment** - what should actions cost?
- **Partial success design** - what does "yes, but" look like?

**Missing workflow:** The actual decision tree for "player wants X, here's how I decide what happens"

---

### 3. Managing Information — GOOD ✓
> "What do they know? What should they learn? When?"

**Covered by:** Three Clue Rule (extensively), Node-Based Design, Don't Prep Plots

| Concept | Source | Notes |
|---------|--------|-------|
| Redundancy (3+ paths to truth) | Three Clue Rule | Never single point of failure |
| Proactive information delivery | Three Clue, Node-Based | Info comes to player when stuck |
| Revelation vs location distinction | Node-Based | What they learn ≠ where they go |
| Permissive clue-finding | Three Clue Rule | Credit reasonable attempts |
| "Spill information freely" | Don't Prep Plots | Don't hoard, it creates stalls |

**Gap:** Nothing on **pacing revelations** - when to give info freely vs make them work for it. How to create satisfying discovery moments vs just dumping facts.

---

### 4. Running the World — GOOD ✓
> "What are NPCs doing? How does time pass? What changes?"

**Covered by:** Don't Prep Plots (extensively), Dungeon World, Node-Based

| Concept | Source | Notes |
|---------|--------|-------|
| NPCs as goal-oriented agents | Don't Prep Plots | They want things, pursue them |
| "Think offscreen too" | Dungeon World | World moves when player isn't looking |
| Proactive nodes/triggers | Node-Based | Some things come hunting the player |
| Situations not plots | Don't Prep Plots | Maintain state, not scripts |
| Toolkit NPCs | Don't Prep Plots | Each NPC useful for something |

**Gap:** Nothing on **time & resource systems** - how clocks work, what triggers advancement, how to pace the world's movement against player actions.

---

### 5. Creating Tension — GOOD but shallow ✓
> "How do I escalate? When do I release? What's the rhythm?"

**Covered by:** Game Structures, Dungeon World, Node-Based

| Concept | Source | Notes |
|---------|--------|-------|
| Structure phases (setup→climax) | Game Structures | Macro pacing |
| Push vs pull balance | Node-Based | Pressure vs opportunity |
| Soft → hard escalation | Dungeon World | Ignored warnings become consequences |
| "Think dangerous" | Dungeon World | The world has teeth |
| Clocks as push mechanisms | Node-Based (brief) | Deadlines create urgency |

**Gaps:**
- **Tension curves** - how much pressure per beat? When to release?
- **Clock mechanics** - how do clocks actually work? What do values mean?
- **Spiral prevention** - how to avoid death spirals / overwhelming the player?
- **Recovery beats** - when and how to give player breathing room?

---

### 6. Portraying the Fiction — WEAK ⚠️
> "How do I describe, speak as NPCs, create atmosphere?"

**Covered by:** Dungeon World (briefly)

| Concept | Source | Notes |
|---------|--------|-------|
| "Address characters not players" | Dungeon World | Stay in fiction |
| "Never speak the name of your move" | Dungeon World | Hide mechanics |
| "Give every monster life" | Dungeon World | NPCs have personality |
| "Name every person" | Dungeon World | Specificity matters |

**Gaps:**
- **Description craft** - how to describe scenes, actions, outcomes
- **Dialogue** - how to voice NPCs, create distinct characters
- **Atmosphere/mood** - how to evoke genre feel
- **Prose rhythm** - pacing of narration, when verbose vs terse
- **Genre conventions** - cyberpunk/noir specific techniques

This is the **weakest workflow coverage**. You have principles ("stay in fiction") but no craft guidance.

---

### 7. Improvising — GOOD ✓
> "How do I respond when they do something unexpected?"

**Covered by:** Dungeon World (extensively), Don't Prep Plots, Robin's Laws

| Concept | Source | Notes |
|---------|--------|-------|
| The Choice Method | Robin's Laws | Pick what's entertaining |
| 12 GM moves | Dungeon World | Concrete response options |
| "Play to find out" | Dungeon World | You don't need to know the answer |
| Situations adapt to choices | Don't Prep Plots | Prep survives contact |
| "Ask questions, use answers" | Dungeon World | Player contributes to world |

**Gap:** The 12 moves are great but they're **Dungeon World flavored**. Nothing on adapting improv responses to different genres.

---

## Summary: What You Have vs What's Missing

### STRONG COVERAGE
- **Understanding intent** via player psychology (Robin's Laws)
- **Managing information** via clue/revelation design (Three Clue, Node-Based)
- **Running the world** via NPC agency (Don't Prep Plots)
- **Improvising** via GM moves (Dungeon World)

### PARTIAL COVERAGE - have principles, missing mechanics
- **Adjudicating actions** - know to "say yes" but not how to calibrate costs/stakes
- **Creating tension** - know about escalation but not clock mechanics or pacing math

### WEAK COVERAGE - need new material
- **Portraying the fiction** - almost nothing on description, dialogue, atmosphere, genre voice

---

## Material Recommendations by Workflow

### For Adjudicating Actions
**Need:** Decision frameworks for difficulty, stakes, costs

| Source | What It Provides |
|--------|------------------|
| **Blades in the Dark** | Position/Effect framework, consequence types, resistance |
| **[The Alexandrian - GM Don't List #20: Always Say Yes](https://thealexandrian.net/wordpress/52303/roleplaying-games/gm-dont-list-20-always-say-yes)** | Critical analysis distinguishing improv "yes-and" from RPG adjudication; GM as arbiter of fictional reality |
| **Fate Core** | Difficulty ladder, aspect invocation costs |
| **Powered by the Apocalypse essays** | "To do it, do it" in depth |

### For Creating Tension
**Need:** Clock mechanics, pacing systems, spiral prevention

| Source | What It Provides |
|--------|------------------|
| **Blades in the Dark** | Progress clocks (4/6/8), faction clocks, racing clocks |
| **[The Alexandrian - The Art of Pacing](https://thealexandrian.net/wordpress/31509/roleplaying-games/the-art-of-pacing)** | Pacing theory and practice |
| **[Campaign Mastery - Swell and Lull (Emotional Pacing)](https://www.campaignmastery.com/blog/emotional-pacing-1/)** | Emotional rhythm, upward/downward beats |
| **[The Angry GM - Keeping Pace](https://theangrygm.com/keeping-pace/)** | Scene pacing, dramatic narration |
| **Hamlet's Hit Points (Robin Laws)** | Upward/downward beat theory - "too many upward beats becomes boring, too many downward feels hopeless" |
| **[Cannibal Halfling - Pacing Problems](https://cannibalhalflinggaming.com/2022/02/09/pacing-problems/)** | Common pacing pitfalls and solutions |

### For Portraying the Fiction
**Need:** Description craft, dialogue, genre voice

| Source | What It Provides |
|--------|------------------|
| **[The Alpine DM - How to Describe a Scene](https://thealpinedm.com/how-to-describe-a-scene-easiest-way/)** | Scene as living place, including "events" in descriptions |
| **[Dawnfist - The Rule of Three](https://www.dawnfist.com/blog/gm-advice/how-to-describe-a-scene-the-rule-of-3/)** | Triadic description: sensory (sight/smell/sound) or scale (large/medium/small detail) |
| **Cyberpunk genre guides** | Prose style, atmosphere, tropes |
| **Fiction writing craft** | Description, dialogue, POV |
| **The Angry GM (various)** | Scene description, dramatic narration |

---

## The Real Gaps (Workflow-Centric View)

1. **"How do I decide if this works and what it costs?"**
   - You have "say yes" philosophy but no calibration framework
   - Need: stakes/difficulty/cost decision system

2. **"How do clocks/pressure actually work?"**
   - You mention clocks everywhere but have no clock theory
   - Need: clock mechanics, pacing math, advancement triggers

3. **"How do I actually describe things compellingly?"**
   - You have zero craft guidance for narration
   - Need: prose technique, genre voice, dialogue patterns

Everything else has solid conceptual coverage from your existing docs.

---

## Recommended Articles to Add

### Priority 1: Adjudication Framework
- [ ] **[The Alexandrian - GM Don't List #20: Always Say Yes](https://thealexandrian.net/wordpress/52303/roleplaying-games/gm-dont-list-20-always-say-yes)** — Critical nuance on when to say no
- [ ] **Blades in the Dark SRD - Position & Effect** — Concrete stakes/difficulty framework

### Priority 2: Pacing & Tension
- [ ] **[The Alexandrian - The Art of Pacing](https://thealexandrian.net/wordpress/31509/roleplaying-games/the-art-of-pacing)** — Pacing theory
- [ ] **[Campaign Mastery - Emotional Pacing series](https://www.campaignmastery.com/blog/emotional-pacing-1/)** — Swell and lull, beat rhythm
- [ ] **Blades in the Dark SRD - Progress Clocks** — Clock mechanics
- [ ] **Hamlet's Hit Points summary** — Upward/downward beat framework

### Priority 3: Description & Voice
- [ ] **[Dawnfist - Rule of Three for Descriptions](https://www.dawnfist.com/blog/gm-advice/how-to-describe-a-scene-the-rule-of-3/)** — Triadic description framework
- [ ] **[The Alpine DM - How to Describe a Scene](https://thealpinedm.com/how-to-describe-a-scene-easiest-way/)** — Scenes as living places
- [ ] **Cyberpunk/noir writing guide** — Genre-specific voice

### Nice to Have
- [ ] **[The Angry GM - Keeping Pace](https://theangrygm.com/keeping-pace/)** — Scene pacing mechanics
- [ ] **[Cannibal Halfling - Pacing Problems](https://cannibalhalflinggaming.com/2022/02/09/pacing-problems/)** — Common pitfalls
