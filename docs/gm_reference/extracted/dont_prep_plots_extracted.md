# Don't Prep Plots - AI GM Extraction

**Source:** dont_prep_plots.txt (The Alexandrian)

## Core Insight: Situations vs Plots

The fundamental distinction is between **plots** (predetermined sequences of events) and **situations** (circumstances that generate events based on player actions).

**For AI GM:** This is the foundational philosophy. The AI should maintain a living situation state, not try to railroad toward predetermined story beats.

---

## Highly Applicable Concepts

### 1. Situation-Based State
Instead of: "The PCs will go to the derelict, fight the monster, rescue the survivor, then go to the temple..."

Maintain: "The derelict is floating at coordinates X. The monster killed the crew except one survivor. The villains are at the Temple assuming cover identities."

**AI Implementation:** The game state (entities, facts, scene) represents the *situation*. The narrative emerges from player interaction with that situation.

### 2. Goal-Oriented Opponents
> "Instead of trying to second-guess what your PCs will do, simply ask yourself: 'What is the bad guy trying to do?'"

**AI Implementation:** Each NPC/faction should have:
- Current objective
- Resources to achieve it
- Timeline if uninterrupted

The Planner pass should consider NPC agendas, not just react to player actions.

### 3. The Toolkit Concept
NPCs are "tools" the GM can deploy. Know what each tool is useful for:
- Personnel (who can be sent, questioned, bribed)
- Locations (where action can happen)
- Information (what can be revealed)
- Equipment/resources

**AI Implementation:** Entity tags and relationships should encode "what is this useful for" - not just static facts.

### 4. Non-Specific Contingency Planning
> "You're giving yourself a hammer and saying, 'if the players give me anything that looks like a nail, I know what I can hit it with.'"

**AI Implementation:** Don't try to enumerate every possible player action. Instead, understand each entity's capabilities and let the Narrator match them to player-created situations.

---

## Concepts That Need Adaptation

### Robust Design via Redundancy
The essay discusses having multiple paths to success. In tabletop, this compensates for missed clues or bad rolls.

**AI Adaptation:** Without dice, "robustness" means:
- Multiple NPCs who know key information
- Multiple ways to reach important locations
- Facts that can be discovered through different approaches

The AI doesn't need to "fail" to find something, but the player might not think to look - so redundancy in the world state is still valuable.

---

## Concepts to Discard

### Prep Time Economics
The essay argues situation-based design requires *less* prep than plotting. This is a human GM concern about limited time. The AI doesn't have prep time constraints.

### "Waste" of Unused Content
> "If the PCs don't interfere at point X, then all the time you spent prepping contingency X2 is completely wasted."

The AI can generate content on demand. "Wasted prep" isn't a concern.

---

## Key Quotes for Prompt Design

> "Your gaming session is not a story — it is a happening. It is something about which stories can be told, but in the genesis of the moment it is not a tale being told. It is a fact that is transpiring."

> "Situation-based design is like handing the players a map and then saying 'figure out where you're going'. Plot-based design is like handing the players a map on which a specific route has been marked with invisible ink… and then requiring them to follow that invisible path."

> "The magical creativity which only happens when people get together."

---

## Implementation Notes

The core loop should be:
1. Player states intent
2. AI evaluates intent against *situation state*
3. AI determines what *would happen* given that situation
4. AI narrates the outcome
5. Situation state updates

NOT:
1. Player states intent
2. AI checks if intent matches expected plot
3. AI steers player toward predetermined outcome
