# Perception & Observation System Design

## The Problem

A common failure mode in AI RPG systems:

1. **LLM describes unperceived things** — Narrator mentions the assassin hiding in the shadows before player has any way to know
2. **Player acts on metagame knowledge** — "I duck before the sniper shoots" when character doesn't know there's a sniper
3. **Actions reference unknown entities** — "I ask Viktor about the murder" but character doesn't know Viktor exists yet
4. **Information leakage** — Context packet includes facts the character hasn't learned

## Three Levels of Information

| Level | What It Means | Example |
|-------|---------------|---------|
| **World State** | What actually exists | There's a bomb under the car |
| **Character Knowledge** | What PC has learned | PC knows Viktor is a fixer |
| **Current Perception** | What PC can sense right now | PC can see the bartender, hear music |

The LLM should only work with **Character Knowledge ∩ Current Perception** — never raw World State.

---

## Proposed Implementation

### 1. Extend Facts Schema with Discovery Tracking

Currently facts have `visibility` but it's undefined. Define it:

```sql
-- visibility values:
-- 'world'     = exists but character doesn't know
-- 'rumored'   = character has heard about it (uncertain)
-- 'known'     = character has confirmed knowledge
-- 'witnessed' = character directly observed this

-- Add discovery tracking
ALTER TABLE facts ADD COLUMN discovered_turn INTEGER;  -- when PC learned this
ALTER TABLE facts ADD COLUMN discovery_method TEXT;    -- how they learned (seen, told, deduced)
```

### 2. Add Perception State to Scene

```sql
-- Current sensory conditions
ALTER TABLE scene ADD COLUMN visibility_conditions TEXT;  -- 'bright', 'dim', 'dark'
ALTER TABLE scene ADD COLUMN noise_level TEXT;            -- 'quiet', 'noisy', 'deafening'
ALTER TABLE scene ADD COLUMN obscured_entities_json TEXT; -- entities present but hidden
```

### 3. Context Builder: Perception Filtering

The Context Builder should have an explicit perception filtering step:

```python
def build_context(state, player_input, options):
    # Step 1: Get current scene
    scene = state.get_scene()

    # Step 2: Determine perceivable entities
    perceivable = get_perceivable_entities(
        present_entities=scene.present_entities,
        obscured_entities=scene.obscured_entities,
        visibility=scene.visibility_conditions,
        pc_capabilities=get_pc_perception_capabilities()
    )

    # Step 3: Filter facts to character knowledge
    known_facts = filter_facts(
        all_facts=state.get_facts(),
        visibility_filter=['rumored', 'known', 'witnessed'],  # exclude 'world'
        entity_filter=perceivable + get_known_entities()
    )

    # Step 4: Build packet with filtered information
    return ContextPacket(
        present_entities=perceivable,  # NOT scene.present_entities
        facts=known_facts,
        # ... etc
    )
```

### 4. Interpreter: Flag Unperceived References

Add to InterpreterOutput:

```json
{
  "intent": "...",
  "referenced_entities": ["entity_id"],
  "proposed_actions": [...],
  "perception_flags": [
    {
      "entity_id": "sniper_01",
      "issue": "not_perceived",
      "player_assumption": "Player assumes sniper exists on roof"
    }
  ]
}
```

The Interpreter prompt should instruct:
> "If the player references an entity not in the context packet, flag it as `not_perceived`. Do not assume the entity exists just because the player mentions it."

### 5. Validator: Perception Rules

Add to Validator rules:

```
## Perception Rules (v0)
- Unperceived entity check: If action targets an entity not in `present_entities`
  or `known_entities`, block with reason "Character doesn't know about X"
- Hidden entity check: If action targets an entity in `obscured_entities`,
  require a perception check or discovery action first
- Knowledge check: If action assumes a fact with visibility='world',
  block with reason "Character hasn't learned this yet"
```

### 6. Narrator: Perception Constraints

Add to Narrator prompt:

> "Only describe what the character can currently perceive. Use sensory language tied to the character's POV. Never reveal information the character couldn't know. If something important is happening out of sight, show only its effects (sounds, vibrations, reactions of others)."

---

## Perception Discovery Flow

How does a character learn things?

```
WORLD STATE (exists)
       ↓
   [Discovery Event]
       ↓
CHARACTER KNOWLEDGE (knows)
       ↓
   [Enters Scene / Uses Senses]
       ↓
CURRENT PERCEPTION (perceives now)
```

**Discovery Events:**
- Direct observation ("You see a man at the bar")
- Told by NPC ("Viktor mentions there's a fixer named Lou")
- Found evidence ("The datapad contains shipping manifests")
- Deduction ("Given X and Y, Z must be true")

**Perception Conditions:**
- Entity is present in scene
- Entity is not obscured/hidden
- Visibility conditions allow (can't see in dark without light)
- No interfering conditions (noise, crowds, etc.)

---

## Example: The Sniper Problem

**World State:**
- Sniper exists on rooftop (entity: sniper_01)
- Sniper is aiming at PC (fact: sniper_aiming, visibility='world')

**Character Knowledge:**
- PC doesn't know about sniper (no facts with sniper_01 as subject in known state)

**Player Input:** "I duck to avoid the sniper"

**Interpreter Output:**
```json
{
  "intent": "Evade sniper attack",
  "referenced_entities": ["sniper_01"],
  "perception_flags": [
    {
      "entity_id": "sniper_01",
      "issue": "not_perceived",
      "player_assumption": "Player assumes sniper on rooftop"
    }
  ]
}
```

**Validator Response:**
```json
{
  "blocked_actions": [
    {
      "action": "evade_sniper",
      "reason": "Your character doesn't know there's a sniper. What makes you think you're being targeted?"
    }
  ],
  "clarification_needed": true,
  "clarification_question": "What makes your character think they should duck?"
}
```

**Good Alternatives:**
- Player: "I have a bad feeling, I duck into cover" → Allowed (instinct/caution)
- Player: "I scan the rooftops for threats" → Triggers perception check, might reveal sniper
- GM proactively: "You catch a glint of light from a rooftop" → Now player knows

---

## Integration with Existing Systems

### Three Clue Rule Connection
The Three Clue Rule says players need multiple paths to revelations. Our perception system is the **gate** that revelations pass through:

- Revelation exists in world state (visibility='world')
- Player investigates, clue is found → visibility='known', discovery_method='found_evidence'
- Now it's in character knowledge
- Now it can appear in context packet
- Now LLM can reference it

### NPC Memory Connection
NPCs should also have perception limits:
- NPC only knows what they've witnessed/been told
- NPC can reveal info to PC (transfers fact to PC's knowledge)
- NPC might lie (creates fact with low confidence)

### Proactive Nodes Connection
Proactive nodes (things that come to the player) work through perception:
- Assassin enters scene → becomes perceivable
- But assassin might be disguised → perceivable as "stranger", not as "assassin"
- Player must discover true identity through interaction

---

## Open Questions

1. **How granular should perception be?** Per-entity? Per-fact? Per-attribute?
2. **Should PCs have perception stats?** Or is it narrative/situational only?
3. **How to handle "I search the room"?** Reveal all perceivable, or require specific searches?
4. **Passive vs active perception?** Automatically notice obvious things, roll for hidden?
5. **Memory decay?** Does character forget things over time?

---

## Minimum Viable Implementation

For v0, keep it simple:

1. **Use visibility field** — 'world' vs 'known' distinction
2. **Context Builder filters** — Only include 'known' facts
3. **Interpreter flags unknown refs** — Add perception_flags to output
4. **Validator blocks unknown targets** — Can't act on things you don't know
5. **Narrator stays in POV** — Prompt instructs first-person sensory description

More sophisticated perception (lighting, stealth, perception checks) can come later.
