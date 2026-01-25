# Session Zero / First Session Setup Design

## The Problem

Our turn-by-turn pipeline assumes a well-structured initial state exists AND that the mechanical system (clocks, rolls, costs, consequences) is defined. Session Zero must establish both **content** (characters, NPCs, case) and **mechanics** (what system governs play).

This is the foundation that sets the tone for everything else. We need an architecture with good hooks for iteration—we don't need every detail today, but we need the right structure to evolve.

---

## Two Concerns: Content + System

| Concern | What It Covers | Examples |
|---------|----------------|----------|
| **Content** | Characters, NPCs, locations, case structure | "Viktor is a fixer who owes you a favor" |
| **System** | Mechanics, clocks, rolls, costs, consequences | "Position/Effect from Blades, 2d6 rolls" |

Both get established in Session Zero. Both should be modular and swappable.

---

## The Problem (Content)
- Player character with identity, skills, relationships
- NPCs with agendas, knowledge, relationships
- Locations with descriptions, connections, inhabitants
- A case/scenario with revelations, nodes, clues
- Clocks initialized to meaningful starting values
- Active threads with stakes

**If this initial state is poorly constructed, the entire game suffers.** Garbage in, garbage out.

This document designs the "Setup Pipeline" that runs before the first turn.

---

## Game System Architecture

### Why This Matters

The PRD mentions "clocks" and "soft checks" but doesn't define HOW they work. We could:
- Invent our own system (risky, untested)
- Adopt an existing system like Blades in the Dark (proven, but might not fit)
- Create a flexible layer that can be configured per game (best for iteration)

**Recommended:** Create a **Game System Module** that defines mechanics, loaded at Session Zero, referenced by pipeline stages.

### Game System as a Module

```python
# src/systems/base.py

class GameSystem:
    """Base class for game mechanical systems"""

    def get_clocks(self) -> List[ClockDefinition]:
        """What clocks exist and what they mean"""
        raise NotImplementedError

    def get_roll_system(self) -> RollSystem:
        """How dice/randomness works"""
        raise NotImplementedError

    def get_action_costs(self) -> CostTable:
        """What actions cost what resources"""
        raise NotImplementedError

    def get_consequence_types(self) -> List[ConsequenceType]:
        """What can go wrong and how bad"""
        raise NotImplementedError

    def get_position_effect(self) -> Optional[PositionEffectSystem]:
        """If using Position/Effect (Blades-style)"""
        return None

    def get_genre_rules(self) -> GenreContext:
        """What's possible/normal in this world"""
        raise NotImplementedError
```

### Example: Blades-Inspired System

```python
# src/systems/blades_noir.py

class BladesNoirSystem(GameSystem):

    def get_clocks(self):
        return [
            ClockDefinition(
                name="heat",
                description="Law enforcement attention",
                segments=8,
                triggers={
                    4: "Cops start asking questions",
                    6: "Active investigation",
                    8: "Raid imminent"
                }
            ),
            ClockDefinition(
                name="time",
                description="Hours until deadline",
                segments=12,
                triggers={
                    6: "Halfway - pressure mounts",
                    10: "Running out of time",
                    12: "Deadline passes - consequences"
                }
            ),
            # ... harm, cred, rep
        ]

    def get_roll_system(self):
        return RollSystem(
            dice="2d6",
            bands={
                "1-6": "failure",
                "7-9": "mixed_success",
                "10-12": "full_success"
            },
            when_to_roll="risky actions with uncertain outcomes"
        )

    def get_consequence_types(self):
        return [
            ConsequenceType("reduced_effect", "Action works, but less than hoped"),
            ConsequenceType("complication", "New problem emerges"),
            ConsequenceType("lost_opportunity", "Chance is gone"),
            ConsequenceType("worse_position", "Situation escalates"),
            ConsequenceType("harm", "Physical/mental damage", levels=4),
        ]

    def get_position_effect(self):
        return PositionEffectSystem(
            positions=["controlled", "risky", "desperate"],
            effects=["limited", "standard", "great"],
            default=("risky", "standard")
        )
```

### Example: Lighter System (No Position/Effect)

```python
# src/systems/simple_noir.py

class SimpleNoirSystem(GameSystem):

    def get_clocks(self):
        # Fewer, simpler clocks
        return [
            ClockDefinition(name="trouble", segments=6, ...),
            ClockDefinition(name="time", segments=8, ...),
        ]

    def get_roll_system(self):
        return RollSystem(
            dice="d20",
            bands={
                "1-7": "failure",
                "8-14": "mixed",
                "15-20": "success"
            }
        )

    def get_position_effect(self):
        return None  # Not using this mechanic
```

### System Loaded at Session Zero

```python
def run_setup(template_id: str, system_id: str, player_responses: dict):
    # Load the game system
    system = load_game_system(system_id)

    # Store it for pipeline stages to reference
    config.set_game_system(system)

    # Initialize clocks based on system definitions
    for clock_def in system.get_clocks():
        db.insert_clock(
            name=clock_def.name,
            value=clock_def.starting_value,
            max=clock_def.segments,
            triggers=clock_def.triggers
        )

    # Store genre rules for context injection
    db.insert_genre_context(system.get_genre_rules())

    # ... continue with content setup
```

### Pipeline Stages Reference System

```python
# src/core/validator.py

class Validator:
    def validate(self, interpreter_output, state):
        system = config.get_game_system()

        # Use system's cost table
        costs = system.get_action_costs()
        action_cost = costs.lookup(interpreter_output.action_type)

        # Use system's position/effect if available
        if system.get_position_effect():
            position = self.assess_position(interpreter_output, state)
            # ...

# src/core/resolver.py

class Resolver:
    def resolve(self, state, validator_output, planner_output):
        system = config.get_game_system()

        # Use system's roll mechanics
        if self.needs_roll(validator_output):
            roll_system = system.get_roll_system()
            result = roll_system.roll()
            outcome = roll_system.interpret(result)

        # Apply consequences from system's consequence types
        if outcome == "mixed_success":
            consequence = self.pick_consequence(system.get_consequence_types())
```

### Configuration File Format

```yaml
# systems/blades_noir.yaml
id: blades_noir
name: "Blades-Inspired Cyberpunk Noir"
description: "Position/Effect mechanics with progress clocks"

clocks:
  - name: heat
    segments: 8
    starting_value: 1
    description: "Law enforcement and faction attention"
    triggers:
      4: "Cops start asking questions in the district"
      6: "Active investigation opened"
      8: "Task force mobilized, raid imminent"

  - name: time
    segments: 12
    starting_value: 8
    description: "Hours until case deadline"
    countdown: true  # decrements rather than increments
    triggers:
      4: "Dawn approaches, options narrowing"
      2: "Final hours, desperation"
      0: "Deadline passed"

  - name: harm
    segments: 4
    starting_value: 0
    description: "Physical and mental damage"
    levels:
      1: "Lesser (bruised, shaken)"
      2: "Moderate (bleeding, rattled)"
      3: "Severe (broken, traumatized)"
      4: "Fatal/Incapacitated"

  - name: cred
    type: resource  # not a clock, just a number
    starting_value: 500
    description: "Street currency and favors"

  - name: rep
    segments: 5
    starting_value: 2
    description: "Reputation in the underworld"
    bidirectional: true  # can go up or down

rolls:
  dice: "2d6"
  bands:
    failure: [2, 6]
    mixed: [7, 9]
    success: [10, 12]
  critical: 12
  when_to_roll: "When outcome is uncertain and stakes exist"

position_effect:
  enabled: true
  positions:
    controlled:
      description: "You have advantage, can withdraw safely"
      failure_consequence: "You don't get what you want, but no worse"
    risky:
      description: "Standard situation, could go either way"
      failure_consequence: "You suffer a consequence"
    desperate:
      description: "Serious danger, high stakes"
      failure_consequence: "Serious consequence, situation worsens"
  effects:
    limited: "Partial progress, 1-2 ticks on clock"
    standard: "Expected progress, 2-3 ticks"
    great: "Exceptional progress, 4-5 ticks"
  trading: true  # can trade position for effect

consequences:
  - type: reduced_effect
    description: "Action works but less effectively than hoped"
  - type: complication
    description: "New problem emerges (heat +1, alarm triggered, etc.)"
  - type: lost_opportunity
    description: "The chance is gone, approach is burned"
  - type: worse_position
    description: "Situation escalates to more dangerous"
  - type: harm
    description: "Physical or mental damage"
    uses_harm_clock: true

action_costs:
  # Default costs for action categories
  violence:
    heat: 1
    description: "Violence attracts attention"
  social:
    time: 1
    description: "Talking takes time"
  investigation:
    time: 1
    description: "Research takes time"
  travel:
    time: 1
    description: "Moving around takes time"
  crime:
    heat: 2
    description: "Illegal acts are risky"

genre_rules:
  setting: "Cyberpunk noir"
  technology: "Near-future, cybernetics common, AR/VR ubiquitous"
  society: "Megacorp dominated, vast inequality, street-level survival"
  tone: "Morally ambiguous, fatalistic, neon-lit shadows"
  themes:
    - "Technology as tool and trap"
    - "Corporate power vs individual agency"
    - "Identity in a synthetic age"
  what_works:
    - "Street smarts and connections"
    - "Information as currency"
    - "Creative use of technology"
  what_doesnt:
    - "Frontal assaults on corps"
    - "Trusting authorities"
    - "Clean solutions"
```

### Hooks for Iteration

The system module approach gives us:

1. **Swap systems easily** — Try Blades-style, then simpler, compare
2. **A/B test mechanics** — Run same scenario with different roll systems
3. **Tune without code changes** — Edit YAML, reload
4. **Mix and match** — Use Blades clocks but simpler consequences
5. **Add mechanics incrementally** — Start minimal, add Position/Effect later

### What Needs Definition (Can Iterate Later)

| Component | v0 Approach | Can Evolve To |
|-----------|-------------|---------------|
| **Clocks** | 5 simple clocks, linear triggers | Faction clocks, racing clocks, complex triggers |
| **Rolls** | 2d6 bands | Position/Effect, advantage/disadvantage, modifiers |
| **Costs** | Fixed per action type | Situational costs, negotiable costs |
| **Consequences** | Basic list | Resistance mechanics, lasting effects |
| **Genre Rules** | Static text | Dynamic adaptation based on play |

---

## What Session Zero Must Establish (Content)

Based on traditional RPG best practices and our v0 scope:

### 1. World Context (Genre Rules)
- **Genre conventions**: What's normal in this world?
- **Tone**: Gritty? Cinematic? Dark? Hopeful?
- **Technology/magic rules**: What's possible?
- **Social structures**: Who has power? How does society work?

*For v0 cyberpunk noir:* Megacorps rule, street-level crime is endemic, technology is ubiquitous but unequally distributed, moral ambiguity is the norm.

### 2. Player Character
- **Identity**: Name, background, current situation
- **Capabilities**: What are they good at? What are their limits?
- **Relationships**: Who do they know? Who owes them? Who do they owe?
- **Goal**: What do they want? What drives them?
- **Vulnerabilities**: What can hurt them? What do they care about?

### 3. Starting Situation
- **Inciting incident**: What kicks off the case?
- **Initial location**: Where does the player start?
- **Immediate context**: What just happened? What's about to happen?
- **Available information**: What does the player character already know?

### 4. NPCs with Agendas
For each significant NPC:
- **Identity**: Name, role, appearance
- **Agenda**: What do they want? What are they willing to do?
- **Resources**: What do they have? What can they offer/threaten?
- **Knowledge**: What do they know? What secrets do they hold?
- **Relationship to PC**: How do they feel? History?
- **Trigger conditions**: When do they act proactively?

### 5. Case/Scenario Structure
- **The revelation list**: What truths can the player discover?
- **The node map**: Where/who can they investigate?
- **Clue distribution**: Which nodes contain which clues?
- **Proactive elements**: What comes looking for the player?
- **Resolution conditions**: How can this end?

### 6. Clock Initialization
- **Heat**: Starting police/faction attention (usually low)
- **Time**: How much time pressure exists?
- **Cred**: Starting resources/money
- **Harm**: Starting health (usually full)
- **Rep**: Starting reputation in relevant communities

### 7. Active Threads
- **Main thread**: The primary case/goal
- **Side threads**: Secondary concerns, complications
- **Stakes**: What happens if threads resolve well/poorly?

---

## Design Options

### Option A: Template-Based Setup
Pre-authored scenario files (YAML/JSON) that define all initial state.

**Pros:**
- Predictable, tested starting points
- Fast to start playing
- Quality controlled

**Cons:**
- Not personalized
- Limited variety without many templates
- Player has no input into world

**Implementation:**
```
src/scenarios/
  cyberpunk_noir_case_01.yaml
  cyberpunk_noir_case_02.yaml
```

### Option B: Guided Wizard
Series of questions/prompts where player makes choices.

**Pros:**
- Player investment in character/world
- Personalized experience
- Teaches player about the world

**Cons:**
- Takes time before playing
- Requires good question design
- Can feel like a chore

**Implementation:**
```
Setup Pipeline:
1. Choose character archetype (or answer questions)
2. Name and customize
3. Define one key relationship
4. Choose starting hook
5. Confirm and generate full state
```

### Option C: AI-Assisted Generation
Collaborative creation where AI proposes, player approves/modifies.

**Pros:**
- Fast iteration on ideas
- Handles complexity
- Can generate NPCs, locations, clues coherently

**Cons:**
- Needs careful constraints to stay coherent
- Risk of generic/random content
- May not match player's vision

**Implementation:**
```
1. Player provides preferences (3-5 sentences)
2. AI generates character + situation
3. Player approves or requests changes
4. AI expands to full NPC/location set
5. AI generates case structure
6. Final review and commit
```

### Option D: Hybrid (Recommended)
Template provides structure + constraints, AI fills details, player customizes.

**Pros:**
- Quality controlled structure
- Personalized details
- Efficient workflow
- Coherent results

**Cons:**
- More complex to implement

**Implementation:**
```
1. Load scenario template (structure, locations, factions)
2. Player answers 5-7 key questions (character, motivation)
3. AI generates character details from answers
4. AI populates NPCs based on template roles + character relationships
5. AI distributes clues/revelations per template structure
6. Player reviews key elements, can adjust
7. Commit initial state
```

---

## Recommended Architecture: Setup Pipeline

### Phase 0: System Selection
**Input:** System ID or player preferences
**Output:** Loaded game system module

```python
# Either explicit selection
system = load_game_system("blades_noir")

# Or inferred from scenario template
system = scenario.default_system

# Or player chooses
system = prompt_system_choice([
    ("blades_noir", "Blades-style with Position/Effect"),
    ("simple_noir", "Simpler mechanics, faster play"),
    ("freeform", "Minimal mechanics, narrative focus")
])
```

The system is loaded first because it affects:
- What clocks get initialized
- What questions to ask in character creation
- How costs/consequences work throughout play

### Phase 1: Scenario Selection
**Input:** Template ID or player preferences
**Output:** Loaded scenario skeleton

```python
class ScenarioTemplate:
    genre_rules: GenreContext
    locations: List[LocationSkeleton]  # Names, types, connections
    factions: List[FactionSkeleton]    # Names, types, general goals
    npc_roles: List[NPCRole]           # "The Fixer", "The Victim", "The Villain"
    thread_structure: ThreadSkeleton   # Main + side thread templates
    clock_defaults: Dict[str, int]     # Starting clock values
    revelation_structure: List[RevelationSkeleton]  # What can be discovered
```

### Phase 2: Character Creation
**Input:** Player answers to character questions
**Output:** Player character entity + initial relationships

**Key Questions (5-7):**
1. What's your name and what do you do? (identity)
2. What's one thing you're really good at? (capability)
3. What's your biggest vulnerability or weakness? (vulnerability)
4. Who's someone you trust? (relationship seed)
5. Who's someone you owe or who's after you? (tension seed)
6. What do you want more than anything? (motivation)
7. What line won't you cross? (moral boundary)

**AI Task:** Generate full character entity from sparse answers, maintaining consistency.

### Phase 3: NPC Population
**Input:** Character details + NPC role skeletons
**Output:** Fully realized NPCs with agendas

For each NPC role in template:
1. Generate identity (name, appearance, mannerisms)
2. Generate agenda based on role + faction
3. Determine relationship to PC based on character answers
4. Assign knowledge (what revelations they know about)
5. Define proactive triggers

**AI Task:** Create coherent NPCs that connect to character's stated relationships.

### Phase 4: Case Structure Generation
**Input:** Revelation structure + populated NPCs + locations
**Output:** Clue distribution, node connections

1. Assign each revelation to 3+ nodes (Three Clue Rule)
2. Create clue objects with discovery conditions
3. Link NPCs to locations
4. Set up proactive node triggers
5. Define resolution paths

**AI Task:** Ensure redundancy, avoid chokepoints, create interesting paths.

### Phase 5: State Initialization
**Input:** All generated content
**Output:** Populated database tables

```python
def initialize_game_state(scenario, character, npcs, case):
    # Create all entities
    for entity in [character] + npcs + locations + items:
        db.insert_entity(entity)

    # Create facts with proper visibility
    for fact in world_facts:
        fact.visibility = 'known' if player_knows(fact) else 'world'
        db.insert_fact(fact)

    # Initialize clocks
    for clock_name, value in scenario.clock_defaults.items():
        db.insert_clock(clock_name, value)

    # Create threads
    db.insert_thread(main_thread)
    for side_thread in side_threads:
        db.insert_thread(side_thread)

    # Set initial scene
    db.insert_scene(starting_location, present_entities)

    # Create initial relationships
    for rel in character_relationships + npc_relationships:
        db.insert_relationship(rel)
```

### Phase 6: Validation & Confirmation
**Input:** Complete initial state
**Output:** Approved state or revision requests

**Checks:**
- Every revelation reachable via 3+ paths
- No orphaned entities (everyone connected to something)
- Clocks in valid ranges
- Relationships are bidirectional
- Player character has clear starting context

**Player Review:**
- Show character summary
- Show key relationships
- Show starting situation
- Allow minor adjustments

---

## Setup Pipeline Module Design

```python
# src/setup/pipeline.py

class SetupPipeline:
    def __init__(self, llm_gateway, state_store, prompt_registry):
        self.llm = llm_gateway
        self.db = state_store
        self.prompts = prompt_registry

    def run_setup(
        self,
        system_id: str,
        template_id: str,
        player_responses: dict
    ) -> SetupResult:
        # Phase 0: Load game system
        system = self.load_system(system_id)
        self.db.store_system_config(system)

        # Phase 1: Load template
        template = self.load_template(template_id)

        # Phase 2: Create character
        character = self.create_character(template, player_responses, system)

        # Phase 3: Populate NPCs
        npcs = self.populate_npcs(template, character)

        # Phase 4: Generate case structure
        case = self.generate_case(template, character, npcs)

        # Phase 5: Initialize state (uses system for clocks, costs)
        self.initialize_state(system, template, character, npcs, case)

        # Phase 6: Validate
        issues = self.validate_state()

        return SetupResult(
            system=system,
            character=character,
            summary=self.generate_summary(),
            issues=issues
        )

    def load_system(self, system_id: str) -> GameSystem:
        """Load game system from YAML config"""
        config_path = f"systems/{system_id}.yaml"
        return GameSystem.from_yaml(config_path)
```

---

## Setup Prompts Needed

### Character Generation Prompt
```
You are creating a player character for a cyberpunk noir RPG.

PLAYER RESPONSES:
{{player_responses}}

GENRE CONTEXT:
{{genre_rules}}

Generate a complete character including:
- Full name and street name/alias
- Background (2-3 sentences)
- Current situation
- Key skills and capabilities
- Vulnerabilities and limitations
- Defining personality traits

Ensure the character fits the player's stated preferences while grounding
them in the cyberpunk noir genre.

OUTPUT JSON:
{{character_schema}}
```

### NPC Generation Prompt
```
You are populating NPCs for a cyberpunk noir case.

PLAYER CHARACTER:
{{character_summary}}

NPC ROLE: {{npc_role}}
FACTION: {{faction}}
LOCATION: {{primary_location}}

PLAYER RELATIONSHIP SEEDS:
{{relationship_seeds}}

Generate an NPC including:
- Name and appearance
- Personality and mannerisms
- Agenda (what they want, what they'll do to get it)
- Knowledge (what secrets they know)
- Relationship to player character
- Proactive triggers (when they act without player prompting)

The NPC should feel authentic to the genre and connected to the player's story.

OUTPUT JSON:
{{npc_schema}}
```

### Case Structure Prompt
```
You are designing the mystery structure for a cyberpunk noir case.

MAIN REVELATION: {{main_truth}}
SECONDARY REVELATIONS: {{secondary_truths}}

AVAILABLE NODES:
- Locations: {{locations}}
- NPCs: {{npcs}}
- Items: {{items}}

For each revelation, assign 3+ clues across different nodes.
Ensure no single node is required (redundancy).
Create at least one proactive path (something comes to the player).

OUTPUT JSON:
{{case_structure_schema}}
```

---

## Scenario Template Format (v0)

```yaml
# scenarios/cyberpunk_noir_case_01.yaml
id: cyberpunk_noir_case_01
name: "Dead Drop"
genre: cyberpunk_noir
estimated_length: "2-4 hours"

genre_rules:
  technology_level: "near-future, cybernetics common"
  social_structure: "megacorp dominated, street-level survival"
  tone: "gritty noir, moral ambiguity, neon and shadow"
  common_elements:
    - "Corporate espionage"
    - "Street-level crime"
    - "Cybernetic enhancement"
    - "Information as currency"

locations:
  - id: bar_neon_dragon
    name: "The Neon Dragon"
    type: bar
    description_seed: "Dive bar in the Undercity, neutral ground"
    connections: [street_undercity, back_alley]
  - id: street_undercity
    name: "Undercity Streets"
    type: street
    description_seed: "Rain-slicked streets, neon signs, crowds"
  # ... more locations

factions:
  - id: yakuza_local
    name: "Jade Serpent Syndicate"
    type: organized_crime
    general_goal: "Control Undercity vice trade"
  - id: megacorp_zenith
    name: "Zenith Industries"
    type: megacorporation
    general_goal: "Suppress damaging information"
  # ... more factions

npc_roles:
  - role: the_client
    faction: null
    location: bar_neon_dragon
    relationship_to_pc: "approaches with job"
  - role: the_fixer
    faction: null
    location: bar_neon_dragon
    relationship_to_pc: "player defined"
  - role: the_victim
    faction: megacorp_zenith
    location: null  # dead
    relationship_to_pc: "connection to case"
  # ... more roles

thread_structure:
  main:
    title_template: "Find out who killed {{victim}}"
    stakes: "Justice, payment, survival"
  side:
    - title_template: "{{fixer}} needs a favor"
      stakes: "Relationship, future work"
    - title_template: "{{faction}} is watching"
      stakes: "Heat, territory"

clock_defaults:
  heat: 1
  time: 8  # out of 12 (hours until deadline)
  cred: 500
  harm: 0
  rep: 2  # out of 5

revelation_structure:
  - id: who_killed_victim
    type: core
    description: "The identity of the killer"
  - id: why_victim_died
    type: core
    description: "The motive behind the murder"
  - id: what_victim_knew
    type: supporting
    description: "The secret the victim discovered"
  - id: faction_involvement
    type: supporting
    description: "Which faction is behind this"
  # ... more revelations
```

---

## Integration with Turn Pipeline

After setup completes:

1. **Context Builder** has populated entities, facts, scene
2. **Memory anchors** are set (character identity, goal, key relationships)
3. **Genre rules** are stored for injection into prompts
4. **First turn** begins with inciting incident narration

The setup pipeline **outputs to the same state store** that the turn pipeline reads from.

```
Setup Pipeline → State Store ← Turn Pipeline
                     ↓
              [entities, facts, scene,
               threads, clocks, relationships]
```

---

## Open Questions

### Content Questions
1. **How interactive should NPC generation be?**
   - Show player each NPC for approval?
   - Or just key NPCs (fixer, main antagonist)?

2. **Should player choose scenario template or just preferences?**
   - "Play Dead Drop" vs "I want a noir mystery"

3. **Procedural vs authored content ratio?**
   - More authored = higher quality, less variety
   - More procedural = more variety, risk of incoherence

### System Questions
4. **Should players choose/customize game system?**
   - Pick from presets vs adjust individual mechanics?
   - How much complexity to expose?

5. **How to handle mid-game system adjustments?**
   - Player finds clocks too punishing
   - Can we tune without breaking state?

6. **Pre-built systems vs custom?**
   - Start with Blades-inspired, PbtA-inspired, Fate-inspired?
   - Or build our own minimal system?

### Infrastructure Questions
7. **How to handle replay/restart?**
   - Reset to post-setup state?
   - Re-run setup with same/different choices?

8. **Multiple characters?**
   - v0 is single player, but architecture should allow future multi-PC

---

## Summary: Hooks for Iteration

The key architectural decisions that enable iteration:

### 1. System as Data, Not Code
Game mechanics defined in YAML, not hardcoded. Change rules by editing config.

```
systems/
  blades_noir.yaml      # Full Blades-style
  simple_noir.yaml      # Minimal mechanics
  freeform.yaml         # Almost no mechanics
  experimental_v2.yaml  # Testing new ideas
```

### 2. System Loaded at Setup, Referenced Throughout
Pipeline stages don't hardcode mechanics—they ask the system module.

```python
# Resolver doesn't know how rolls work—it asks
roll_system = config.get_game_system().get_roll_system()
result = roll_system.roll_and_interpret()
```

### 3. Clear Boundaries Between Concerns
- **System** = mechanics (clocks, rolls, costs)
- **Template** = structure (locations, NPC roles, case shape)
- **Content** = specifics (this character, this NPC, this clue)

Each can be swapped independently.

### 4. Progressive Complexity
Start with minimal system, add mechanics as needed:

| Phase | What's Active |
|-------|---------------|
| v0.1 | Simple clocks, no rolls, fixed costs |
| v0.2 | Add 2d6 rolls for risky actions |
| v0.3 | Add Position/Effect layer |
| v0.4 | Add resistance/stress mechanics |
| v1.0 | Full Blades-style or custom evolved |

### 5. A/B Testing Built In
```python
# Run same scenario with different systems
result_a = run_game(system="blades_noir", template="dead_drop")
result_b = run_game(system="simple_noir", template="dead_drop")
compare_metrics(result_a, result_b)
```

This architecture means we can:
- Start simple and add complexity based on what works
- Test different mechanical approaches empirically
- Let the player experience guide system design
- Never be locked into a system that doesn't fit
