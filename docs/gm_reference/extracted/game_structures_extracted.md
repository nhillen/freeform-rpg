# Game Structures - AI GM Extraction

**Source:** game_structures.txt (The Alexandrian)

## Core Insight

Every game needs to answer two questions:
1. **What do the characters do?** (The fictional activity)
2. **How do the players do it?** (The mechanical/procedural layer)

> "These questions might seem deceptively simple, but the answers are complex."

---

## The Abstraction Problem

Example that reveals the hidden structure question:

> Player: "I want to explore the dungeon."
> GM: "Okay, make a Dungeoneering check."
> Player: "I succeed."
> GM: "Okay, you kill a tribe of goblins and emerge with 546 gp in loot."

This is technically valid but feels wrong. The "game structure" was collapsed to a single roll.

**AI Relevance:** In freeform narrative, we don't have dice, but we still need to decide *at what level of abstraction* to engage with player actions.

---

## Default Assumption Trap

Most GM advice assumes one particular structure (usually dungeoncrawl or mystery) without acknowledging it.

> "Given the exact same setting and the exact same game system, [PCs] could just as easily be monarchs, dragons, farmers, magical researchers, planar travelers, gods, military masterminds..."

**AI Implementation:** The scenario should define what structure is in play. A noir investigation has different rhythms than a heist, which differs from survival.

---

## Structure Categories (Summarized from full essay)

### Dungeoncrawl
- What they do: Explore dangerous location, overcome obstacles, extract loot
- How: Room-by-room navigation, encounter resolution

### Hexcrawl
- What they do: Explore wilderness, discover points of interest
- How: Hex-by-hex travel, random encounters, resource management

### Mystery
- What they do: Gather clues, reach conclusions
- How: Node-based investigation, revelation tracking

### Heist
- What they do: Plan and execute complex infiltration/theft
- How: Preparation phase → Execution phase → Complication handling

### Intrigue/Politics
- What they do: Navigate social relationships, advance faction goals
- How: Relationship tracking, reputation systems, faction turns

---

## Applicable Insight: Default Structure for Freeform

For a cyberpunk noir investigation (the v0 target):

**What they do:**
- Investigate a case
- Navigate dangerous social landscape
- Make choices with consequences

**How they do it:**
- Scene-based narrative
- Node navigation (locations, people)
- Clock-based time pressure
- Consequence tracking via facts

This is essentially a **puzzle-piece mystery** structure with **noir genre conventions**.

---

## Structure as Pacing Tool

Different structures create different rhythms:

- Dungeoncrawl: Constant low-level tension, frequent small encounters
- Mystery: Rising tension, breakthrough moments, climactic reveal
- Heist: Preparation calm → Execution intensity → Resolution
- Horror: Creeping dread, sudden spikes, resource depletion

**AI Implementation:** The Planner should understand what phase of the structure we're in and pace accordingly.

For noir mystery:
- Early: Establish atmosphere, introduce cast, plant hooks
- Middle: Complications, dead ends, escalating danger
- Late: Threads converge, hard choices, resolution

---

## Concepts Partially Applicable

### "The Skilled Play Question"

> "What does skilled play look like in this structure?"

In a dungeoncrawl, skilled play = resource management, tactical positioning
In a mystery, skilled play = connecting clues, asking right questions
In intrigue, skilled play = reading NPCs, leveraging relationships

**AI Implementation:** The engine should recognize and reward structure-appropriate skilled play. In the investigation, clever questioning should yield information.

---

## Concepts to Discard

### Board Game Comparisons
Extended discussion of how board games handle structures. Not directly relevant.

### Mechanical Resolution Systems
Discussion of dice pools, skill checks, etc. Freeform doesn't use these.

### Multi-Player Coordination
How different players interact with structure simultaneously. Solo AI play.

---

## Key Takeaway

> "One of the most overlooked aspects in the design and play of traditional roleplaying games is the underlying game structure."

The AI can't just respond to player input in a vacuum. It needs to know what *kind* of game it's running and what rhythms/patterns that implies.

For the freeform RPG engine:
- Define structure type per scenario
- Structure informs Planner decisions about pacing and tension
- Structure informs what constitutes "progress" vs "spinning wheels"
