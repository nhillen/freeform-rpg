# PRD: Freeform RPG Engine v0

## Overview
A freeform, chat-first, genre-flexible narrative RPG engine with continuity, real constraints, and consequences. v0 is a single playable case (initial case: cyberpunk noir) with strong GM-like pacing and voice.

## Product goals
- Feel like a good GM: continuity, fair pushback, momentum, strong voice.
- Fast iteration: run and replay turns quickly, swap prompt versions, diff outputs.
- Flexible direction: keep a stable core while allowing inspiration-driven changes without losing progress.

## Non-goals (v0)
- Deep tactical combat.
- Large open world or travel simulation.
- Procedural city generation beyond authored locations.
- Fully autonomous self-modifying prompts.

## Design principles
- Consequences are real and tracked (clocks, inventory, location).
- Clarify rarely; default to conservative outcomes.
- Voice is consistent with the chosen setting (v0 case uses neon-noir cyberpunk).
- Engine is authoritative; LLM narrates from given facts only.
- Core state is stable while prompts and policies are swappable.

## v0 scope
- One case (2 to 4 hours) in a compact setting (initial case: cyberpunk district).
- 3 to 5 locations, 6 to 10 NPCs, 3 factions.
- One main thread, 2 to 3 side threads.
- 10 to 20 key items and info objects.

## Core mechanics
- Clocks: Heat, Time, Cred, Harm, Rep.
- Tags on entities and facts for retrieval.
- Optional soft checks (2d6 or d20 bands) used sparingly.
- Hard constraints: inventory, presence, location, time.
- Loop: player input -> interpret -> validate -> plan -> resolve -> narrate -> commit.

## Target users
- Players who want narrative freedom with meaningful consequences.
- Developers who need a fast iteration loop for prompts and rules.

## User stories
- As a player, I can attempt any action and get a believable outcome or pushback.
- As a player, I can rely on the game to remember people, places, and promises.
- As a developer, I can replay a transcript with a new prompt and compare outputs.
- As a developer, I can see context packets and state diffs per turn.

## Functional requirements (v0)
- Turn orchestrator executes passes in order and logs all artifacts.
- State store (SQLite) is canonical and an append-only event log is kept.
- Context packet builder is entity/thread/clock aware and capped.
- LLM gateway uses structured outputs, validates schema, retries on errors.
- Prompt registry stores versioned prompt templates and pins per campaign.
- Validator enforces presence, location, inventory, and contradiction checks.
- Resolver applies clock deltas, rolls, and emits engine events.
- Narrator uses context + engine events only; no new facts.
- Commit writes event record, applies state diff, updates summaries.
- Orchestrator supports swapping prompts and optional passes without breaking state.

## Dev experience requirements (v0)
- Show context packet per turn.
- Show state diff per turn.
- Rerun last turn with prompt version X.
- Rerun last N turns.
- Flag output (too permissive, contradiction, boring, stalled).
- Prompt version list and per-campaign pinning.
- Optional: side-by-side narrator diff, basic contradiction detection.

## Data model (high level)
- entities, facts, scene, threads, clocks, inventory, relationships, events, summaries.

## Metrics and success criteria
- After 60 to 120 turns: continuity errors are rare.
- Invalid actions get believable pushback or cost.
- Clocks create rising tension without feeling gamey.
- Voice remains consistent and scenes move forward.
- Dev loop: single-turn replay under a few seconds, with usable diffs.

## Decisions (v0)
- Initial LLM provider: Claude via gateway adapter.
- UI form factor: CLI-first for fast iteration; thin web UI is optional later.

## Risks and mitigations
- Hallucinated facts: enforce validator and narrator constraints, use schema validation.
- Stalling via clarifications: strict 1-question rule with conservative default.
- Slow iteration: cache context packets, keep replay lightweight, minimal UI.
- Overfitting to one prompt: prompt registry and replay harness to compare versions.
- Scope creep: lock v0 to single case and authored locations.

## Open questions
- Target response length range per turn.
- Whether the initial case should stay cyberpunk for v0 or rotate to another setting.
- **Authored scenarios vs. full procedural generation**: Are pre-authored scenario YAML files (locations, NPCs, items, threads) worth the effort, or should the engine generate everything from a short premise each session? Authored scenarios have repeatability but limited replay value. Procedural generation is unique each time but harder to quality-control. A possible middle ground: authored "scenario seeds" (tone, theme, a few key NPCs/constraints) that the engine expands at runtime. Tradeable/shareable scenario packs could have value if they define enough structure to be interesting without being rigid. Needs playtesting to evaluate.
