# Three Clue Rule - AI GM Extraction

**Source:** three_clue.txt (The Alexandrian)

## Core Principle

> "For any conclusion you want the PCs to make, include at least three clues."

The theory: Players will miss the first clue, ignore the second, and misinterpret the third before making an incredible leap of logic that gets them where you wanted.

---

## Highly Applicable Concepts

### 1. Redundancy in Information Design

**AI Implementation:** When seeding the world with discoverable information:
- Each important revelation should be reachable via 3+ different paths
- Different NPCs should know overlapping information
- Physical evidence, testimony, and deduction should all point to the same conclusions

This should be encoded in the Facts table - multiple facts with different subjects but pointing to the same revelation.

### 2. The Revelation List

> "List each conclusion you want the players to reach. Under each conclusion, list every clue that might lead them to that conclusion."

**AI Implementation:** The Context Builder should track:
- What major revelations exist in the scenario
- Which clues for each revelation the player has encountered
- Which remain undiscovered

This enables the system to recognize when a player is "stuck" (has seen few clues) vs "should be able to figure it out" (has seen multiple clues).

### 3. Permissive Clue-Finding

> "If the players come up with a clever approach to their investigation, you should be open to the idea of giving them useful information as a result."

**AI Implementation:** The Interpreter should be generous in recognizing player actions that *could* yield information, even if not explicitly designed. If a player does something clever, the Validator/Planner should look for ways to reward it with information.

### 4. Proactive Clues (Bash Them on the Head)

> "The bad guy finds out they're investigating and sends someone to kill them or bribe them."
> "Somebody else dies."
> "The next part of the bad guy's plan happens."

**AI Implementation:** When players are stuck, the system should escalate NPC agendas. This creates new scenes with new clues organically. The engine should track "time since progress" and trigger NPC actions accordingly.

---

## Concepts That Need Adaptation

### Chokepoint Problems

In tabletop, a "chokepoint" is a problem that MUST be solved for the adventure to continue. The essay advises having 3 solutions for every chokepoint.

**AI Adaptation:** In freeform narrative, hard chokepoints are less common. But the principle applies: if the player *needs* information X to proceed meaningfully, ensure X is available through multiple channels.

### Skill Checks as Failure Points

The original context discusses Search checks, Perception rolls, etc. as failure points.

**AI Adaptation:** Without dice, "failure" is narrative. A player might:
- Not think to look somewhere
- Fail to ask the right questions
- Leave before searching thoroughly

The AI should track what information was *available* in a scene vs what was *discovered*, enabling proactive delivery of missed clues later.

---

## Concepts to Discard

### Mechanical Failure States

> "The players could fail to search the room... fail the skill check to identify [the clue]..."

Without mechanical systems, these specific failure modes don't apply.

### Red Herrings Warning

The essay warns against red herrings because players already create enough confusion on their own.

**AI Note:** In AI-GMed games, the AI might accidentally create "red herrings" through inconsistent narration. The Narrator should be constrained to only narrate from validated facts to prevent this.

---

## Key Insight for Freeform AI

The essay identifies **four chokepoints** in a typical clue:
1. Finding the clue
2. Recognizing its importance
3. Correctly interpreting it
4. Making the right deduction

In freeform play, #1 and #2 are the main concerns. The AI should:
- Make clues findable through obvious investigation
- Signal when something is noteworthy ("You notice something odd...")
- Let the player do the interpretation (this is the fun part)

---

## Implementation: The Inverted Three Clue Rule

From node_based design:

> "If the PCs have access to ANY three clues, they will reach at least ONE conclusion."

**AI Implementation:** Track total clues discovered across all threads. If >= 3 clues exist pointing to different nodes/revelations, the player has enough information to make *some* progress, even if not on the "main" path.

---

## Revelation Tracking Schema

Suggested data structure for tracking revelations:

```
Revelation:
  - id: "killer_identity"
  - description: "Marcus is the killer"
  - clues_available: ["bloody_knife", "witness_testimony", "motive_letter", "alibi_hole"]
  - clues_discovered: ["witness_testimony"]
  - is_revealed: false
```

When clues_discovered >= 3, strongly consider having an NPC or event surface the revelation if the player hasn't connected the dots.
