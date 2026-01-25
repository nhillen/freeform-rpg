# Session Zero / First Session Setup Design

## The Problem

Our turn-by-turn pipeline assumes a well-structured initial state exists:
- Player character with identity, skills, relationships
- NPCs with agendas, knowledge, relationships
- Locations with descriptions, connections, inhabitants
- A case/scenario with revelations, nodes, clues
- Clocks initialized to meaningful starting values
- Active threads with stakes

**If this initial state is poorly constructed, the entire game suffers.** Garbage in, garbage out.

This document designs the "Setup Pipeline" that runs before the first turn.

---

## What Session Zero Must Establish

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

    def run_setup(self, template_id: str, player_responses: dict) -> SetupResult:
        # Phase 1: Load template
        template = self.load_template(template_id)

        # Phase 2: Create character
        character = self.create_character(template, player_responses)

        # Phase 3: Populate NPCs
        npcs = self.populate_npcs(template, character)

        # Phase 4: Generate case structure
        case = self.generate_case(template, character, npcs)

        # Phase 5: Initialize state
        self.initialize_state(template, character, npcs, case)

        # Phase 6: Validate
        issues = self.validate_state()

        return SetupResult(
            character=character,
            summary=self.generate_summary(),
            issues=issues
        )
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

1. **How interactive should NPC generation be?**
   - Show player each NPC for approval?
   - Or just key NPCs (fixer, main antagonist)?

2. **Should player choose scenario template or just preferences?**
   - "Play Dead Drop" vs "I want a noir mystery"

3. **How to handle replay/restart?**
   - Reset to post-setup state?
   - Re-run setup with same/different choices?

4. **Multiple characters?**
   - v0 is single player, but architecture should allow future multi-PC

5. **Procedural vs authored content ratio?**
   - More authored = higher quality, less variety
   - More procedural = more variety, risk of incoherence
