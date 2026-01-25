# Node-Based Scenario Design - AI GM Extraction

**Source:** node_based.txt, secret_life_of_nopdes.txt (The Alexandrian)

## Core Concept

Nodes are "points of interest" - places the PCs can go and interact with, where they find information pointing to other nodes.

**Types of Nodes:**
- Locations
- Characters/People
- Organizations
- Events
- Activities (rare)

---

## Highly Applicable Concepts

### 1. The Inverted Three Clue Rule

> "If the PCs have access to ANY three clues, they will reach at least ONE conclusion."

**AI Implementation:** Design scenarios where each node contains clues pointing to 2-3 other nodes. The player can navigate freely through the web, always having *somewhere* to go.

### 2. Proactive Nodes

> "Proactive nodes come looking for the PCs."

These are the "response teams" - entities that take action toward the player rather than waiting to be found.

**AI Implementation:**
- Tag certain entities as "proactive"
- Give them triggers: "If PCs investigate X, this NPC acts"
- Use them to re-inject momentum when players stall

Examples:
- Assassin sent when PCs get too close
- Informant who reaches out when they hear PCs are asking questions
- Event that happens on a timeline regardless of PC action

### 3. Push vs Pull

**Pull:** Player wants to explore/experience the node (reward, opportunity, curiosity)
**Push:** Player is forced to engage (attack, deadline, necessity)

**AI Implementation:** Balance both. Too much pull = player paralysis (too many options). Too much push = player feels railroaded.

Clocks serve as push mechanisms: "The ritual completes at midnight whether you're there or not."

### 4. Fractal Node Design

Nodes can contain nodes. A city is a node containing district nodes containing building nodes containing room nodes.

> "You can 'zoom in' on a node and break it apart into more nodes. Or you can 'zoom out' and discover it's all just ONE node in a much larger web."

**AI Implementation:** The scene/location system should support this naturally. "The Docks" is a node. "The warehouse on pier 7" is a sub-node. "The hidden basement" is a sub-sub-node.

### 5. Node Navigation Methods

- **Clues:** Information pointing to other nodes
- **Geography:** Physical proximity/connection
- **Temporal:** Events happening at specific times
- **Random:** Chance encounters
- **Proactive:** Nodes that come to the player
- **Player-initiated:** Players invent their own intermediate nodes

**AI Implementation:** The Planner should consider all these when determining what happens next. Not just "where do clues point?" but also "what's nearby? what's happening now? who would seek out the player?"

### 6. Dead Ends Are Okay

> "In a node-based structure, dead ends aren't a problem: This lead may not have panned out, but the PCs will still have other clues to follow."

**AI Implementation:** Not every investigation thread needs to pay off. Some contacts don't know anything useful. Some locations are empty. This is realistic and fine, as long as other paths exist.

---

## Scenario Structures

### Basic Loop (4 nodes)
Each node has 3 clues pointing to the other 3 nodes. Player can enter anywhere, visit in any order.

### Funnel Structure
Layers of nodes, each layer funneling toward a "gateway" node that opens the next layer.

Good for: Escalating stakes, power progression, managing scope.

### Layer Cake
Each node in a layer points to same-layer nodes AND one node in the next layer. Movement between layers is fluid.

### Conclusion Structure
Multiple nodes all pointing toward a final "boss" node. Player explores freely then converges on climax.

---

## The Revelation List

Track separately:
1. **Node list:** Places/people/events the player can visit
2. **Revelation list:** Conclusions the player needs to reach

These overlap but aren't identical. "Bob is the killer" is a revelation. "Bob's apartment" is a node. The node might contain clues to multiple revelations.

**AI Implementation:**
- Entities table = nodes (people, places)
- Facts table = revelations and clues
- Revelation tracking = which facts the player has discovered

---

## Proactive Node Triggers

From the essay, example triggers for proactive nodes:
- Monitoring location X (spot PCs investigating)
- Sent to kill target Y (while PCs are talking to Y)
- Staking out nodes A, B, or C
- Notified by ally if they become aware of PCs
- Respond to violence in area within 1d6+10 minutes
- Random encounter while traveling

**AI Implementation:** Each proactive entity should have a trigger list. The Planner checks triggers each turn.

---

## Managing Complexity

> "Working memory capacity for most adults is in the range of 7 +/- 2 objects."

If you have more than ~7 active nodes, chunk them into groups.

**AI Implementation:** The Context Builder must be selective. Don't dump all 20 NPCs into context. Group by relevance:
- Currently present entities
- Recently mentioned entities
- Entities related to current thread
- Background entities (summarized)

---

## Concepts That Need Adaptation

### Campaign-Scale Node Maps

The essays discuss multi-session campaigns with 40+ scenarios as nodes.

**AI Adaptation:** For a single-case game (2-4 hours), the node map is smaller but the principles apply. Maybe 5-8 major nodes with sub-nodes.

### Physical Prep Materials

Discussion of binders, numbered keys, revelation lists on paper.

**AI Adaptation:** This maps to database schema. The entities/facts tables ARE the revelation list. The system tracks discovery automatically.

---

## Concepts to Discard

### Hexcrawl-Specific Mechanics

Discussion of random encounter density in hex exploration.

### Dungeon Geography as Navigation

Physical mapping of rooms/doors. Less relevant to narrative-focused freeform.

---

## Key Implementation Insight

> "Once I came to see scenes as an emergent property of game play (rather than something that's prepared), I began to realize that scenario prep is almost entirely about designing tools. Or, perhaps more accurately, toys."

The AI should think of entities as *toys to play with*, not *scripts to execute*.

The player says what they do. The AI picks up the relevant toys and plays with them in response.
