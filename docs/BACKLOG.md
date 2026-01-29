# Implementation Backlog

Open issues, technical debt, and planned improvements. Items are grouped by area and priority.

**Legend**: 🔴 Blocking / High Priority | 🟡 Medium Priority | 🟢 Low Priority / Nice-to-Have

---

## Ingest Pipeline — Remaining Work

System extraction configs are now implemented (`systems/_base.yaml`, `systems/world_of_darkness.yaml`). See `docs/TDD.md` → "System Extraction Configuration" for usage.

### Schema Fixes (High Priority)

LLM sometimes returns `null` for required integer/string fields, causing validation failures:

| Priority | Extractor | Issue | Fix |
|----------|-----------|-------|-----|
| 🔴 | `stat_schema` | `None is not of type 'integer'` | Make integer fields nullable in schema or add defaults |
| 🔴 | `health` | `None is not of type 'string'` | Make string fields nullable in schema |
| 🔴 | `magic` | `None is not of type 'string'` | Make string fields nullable in schema |

### Polish Items (Medium Priority)

| Priority | Item | Description |
|----------|------|-------------|
| 🟡 | `review-guidance` command | Interactive CLI for reviewing universal GM guidance candidates |
| 🟡 | Low-confidence warnings | Alert when extractions have < 70% confidence |
| 🟡 | Pack override testing | Test with `extraction.yaml` in a content pack |

### Technical Debt (Low Priority)

| Priority | File | Issue | Recommended Fix |
|----------|------|-------|-----------------|
| 🟢 | `src/ingest/sphere_extract.py` | Hardcoded Mage sphere names in `find_sphere_page_ranges()` | Rename to `ranked_abilities_extract.py`, use config patterns |
| 🟢 | `src/ingest/systems_refine.py` | Only refines 2 of 9 extractors (`magic`, `stat_schema`) | Expand LLM refinement to all extractors |

### Future System Configs (Low Priority)

Additional system configs for other game families:

| Config | Game Family | Status |
|--------|-------------|--------|
| `world_of_darkness.yaml` | WoD (Vampire, Werewolf, Mage) | ✅ Implemented |
| `pbta.yaml` | Powered by the Apocalypse | Not started |
| `osr.yaml` | Old School Revival | Not started |
| `dnd5e.yaml` | D&D 5th Edition | Not started |

---

## System Adapter — Mage: The Ascension

The dice pool resolution system is implemented, but several Mage-specific mechanics are not yet supported.

See `docs/SYSTEM_ADAPTER_DESIGN.md` → "Not Yet Implemented" for context.

| Priority | Feature | Description | Complexity |
|----------|---------|-------------|------------|
| 🟡 | Sphere-based magick rolls | Arete + Sphere as pool instead of Attribute + Ability | Medium |
| 🟡 | Health levels | Replace simple Harm clock with 7-level health track + penalties | Medium |
| 🟡 | Soak rolls | Stamina roll to reduce incoming damage | Low |
| 🟢 | Paradox accumulation | Track Paradox points, trigger backlash at thresholds | Medium |
| 🟢 | Extended actions | Accumulate successes over multiple turns | Medium |
| 🟢 | Resisted actions | Contested pools (attacker vs defender) | Medium |
| 🟢 | Initiative system | Turn order for multi-combatant scenes | Medium |
| 🟢 | Specialty bonus | +1 die when action matches character specialty | Low |
| 🟢 | Merits and Flaws | Pool modifiers from character traits | Low |
| 🟢 | Quintessence spending | Spend Quintessence for magick effects | Low |

---

## Documentation — Stale Content

| Priority | File | Issue |
|----------|------|-------|
| 🟢 | `docs/IMPLEMENTATION_PLAN.md` | Stale - references things as "not built" that are now complete. Archive or delete. |
| 🟢 | `docs/FINAL_AUDIT.md` | Review for staleness |
| 🟢 | `docs/GM_GUIDANCE_GAPS.md` | Review for staleness |

---

## v2 Roadmap (Not Started)

From `docs/PRD.md` → "v2 scope". These are planned features, not bugs.

| Feature | Description |
|---------|-------------|
| Multi-pack loading | Load multiple content packs simultaneously with layering/priority |
| Pack conflict resolution | Handle same entity defined in multiple packs |
| Cross-pack entity references | Namespaced IDs across packs |
| Unified cross-pack index | Single retrieval index with provenance metadata |
| License metadata | Pack manifest with publisher info, SKU, license type |

---

## v3 Roadmap (Not Started)

From `docs/PRD.md` → "v3 scope". Shared evolving worlds.

| Feature | Description |
|---------|-------------|
| World-level state layer | Shared canonical entities/facts separate from campaign state |
| World ticker | Between-session process that extracts macro consequences |
| Event propagation | Campaign events tagged as world-affecting consumed by ticker |
| Conflict resolution | Handle contradictory world events from concurrent campaigns |
| Emergent history as RAG | Auto-generated world history documents from play |
| Fact promotion | Campaign-discovered facts promoted to shared world truth |

---

## How to Use This Document

**Adding issues**: Add new rows to the appropriate section with priority tag.

**Claiming work**: Move item to "In Progress" section (add below) with your name and date.

**Completing work**: Remove from backlog, ensure relevant docs are updated.

### In Progress

_None currently._

### Recently Completed

| Date | Item | Notes |
|------|------|-------|
| 2026-01-29 | System extraction config inheritance | `_base.yaml` → `world_of_darkness.yaml` with `deep_merge()` |
| 2026-01-29 | GM guidance extraction | New stage extracts storytelling advice to `storytelling/` |
| 2026-01-29 | Draft mode with review markers | `--draft` flag, `REVIEW_NEEDED.md`, `promote-draft` command |
| 2026-01-29 | `--system-hint` CLI flag | Apply system-specific patterns during ingest |
| 2026-01-29 | `list-systems` CLI command | List available system configs |
| 2026-01-29 | Confidence scoring | All extractors report confidence in `extraction_report.json` |
| 2026-01-29 | `_extract_equipment()` generic structural detection | Replaced hardcoded weapon names with table/stat pattern detection |
| 2026-01-29 | `_extract_health()` generic structural detection | Replaced hardcoded health levels with penalty ladder detection |
| 2026-01-29 | Ingest pipeline philosophy documentation | Added to CLAUDE.md, TDD.md, SYSTEM_ADAPTER_DESIGN.md |
| 2026-01-29 | Documentation migration/cleanup | Slimmed CLAUDE.md, updated USAGE.md with missing commands |
