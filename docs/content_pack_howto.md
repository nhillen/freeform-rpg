# Content Pack Authoring Guide

This guide covers how to build content packs — world sourcebooks that provide deep background knowledge to the AI narrator through RAG retrieval.

## What Is a Content Pack?

A content pack is the equivalent of a tabletop RPG sourcebook. It provides lore, atmosphere, NPC backstories, faction profiles, cultural details, and discoverable secrets that the narrator can draw on during play.

Content packs are **immutable reference material**. The game engine never modifies pack content. During play, relevant sections are retrieved and injected into the narrator's context, giving it the depth of knowledge a prepared GM would have.

**Without content packs**, the engine works fine — it runs on scenario data alone. Content packs add richness and consistency to the world beyond what a scenario can carry in its YAML.

## Directory Structure

A content pack is a directory with a `pack.yaml` manifest and markdown files organized by type:

```
my_pack/
  pack.yaml                    # Required: manifest
  locations/                   # Location lore
    tavern.md
    marketplace.md
  npcs/                        # NPC backstories and profiles
    bartender.md
    merchant.md
  factions/                    # Organizations, corporations, guilds
    thieves_guild.md
  culture/                     # World culture, customs, slang
    street_life.md
  items/                       # Notable items, equipment, artifacts
    ancient_sword.md
```

The directory names determine the content type:

| Directory    | Content Type | Lore Category        |
|-------------|-------------|----------------------|
| `locations/` | `location`  | `atmosphere`          |
| `npcs/`      | `npc`       | `npc_briefings`       |
| `factions/`  | `faction`   | `thread_connections`  |
| `culture/`   | `culture`   | `atmosphere`          |
| `items/`     | `item`      | `discoverable`        |

Files in the root directory (next to `pack.yaml`) are treated as `general` type and categorized under `atmosphere`.

## pack.yaml Manifest

The manifest describes the pack and is the only required file.

```yaml
# Required fields
id: my_pack              # Unique identifier (snake_case, no spaces)
name: "My Content Pack"  # Human-readable name

# Optional fields
version: "1.0"           # Semantic version
description: "A sourcebook for my campaign world."
layer: adventure         # Content layer (see below)
author: "Your Name"
tags:
  - fantasy
  - mystery
dependencies: []         # IDs of packs this one requires
metadata:                # Arbitrary key-value pairs
  genre: fantasy
  scenario_id: quest_one
```

### Layer Values

The `layer` field describes the scope of the content:

| Layer        | Description                                    |
|-------------|------------------------------------------------|
| `world`     | Foundational world lore (geography, physics, history) |
| `setting`   | Regional/era-specific detail                    |
| `adventure` | Scenario-specific locations, NPCs, factions     |

Most packs will be `adventure` layer. The layer is metadata for organization — it doesn't affect retrieval behavior.

## Writing Content Files

Each content file is a markdown document with YAML frontmatter.

### Frontmatter Schema

```yaml
---
title: "The Rusty Anchor"       # Required: display title
type: location                   # Required: content type
entity_id: rusty_anchor          # Optional: maps to scenario entity ID
entity_refs:                     # Optional: entity IDs this content references
  - rusty_anchor
  - captain_ward
tags:                            # Optional: retrieval tags
  - tavern
  - waterfront
  - social
---
```

| Field        | Required | Description                                      |
|-------------|----------|--------------------------------------------------|
| `title`     | Yes      | Human-readable name                               |
| `type`      | Yes      | Content type: `location`, `npc`, `faction`, `culture`, `item` |
| `entity_id` | No       | Links this file to a scenario entity by ID         |
| `entity_refs`| No      | Entity IDs referenced in this content (used for retrieval matching) |
| `tags`      | No       | Retrieval tags for keyword matching                |

### Markdown Body

The body uses standard markdown with a specific header hierarchy:

```markdown
# The Rusty Anchor

Overview paragraph about this location. This becomes the "overview" chunk.

## Atmosphere

Detailed description of the atmosphere, sights, sounds, smells.
This is a good place for sensory details the narrator can weave
into scene descriptions.

## Regular Patrons

Description of who frequents this place. Names, roles, habits.
The narrator uses this to populate scenes naturally.

### The Captain's Table

Sub-sections (H3+) merge into their parent H2 chunk.
This content stays with "Regular Patrons" above.

## Secrets

Hidden information that might surface during investigation.
The narrator can reveal this when players actively look for clues.
```

## Chunking Rules

Understanding how content is split into chunks helps you write for optimal retrieval.

**Header hierarchy:**
- **H1 (`#`)**: Becomes the "overview" chunk for the file. Keep it brief (1-2 paragraphs). It provides context when the H2 sections are retrieved.
- **H2 (`##`)**: Primary split boundary. Each H2 section becomes its own chunk. This is the main unit of retrieval.
- **H3+ (`###`, `####`)**: Merged into their parent H2 chunk. Use these for sub-structure within a section.

**Target section size**: Aim for 200-500 words per H2 section. Sections under 100 words may lack enough context for the narrator. Sections over 600 words consume too much of the token budget when retrieved.

**Chunk IDs**: Automatically generated as `{pack_id}:{filename}:{section_slug}`. For example: `dead_drop_lore:neon_dragon:atmosphere`.

**Token estimates**: Roughly 1.33 tokens per word. A 400-word section uses about 530 tokens. The default retrieval budget is 2000 tokens, so 3-4 sections typically fit in a single scene's lore context.

## Metadata Best Practices

Good metadata drives good retrieval. Here's how to optimize:

### Entity References

Always list `entity_refs` in frontmatter for content that relates to specific game entities. The retriever uses entity refs for direct lookup — if the entity is in the scene, its lore gets found.

```yaml
entity_refs:
  - neon_dragon        # This location
  - viktor             # NPC who is often here
  - zenith_industries  # Faction connected to this place
```

### Tags

Tags feed into FTS5 keyword search. Use tags that match likely search queries:

```yaml
tags:
  - crime_scene        # What this place is
  - undercity          # Where it is
  - investigation      # What players might do here
```

### Common Pitfalls

1. **Missing entity_refs**: If an NPC file doesn't list the NPC's entity_id in `entity_refs`, the retriever won't find it by entity lookup. Always include at least the file's own entity.

2. **Overly long sections**: A single H2 section of 1000+ words will consume most of the token budget, crowding out other relevant lore. Split into multiple H2s.

3. **Too many small files**: A file with only 50 words of content produces thin chunks that lack context. Combine related thin content into a single file.

4. **Generic tags**: Tags like `important` or `content` don't help retrieval. Use specific, searchable terms.

5. **No overview chunk**: Skipping the H1 section means the file has no overview context. Always include at least a sentence under H1.

## CLI Workflow

### Installing a Pack

```bash
# Install a content pack into your game database
freeform-rpg --db game.db install-pack path/to/my_pack

# Output shows indexing stats:
#   Installed content pack: My Content Pack
#   ID: my_pack
#   Version: 1.0
#   Layer: adventure
#   Files: 5
#   Chunks indexed: 18
#   FTS5 indexed: 18
#   Vector indexed: 0
```

### Listing Installed Packs

```bash
freeform-rpg --db game.db list-packs

# Output:
#   Installed Content Packs (1):
#   --------------------------------------------------
#     my_pack: My Content Pack v1.0
#       Layer: adventure, Chunks: 18
#       A sourcebook for my campaign world.
```

### Playing with Packs

Scenarios declare which content packs they use via the `content_packs` field in the scenario YAML. When a scenario is loaded, the engine builds a **lore manifest** — a pre-computed mapping of scenario entity IDs to relevant pack chunks. This means known entities get instant lore lookup during play without re-querying the pack.

```yaml
# In your scenario YAML
content_packs:
  - undercity_sourcebook
  - cyberpunk_setting
```

Lore is retrieved automatically at scene transitions and NPC introductions. Revisiting a location uses cached lore instead of re-fetching.

```bash
# Install packs first, then play
freeform-rpg --db game.db install-pack content_packs/undercity_sourcebook
freeform-rpg --db game.db --campaign my_campaign play
```

## Testing Your Pack

After installing, verify that retrieval returns expected results.

### Validation

The pack loader validates structure on install. Common issues:

- Missing `pack.yaml` → error
- Missing `id` or `name` in manifest → error
- Content files without frontmatter → warning (parsed as general type)
- Unknown directory names → files treated as general type

### Write Integration Tests

Create a test that loads, indexes, and queries your pack:

```python
from src.content.pack_loader import PackLoader
from src.content.chunker import Chunker
from src.content.indexer import LoreIndexer
from src.content.retriever import LoreRetriever, LoreQuery

# Load and index
loader = PackLoader()
manifest, files = loader.load_pack("path/to/my_pack")
chunks = Chunker().chunk_files(files, manifest.id)
indexer = LoreIndexer(state_store)
indexer.index_pack(manifest, chunks)

# Test retrieval
retriever = LoreRetriever(state_store)

# Does searching for a location return its lore?
result = retriever.retrieve_for_scene(
    scene_state={"location_id": "rusty_anchor"},
    active_threads=[],
    campaign_id="test",
    pack_ids=["my_pack"],
)
assert len(result.chunks) > 0

# Does searching for an NPC return their backstory?
result = retriever.retrieve_for_entity("captain_ward", pack_ids=["my_pack"])
assert len(result.chunks) > 0
```

### Check What Surfaces

Use the debug panel during play (`/debug` command) to see the `lore_context` field in the context packet. This shows exactly what lore the narrator received for the current scene.

## Connecting to Scenarios

Content packs and scenarios are complementary:

- **Scenario YAML** defines mechanical state: entities, clocks, threads, facts, starting scene
- **Content pack** provides deep lore: backstories, atmosphere, discoverable secrets, cultural context

They connect through shared entity IDs. If your scenario has an entity `id: viktor`, your content pack's NPC file should have `entity_id: viktor` and `entity_refs: [viktor]` in its frontmatter.

```
Scenario (dead_drop.yaml)           Content Pack (undercity_sourcebook/)
  content_packs:                      npcs/
    - undercity_sourcebook              viktor.md (entity_id: viktor)
  entities:                           locations/
    - id: viktor  ←──────────────→      neon_dragon.md (entity_id: neon_dragon)
    - id: neon_dragon  ←──────────→
```

At scenario load time, the engine scans the declared packs and builds a **lore manifest** — a mapping of `entity_id → [chunk_ids]`. During play, this manifest provides instant lookups for known entities. FTS5 keyword search handles dynamic queries for entities the scenario didn't anticipate.

A single scenario can reference multiple content packs (e.g., a world pack + a setting pack). A single content pack can be used across multiple scenarios.

## Quick Reference

### Frontmatter Fields

| Field        | Type       | Default    | Description                     |
|-------------|-----------|------------|----------------------------------|
| `title`     | string    | (required) | Display name                     |
| `type`      | string    | (required) | `location`, `npc`, `faction`, `culture`, `item` |
| `entity_id` | string    | `""`       | Scenario entity this maps to     |
| `entity_refs`| string[] | `[]`       | All entities referenced           |
| `tags`      | string[]  | `[]`       | Retrieval keywords                |

### Valid Content Types

| Type       | Directory    | Lore Category        | Use For                        |
|-----------|-------------|----------------------|-------------------------------|
| `location`| `locations/` | `atmosphere`          | Places, buildings, areas       |
| `npc`     | `npcs/`      | `npc_briefings`       | Character profiles, backstories |
| `faction` | `factions/`  | `thread_connections`  | Organizations, companies        |
| `culture` | `culture/`   | `atmosphere`          | Customs, slang, daily life      |
| `item`    | `items/`     | `discoverable`        | Artifacts, equipment, clues     |
| `general` | (root)       | `atmosphere`          | Everything else                 |

### Tag Conventions

| Category    | Example Tags                           |
|------------|----------------------------------------|
| Location   | `tavern`, `undercity`, `crime_scene`    |
| Faction    | `corporate`, `criminal`, `government`   |
| Theme      | `investigation`, `social`, `combat`     |
| Region     | `waterfront`, `upper_city`, `market`    |
| Narrative  | `key_npc`, `antagonist`, `ally`         |

### pack.yaml Template

```yaml
id: my_pack_id
name: "My Pack Name"
version: "1.0"
description: "Brief description of what this pack covers."
layer: adventure
author: "Author Name"
tags:
  - genre_tag
  - theme_tag
dependencies: []
metadata:
  genre: genre_name
  scenario_id: related_scenario
```
