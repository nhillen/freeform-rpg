# Implementation Backlog

Open issues, technical debt, and planned improvements. Items are grouped by area and priority.

**Legend**: 🔴 Blocking / High Priority | 🟡 Medium Priority | 🟢 Low Priority / Nice-to-Have

---

## Ingest Pipeline — Technical Debt

The systems extraction pipeline has hardcoded patterns that violate the "generic structural detection" principle. These work for WoD/Mage but will fail on other game systems.

See `docs/TDD.md` → "Systems Extraction Philosophy" for the target architecture.

| Priority | File | Issue | Recommended Fix |
|----------|------|-------|-----------------|
| 🟡 | `src/ingest/sphere_extract.py` | Hardcoded Mage sphere names in `find_sphere_page_ranges()` | Rename to `ranked_abilities_extract.py`, detect "section header + ranked bullets (•)" generically |
| 🟢 | `src/ingest/systems_refine.py` | Only refines 2 of 9 extractors (`magic`, `stat_schema`) | Expand LLM refinement to all extractors |

### Future: System Detection Module

When the above cleanup is done, consider adding optional system detection:

```
src/ingest/system_configs/
  wod.yaml       # World of Darkness family
  dnd5e.yaml     # D&D 5e
  pbta.yaml      # Powered by the Apocalypse
```

This is NOT blocking — the pipeline should work without knowing the game system.

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
| 2026-01-29 | `_extract_equipment()` generic structural detection | Replaced hardcoded weapon names with table/stat pattern detection |
| 2026-01-29 | `_extract_health()` generic structural detection | Replaced hardcoded health levels with penalty ladder detection |
| 2026-01-29 | Ingest pipeline philosophy documentation | Added to CLAUDE.md, TDD.md, SYSTEM_ADAPTER_DESIGN.md |
| 2026-01-29 | Documentation migration/cleanup | Slimmed CLAUDE.md, updated USAGE.md with missing commands |
