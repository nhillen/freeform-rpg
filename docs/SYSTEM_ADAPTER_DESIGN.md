# System Adapter Design

Multi-system resolution adapter. Config-driven, no class hierarchies. The `system:` block in scenario YAML is the single source of truth.

## Important: Ingest vs Runtime Separation

This document describes **runtime resolution** — how the game engine rolls dice and resolves actions during play. This is SEPARATE from the **PDF ingest pipeline** that extracts mechanical data from sourcebooks.

| Domain | Purpose | Location | System-Specific? |
|--------|---------|----------|------------------|
| **Ingest** | Extract mechanics from PDF → content pack | `src/ingest/systems_*.py` | NO — generic patterns, LLM interprets |
| **Runtime** | Resolve actions during play | `src/core/resolver.py` | YES — scenario YAML configures system |

**Don't confuse them:**
- Ingest extracts raw mechanical data without knowing the game system
- Runtime uses that data (after human review/authoring) to resolve dice rolls
- The scenario YAML `system:` block is authored, not auto-generated

See `docs/TDD.md` → "Systems Extraction Philosophy" for ingest architecture.

## Architecture

```
scenario.yaml
  └── system:
        ├── clock_rules: { ... }          # existing ClockConfig
        └── resolution_rules: { ... }     # new SystemConfig
```

`load_system_config(system_json)` reads `resolution_rules` from the scenario's `system:` block and returns a `SystemConfig` dataclass. When `resolution_rules` is absent, all values default to the existing 2d6 band system — Dead Drop works identically with zero changes.

The resolver calls `_roll_for_system(system_config, ...)` which dispatches to `_roll_2d6()` or `_roll_dice_pool()` based on `system_config.resolution.method`.

## Supported Systems

| Key | Method | Dice | Outcome Source | Status |
|-----|--------|------|----------------|--------|
| `default_2d6` | `2d6_bands` | 2d6 sum | Band thresholds (6-/7-9/10+/12) | **Implemented** |
| `mage_ascension` | `dice_pool` | Nd10 | Count successes >= difficulty | **Implemented** |

## Resolution Methods

### `2d6_bands` (default)

Roll 2d6, sum, compare to bands:
- **Failure**: 2-6
- **Mixed**: 7-9
- **Success**: 10-11
- **Critical**: 12

### `dice_pool`

Roll N d10s where N = attribute + ability (from `action_stat_map`).

1. Count dice showing >= `difficulty` (default 6).
2. If `ones_cancel_successes` is true, subtract count of 1s from successes.
3. If `threshold_past_9` is true and difficulty > 9, each point past 9 costs one additional success.
4. Map net successes to outcome via `pool_outcome_thresholds`:
   - 0 successes = failure (or botch if any 1s rolled and net successes <= 0)
   - 1 success = mixed
   - 2-3 successes = success
   - 4+ successes = critical

**Botch**: 0 net successes with any 1s rolled. Forced severity tier 2+, doubled failure effects, `action_botched` engine event.

## Mage: The Ascension Rules Reference

### Attributes (3 categories, 3 each)

| Category | Attributes |
|----------|-----------|
| Physical | Strength, Dexterity, Stamina |
| Social | Charisma, Manipulation, Appearance |
| Mental | Perception, Intelligence, Wits |

### Abilities (3 categories)

| Category | Abilities |
|----------|----------|
| Talents | Alertness, Athletics, Awareness, Brawl, Expression, Intimidation, Leadership, Streetwise, Subterfuge |
| Skills | Crafts, Drive, Etiquette, Firearms, Martial Arts, Meditation, Melee, Stealth, Survival, Technology |
| Knowledges | Academics, Computer, Cosmology, Enigmas, Investigation, Law, Linguistics, Medicine, Occult, Science |

### Special Traits

| Trait | Range | Notes |
|-------|-------|-------|
| Arete | 1-10 | Magical potency. Dice pool for magick rolls. |
| Willpower | 1-10 | Spend 1 for auto-success. Max 1 per turn. |
| Quintessence | 0-20 | Magical energy. |
| Paradox | 0-20 | Accumulated reality backlash. |

### Resolution

- **Pool**: Attribute + Ability (or Arete for magick).
- **Difficulty**: 3-9, default 6. Standard difficulties: 3 (trivial), 4 (easy), 5 (straightforward), 6 (standard), 7 (challenging), 8 (difficult), 9 (nearly impossible).
- **Success threshold**: Each die >= difficulty = 1 success. 1s cancel successes.
- **Botch**: Zero net successes with any 1s = botch (catastrophic failure).
- **Willpower**: Spend 1 Willpower for 1 automatic success. Max 1 per turn.

### Outcome Bands (dice pool)

| Net Successes | Outcome | Engine Mapping |
|---------------|---------|----------------|
| Botch (0 + 1s) | Catastrophic failure | `botch` |
| 0 | Failure | `failure` |
| 1 | Marginal success | `mixed` |
| 2-3 | Standard success | `success` |
| 4+ | Exceptional success | `critical` |

### Action-to-Stat Mapping (living table)

| Action Type | Attribute | Ability | Notes |
|-------------|-----------|---------|-------|
| sneak | Dexterity | Stealth | |
| hide | Dexterity | Stealth | |
| attack | Strength | Brawl | Melee: Strength + Melee |
| fight | Strength | Brawl | |
| shoot | Dexterity | Firearms | |
| climb | Dexterity | Athletics | |
| chase | Dexterity | Athletics | |
| flee | Dexterity | Athletics | |
| persuade | Charisma | Expression | |
| intimidate | Strength | Intimidation | |
| deceive | Manipulation | Subterfuge | |
| negotiate | Charisma | Expression | |
| hack | Intelligence | Computer | |
| steal | Dexterity | Subterfuge | |
| investigate | Perception | Investigation | |
| search | Perception | Awareness | |
| examine | Perception | Awareness | Usually auto-success |

### Not Yet Implemented

- [ ] Sphere-based magick rolls (Arete + Sphere as pool)
- [ ] Paradox accumulation and backlash
- [ ] Health levels (replaces simple Harm clock)
- [ ] Soak rolls (Stamina to reduce damage)
- [ ] Initiative system
- [ ] Extended actions (accumulate successes over turns)
- [ ] Resisted actions (contested pools)
- [ ] Specialty bonus (+1 die on specialty match)
- [ ] Merits and Flaws modifying pools
- [ ] Quintessence spending for magick

## Adding a New System

1. Define `resolution_rules` in your scenario YAML under `system:`.
2. Set `resolution.method` to `dice_pool` or `2d6_bands`.
3. Configure outcome thresholds, stat schema, action-stat mapping.
4. `load_system_config()` parses it into a `SystemConfig` dataclass.
5. The resolver dispatches automatically based on `resolution.method`.
6. If you need a new method (e.g., `d20_target`), add a `_roll_<method>()` function in `resolver.py` and a case in `_roll_for_system()`.

### Minimal YAML Example (dice pool)

```yaml
system:
  clock_rules: { ... }
  resolution_rules:
    resolution:
      method: dice_pool
      die_type: 10
      default_difficulty: 6
      ones_cancel_successes: true
      botch_on_ones: true
      pool_outcome_thresholds:
        botch: 0
        failure: 0
        mixed: 1
        success: 2
        critical: 4
    stat_schema:
      attributes:
        physical: [strength, dexterity, stamina]
        social: [charisma, manipulation, appearance]
        mental: [perception, intelligence, wits]
      abilities:
        talents: [alertness, athletics, awareness, brawl, expression, intimidation, leadership, streetwise, subterfuge]
        skills: [crafts, drive, etiquette, firearms, martial_arts, meditation, melee, stealth, survival, technology]
        knowledges: [academics, computer, cosmology, enigmas, investigation, law, linguistics, medicine, occult, science]
      special_traits:
        arete: { min: 1, max: 10 }
        willpower: { min: 1, max: 10 }
        quintessence: { min: 0, max: 20 }
        paradox: { min: 0, max: 20 }
    action_stat_map:
      sneak: { attribute: dexterity, ability: stealth }
      attack: { attribute: strength, ability: brawl }
      shoot: { attribute: dexterity, ability: firearms }
      persuade: { attribute: charisma, ability: expression }
      hack: { attribute: intelligence, ability: computer }
      investigate: { attribute: perception, ability: investigation }
      _default: { attribute: wits, ability: alertness }
    difficulty:
      default: 6
      auto_success_if_pool_gte_difficulty: false
      retry_penalty: 1
    willpower:
      enabled: true
      resource_name: willpower
      auto_successes_per_spend: 1
      max_per_turn: 1
```
