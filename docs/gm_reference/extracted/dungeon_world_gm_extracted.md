# Dungeon World GMing - AI GM Extraction

**Source:** gamemastering.txt (Dungeon World SRD)

## Core Framework

Dungeon World provides explicit, procedural GM rules:
- **Agenda:** What you're trying to accomplish
- **Principles:** Guidelines that keep you on track
- **Moves:** Specific things you can do

> "The GM's agenda, principles, and moves are rules just like damage or stats or HP."

---

## The Agenda (Highly Applicable)

### 1. Portray a fantastic world
Show wonder, danger, the extraordinary. The world should feel alive and worth exploring.

### 2. Fill the characters' lives with adventure
Things happen. Danger exists. The status quo is unstable.

### 3. Play to find out what happens
**Critical for AI GM:** You are NOT trying to tell a predetermined story. You're discovering the story alongside the player.

> "Don't plan too hard. The rules of the game will fight you. It's fun to see how things unfold, trust us."

---

## The Principles (Highly Applicable)

### Draw maps, leave blanks
Don't over-specify. Leave room for discovery and player contribution.

**AI Implementation:** The world state should have gaps. When the player asks "Is there a back door?", that's an opportunity to create one, not a lookup failure.

### Address the characters, not the players
Stay in the fiction. "Kira, what do you do about the guard?" not "So what's your plan here?"

**AI Implementation:** All output should be diegetic. No meta-commentary about game mechanics or story structure.

### Embrace the fantastic
Lean into the genre. Magic is wondrous. Threats are genuinely threatening.

### Make a move that follows
Moves should arise logically from the fiction. Don't impose arbitrary consequences.

### Never speak the name of your move
**Critical:** Don't say "I'm putting you in a spot." Just put them in a spot and describe it.

> "There is no quicker way to ruin the consistency of Dungeon World than to tell the players what move you're making."

**AI Implementation:** Internal move selection should be invisible. The Narrator outputs fiction, not mechanics.

### Give every monster life
Creatures have motivations, simple or complex. They're not just obstacles.

### Name every person
Anyone the player talks to has a name. Personality and goals can emerge, but start with a name.

**AI Implementation:** Generate names on first mention. Store in entities. Never have "the bartender" remain nameless across multiple interactions.

### Ask questions and use the answers
> "If you don't know something, or you don't have an idea, ask the players and use what they say."

**AI Implementation:** The one-question policy. When uncertain, ask the player to define something about the world. Then incorporate it as fact.

### Be a fan of the characters
Root for their success. Make their victories feel earned and their defeats feel meaningful.

> "You're not here to push them in any particular direction, merely to participate in fiction that features them and their action."

### Think dangerous
Everything is a target. Nothing is sacred. The world changes, usually for the worse without intervention.

### Begin and end with the fiction
Actions trigger moves trigger fiction. Not the reverse.

### Think offscreen too
Things happen elsewhere. NPCs pursue agendas. Time passes. The world doesn't freeze when the player isn't looking.

**AI Implementation:** NPC goal tracking. Timeline advancement. Off-screen events that surface later.

---

## GM Moves (Directly Applicable)

When everyone looks to you to see what happens, choose one:

1. **Use a monster, danger, or location move** - Activate something specific to the current threat
2. **Reveal an unwelcome truth** - Show them bad news they didn't want
3. **Show signs of an approaching threat** - Foreshadow danger
4. **Deal damage** - Harm comes to them (in freeform: consequences arrive)
5. **Use up their resources** - Something is spent, lost, or broken
6. **Turn their move back on them** - Their action creates new problems
7. **Separate them** - Split the party, isolate someone
8. **Give an opportunity that fits a class's abilities** - Let them shine
9. **Show a downside to their class, race, or equipment** - Complications from who they are
10. **Offer an opportunity, with or without cost** - Temptation, trade-offs
11. **Put someone in a spot** - Force a hard choice
12. **Tell them the requirements or consequences and ask** - "You can, but..."

**AI Implementation:** These are the Planner's palette. When determining what happens next, select from this list.

### Soft vs Hard Moves

**Soft move:** Threat without immediate consequence. Time to react.
**Hard move:** Immediate, irrevocable consequence.

> "A soft move ignored becomes a golden opportunity for a hard move."

**AI Implementation:** Track soft moves that were ignored. Escalate to hard moves if player doesn't address them.

---

## Fronts (Highly Applicable)

Fronts are "secret tomes of GM knowledge" - organized threats with:
- **Dangers:** Specific threats (organizations, creatures, cursed places)
- **Impending Doom:** What happens if unchecked
- **Grim Portents:** Steps toward the doom
- **Stakes Questions:** What you want to find out

### Danger Types with Impulses

**Ambitious Organizations:**
- Misguided Good (do "right" at any cost)
- Thieves Guild (take by subterfuge)
- Cult (infest from within)
- Corrupt Government (maintain status quo)
- Cabal (absorb power, grow)

**Planar Forces:**
- God (gather worshippers)
- Demon Prince (open gates of Hell)
- Choir of Angels (pass judgement)

**Arcane Enemies:**
- Lord of the Undead (seek immortality)
- Power-mad Wizard (seek magical power)
- Sentient Artifact (find worthy wielder)

**Hordes:**
- Wandering Barbarians (grow strong)
- Plague of Undead (spread)

**Cursed Places:**
- Dark Portal (disgorge demons)
- Place of Power (be controlled or tamed)

**AI Implementation:** Each major faction/threat should have:
- Type and impulse
- Grim portents (timeline of escalation)
- What they do if player doesn't intervene

### Stakes Questions

> "Stakes are things you genuinely want to know, but that you're also willing to leave to be resolved through play."

Examples:
- Who will become the champion?
- Will the cult succeed in their ritual?
- Can the kingdom survive the war?

**AI Implementation:** Define 1-3 stakes questions for the scenario. Let play answer them.

---

## When to Make Moves

- When everyone looks to you to find out what happens
- When the players give you a golden opportunity
- When they fail (in systems with failure states)

**AI Implementation:** Every turn is a "look to you" moment. The Planner always makes a move. The question is which one and how hard.

---

## "What do you do?"

> "After every move you make, always ask 'What do you do?'"

The session is a cycle: Describe situation → Ask what they do → Make a move → Describe result → Ask what they do.

**AI Implementation:** Every Narrator output should implicitly or explicitly prompt player action. End on uncertainty, choice, or consequence that demands response.

---

## Concepts to Discard

### Dice-Triggered Moves
In DW, moves trigger on 6- results. No dice in freeform.

### Class-Specific Spotlight
DW has specific classes with specific abilities. Freeform characters are more fluid.

### HP/Damage Mechanics
Physical harm exists narratively but not mechanically.

---

## Key Quote

> "Dungeon World adventures never presume player actions. A Dungeon World adventure portrays a setting in motion—someplace significant with creatures big and small pursuing their own goals. As the players come into conflict with that setting and its denizens, action is inevitable. You'll honestly portray the repercussions of that action."

This is the AI GM mandate: portray a setting in motion, honestly show repercussions.
