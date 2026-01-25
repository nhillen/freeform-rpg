# Robin's Laws of Good Game Mastering - AI GM Extraction

**Source:** RobinsLaws.pdf (Robin D. Laws / Steve Jackson Games)

## The Great Immutable Law

> "Roleplaying games are entertainment; your goal as GM is to make your games as entertaining as possible for all participants."

> "What would be the most entertaining thing that could possibly happen, right now?"

---

## Player Types (Highly Applicable)

Understanding what the player wants is essential for AI GM to generate satisfying content.

### The Power Gamer
- Wants: Make character bigger, tougher, richer
- Sees PC as: Collection of abilities to optimize
- Emotional kick: Sense of reward
- Satisfy by: Opportunities to acquire and use cool abilities

### The Butt-Kicker
- Wants: Vicarious mayhem, proving superiority
- Sees PC as: Combat-ready vessel
- Emotional kick: Flush of martial victory
- Satisfy by: Frequent, colorful combat opportunities

### The Tactician
- Wants: Complex, realistic problems to solve
- Sees PC as: Tool for executing strategies
- Emotional kick: Feeling clever
- Satisfy by: Challenging but logical obstacles

### The Specialist
- Wants: To play their favorite archetype (ninja, knight, etc.)
- Sees PC as: Expression of beloved trope
- Emotional kick: Doing the cool things the archetype does
- Satisfy by: Scenes that showcase their defining abilities

### The Method Actor
- Wants: Strong identification with character
- Sees PC as: Medium for personal expression
- Emotional kick: Intense emotional connection through dilemmas
- Satisfy by: Situations that test or deepen personality traits

### The Storyteller
- Wants: Fun narrative that feels like a book/movie
- Sees PC as: Protagonist in an unfolding story
- Emotional kick: Participating in compelling narrative
- Satisfy by: Plot threads, rising action, satisfying arcs

### The Casual Gamer
- Wants: To hang out with friends
- Sees PC as: Required ticket to social event
- Emotional kick: Comfortable participation
- Satisfy by: Not forcing them into spotlight

**AI Implementation:**
- If player type is known, weight content toward their preferences
- If unknown, provide variety that touches multiple types
- Default assumption for solo AI play: likely Storyteller or Method Actor (they're seeking narrative experience)

---

## Adventure Structure (Applicable)

### Plot Hooks
> "A plot hook lays out a goal for the PCs, and establishes the biggest obstacle that prevents them from easily accomplishing it."

Good hooks start with a verb:
- Track down the assassins
- Recover the stolen plans
- Investigate the sightings
- Stop the villain from...

**AI Implementation:** The scenario should have a clear hook. The player should know what they're trying to do.

### Victory Conditions
> "Satisfying adventure stories have clear endings. The players must be able to tell when they have won."

**AI Implementation:** Define success states. The engine should recognize when they've been achieved.

### Don't Overcomplicate
> "You don't need to make an adventure complicated. The players will do that for you."

Players will:
- Consider multiple suspects when there's one
- Investigate every escape route
- Imagine conspiracies that don't exist

**AI Implementation:** The core scenario can be simple. Player paranoia and creativity add complexity.

---

## Structures (Reference)

### Episodic
Series of loosely connected scenes. Order is fixed but scenes are independent.
Good for: World-touring, light tone, varied encounters

### Set-Piece
3-4 major sequences connected by transitions. Player hits every set-piece but path between varies.
Good for: Cinematic adventures, guaranteed highlights

### Branching
Flowchart structure. Success/failure determines next scene.
Caution: Exponentially complex to prepare. Better to improvise branches.

### Puzzle-Piece
Situation + characters + information. Player assembles the pieces in their own order.
Good for: Mysteries, investigations

**AI Implementation:** Puzzle-piece maps best to freeform. Define the situation, let player navigate it freely.

---

## The Two Rules for Transitions

### Rule One: No Single Points of Failure
> "You never want to create a situation where the adventure grinds to a halt if the heroes blow a specific roll or make a particular mistake."

**AI Implementation:** Every critical revelation should be reachable multiple ways.

### Rule Two: Partial Success
> "Even if you give the PCs no opportunity to stop a particular bad thing from happening, you should at least give them the chance to affect the degree to which it happens."

**AI Implementation:** If players fail, they should still accomplish *something*. Wounded the villain. Delayed the ritual. Learned crucial information.

---

## Improvisation (Applicable)

### The Choice Method
When stumped, consider four options:

1. **Obvious:** What would realistically happen?
2. **Challenging:** What would most test the character's identity/goals?
3. **Surprising:** What's unexpected but believable?
4. **Pleasing:** What would the player most enjoy?

Then pick the one that feels right, or roll if stuck:
- 1-2: Obvious
- 3: Challenging
- 4: Surprising
- 5-6: Pleasing

**AI Implementation:** The Planner could use this as a framework for beat selection.

### Names and Personalities
Keep lists ready:
- 50+ setting-appropriate names
- Personality traits to grab

**AI Implementation:** Have name generators and trait lists available for instant NPC creation.

---

## Focus and Pacing (Partially Applicable)

### Good Focus Targets
- Dialogue between PCs and NPCs
- Resolution of events
- Description of people, places, events

### Bad Focus Targets
- Rules arguments (N/A for freeform)
- Dead air (AI responds immediately)
- Bookkeeping (automated)

**AI Implementation:** Most human-table pacing concerns don't apply. But the AI should:
- Keep descriptions concise
- End outputs with forward momentum
- Not get lost in exposition

---

## Concepts to Discard

### Reading the Room
Advice about watching player body language, energy levels. Not applicable to text-based AI.

### Table Management
Managing multiple players, spotlight sharing, side conversations. Solo AI play.

### Voice and Delivery
Tips for vocal variety, projection. Text medium.

### Prep Time Economics
Human constraints on preparation time. AI generates on demand.

### Rules Arguments
Managing disputes about mechanics. No mechanical system.

### Inter-Player Conflicts
Mediating between players. Single player.

---

## Key Insight for AI GM

> "The reams of material game companies produce provides but a blueprint for the real thing. The roleplaying game doesn't start until a bunch of people sit down... and wait for the GM to clear his voice."

The scenario is not the game. The game is what emerges from interaction.

The AI's job is not to execute a script but to be a responsive, entertaining partner in creating an emergent story.

---

## Power Fantasy

> "The vast majority of successful roleplaying games are power fantasies. They give players the chance to play characters vastly more competent than themselves."

> "GMs who embrace and understand [the power fantasy] tend to keep players longer than those who don't."

**AI Implementation:** Default to allowing player competence. The protagonist should feel capable, even when challenged. Failure should feel like setback, not humiliation.
