"""Pack Tester - Sanity-check content packs before gameplay.

Loads a content pack into a temp database, analyzes contents,
auto-generates a test scenario, runs retrieval probes, and
produces a terminal report with coverage stats and issues.

No LLM calls required. Fast, deterministic, cheap.
"""

import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.content.chunker import Chunker, ContentChunk, estimate_tokens
from src.content.indexer import LoreIndexer
from src.content.pack_loader import PackLoader, PackManifest, ContentFile, TYPE_DIRS
from src.content.retriever import LoreQuery, LoreRetriever, RetrievalResult
from src.content.vector_store import NullVectorStore
from src.db.state_store import StateStore


@dataclass
class TestReport:
    """Structured output from a pack test run."""

    # Pack info
    pack_id: str = ""
    pack_name: str = ""
    file_count: int = 0
    chunk_count: int = 0
    entity_count: int = 0

    # Distribution
    files_by_type: dict[str, int] = field(default_factory=dict)
    chunks_by_type: dict[str, int] = field(default_factory=dict)
    entities_by_type: dict[str, list[dict]] = field(default_factory=dict)

    # Samples
    samples: list[dict] = field(default_factory=list)

    # Scenario
    scenario_path: str | None = None
    scenario_summary: dict = field(default_factory=dict)

    # Probes
    probes: list[dict] = field(default_factory=list)
    query_hit_rate: float = 0.0
    chunk_coverage: float = 0.0
    unique_chunks_found: int = 0

    # Issues
    issues: list[dict] = field(default_factory=list)

    def format(self) -> str:
        """Render the report as a formatted terminal string."""
        return format_report(self)


class PackTester:
    """Analyzes a content pack and produces a structured test report."""

    def __init__(self, pack_dir: str | Path):
        self.pack_dir = Path(pack_dir)
        self._manifest: PackManifest | None = None
        self._files: list[ContentFile] = []
        self._chunks: list[ContentChunk] = []
        self._entity_registry: list[dict] = []
        self._entity_manifest: dict[str, list[str]] = {}
        self._store: StateStore | None = None
        self._retriever: LoreRetriever | None = None
        self._temp_dir: str | None = None

    def test(
        self,
        generate_scenario: bool = True,
        scenario_dir: str = "scenarios",
    ) -> TestReport:
        """Run all test phases and return a structured report."""
        report = TestReport()

        try:
            self._load_and_index(report)
            self._analyze_distribution(report)
            self._sample_entities(report)

            if generate_scenario:
                self._generate_scenario(report, scenario_dir)

            self._run_retrieval_probes(report)
            self._detect_issues(report)
        finally:
            self._cleanup()

        return report

    # ------------------------------------------------------------------
    # Phase 1: Load and index
    # ------------------------------------------------------------------

    def _load_and_index(self, report: TestReport) -> None:
        """Install the pack into a temp database for querying."""
        loader = PackLoader()
        manifest, files = loader.load_pack(self.pack_dir)

        self._manifest = manifest
        self._files = files

        chunker = Chunker()
        self._chunks = chunker.chunk_files(files, manifest.id)

        # Create temp database
        self._temp_dir = tempfile.mkdtemp(prefix="pack_test_")
        db_path = os.path.join(self._temp_dir, "test.db")
        self._store = StateStore(db_path)
        self._store.ensure_schema()

        # Index into FTS5
        indexer = LoreIndexer(self._store, NullVectorStore())
        indexer.index_pack(manifest, self._chunks)

        # Load entity registry if available alongside the pack
        self._load_entity_registry()

        # Build entity manifest for retriever
        self._entity_manifest = self._build_entity_manifest()

        # Create retriever
        self._retriever = LoreRetriever(
            self._store,
            NullVectorStore(),
            entity_manifest=self._entity_manifest,
        )

        # Fill in report basics
        report.pack_id = manifest.id
        report.pack_name = manifest.name
        report.file_count = len(files)
        report.chunk_count = len(self._chunks)
        report.entity_count = len(self._entity_registry)

    def _load_entity_registry(self) -> None:
        """Try to load entity_registry.json from the ingest output."""
        # Look for entity registry in sibling 05_lore directory
        # (pack_dir is typically .../06_assemble/<pack_id>)
        registry_candidates = [
            self.pack_dir.parent.parent / "05_lore" / "entity_registry.json",
            self.pack_dir.parent / "entity_registry.json",
            self.pack_dir / "entity_registry.json",
        ]
        for candidate in registry_candidates:
            if candidate.exists():
                try:
                    data = json.loads(candidate.read_text(encoding="utf-8"))
                    self._entity_registry = data.get("entities", [])
                    return
                except (json.JSONDecodeError, KeyError):
                    pass

        # Derive entities from chunk entity_refs if no registry found
        self._derive_entities_from_chunks()

    def _derive_entities_from_chunks(self) -> None:
        """Derive a basic entity list from chunk frontmatter/entity_refs."""
        seen = {}
        for cf in self._files:
            eid = cf.entity_id or cf.title.lower().replace(" ", "_")
            if eid and eid not in seen:
                seen[eid] = {
                    "id": eid,
                    "name": cf.title,
                    "entity_type": cf.file_type,
                    "description": "",
                    "aliases": [],
                    "related_entities": list(cf.frontmatter.get("entity_refs", [])),
                    "source_segments": [],
                }
        self._entity_registry = list(seen.values())

    def _build_entity_manifest(self) -> dict[str, list[str]]:
        """Build entity_id -> [chunk_ids] mapping from indexed chunks."""
        manifest: dict[str, list[str]] = {}
        for chunk in self._chunks:
            for ref in chunk.entity_refs:
                manifest.setdefault(ref, []).append(chunk.id)
        return manifest

    # ------------------------------------------------------------------
    # Phase 2: Analyze distribution
    # ------------------------------------------------------------------

    def _analyze_distribution(self, report: TestReport) -> None:
        """Count files, chunks, and entities by type."""
        # Files by type directory
        files_by_type: dict[str, int] = {}
        for cf in self._files:
            files_by_type[cf.file_type] = files_by_type.get(cf.file_type, 0) + 1
        report.files_by_type = files_by_type

        # Chunks by type
        chunks_by_type: dict[str, int] = {}
        for chunk in self._chunks:
            chunks_by_type[chunk.chunk_type] = chunks_by_type.get(chunk.chunk_type, 0) + 1
        report.chunks_by_type = chunks_by_type

        # Entities by type
        entities_by_type: dict[str, list[dict]] = {}
        for ent in self._entity_registry:
            etype = ent.get("entity_type", "unknown")
            entities_by_type.setdefault(etype, []).append(ent)
        report.entities_by_type = entities_by_type

    # ------------------------------------------------------------------
    # Phase 3: Sample entities
    # ------------------------------------------------------------------

    def _sample_entities(self, report: TestReport) -> None:
        """Pick representative entities sorted by cross-reference count."""
        # Count how many chunks reference each entity
        ref_counts: Counter = Counter()
        for chunk in self._chunks:
            for ref in chunk.entity_refs:
                ref_counts[ref] += 1

        samples = []
        seen_types: dict[str, int] = {}

        # Sort all entities by reference count descending
        sorted_entities = sorted(
            self._entity_registry,
            key=lambda e: ref_counts.get(e["id"], 0),
            reverse=True,
        )

        for ent in sorted_entities:
            etype = ent.get("entity_type", "unknown")
            if seen_types.get(etype, 0) >= 3:
                continue

            # Gather chunk info for this entity
            chunk_ids = self._entity_manifest.get(ent["id"], [])
            chunk_tokens = sum(
                c.token_estimate
                for c in self._chunks
                if c.id in set(chunk_ids)
            )

            # Get tags from associated chunks
            entity_tags = set()
            for c in self._chunks:
                if c.id in set(chunk_ids):
                    entity_tags.update(c.tags)

            # Get related entities
            related = ent.get("related_entities", [])

            samples.append({
                "name": ent.get("name", ent["id"]),
                "type": etype,
                "description": (ent.get("description", "") or "")[:120],
                "tags": sorted(entity_tags)[:10],
                "related": related[:5],
                "chunk_count": len(chunk_ids),
                "tokens": chunk_tokens,
            })
            seen_types[etype] = seen_types.get(etype, 0) + 1

        report.samples = samples

    # ------------------------------------------------------------------
    # Phase 4: Generate test scenario
    # ------------------------------------------------------------------

    def _generate_scenario(self, report: TestReport, scenario_dir: str) -> None:
        """Auto-generate a test scenario YAML from pack entities."""
        if not self._manifest:
            return

        ref_counts: Counter = Counter()
        for chunk in self._chunks:
            for ref in chunk.entity_refs:
                ref_counts[ref] += 1

        def top_entities(etype: str, n: int = 3) -> list[dict]:
            typed = [e for e in self._entity_registry if e.get("entity_type") == etype]
            typed.sort(key=lambda e: ref_counts.get(e["id"], 0), reverse=True)
            return typed[:n]

        locations = top_entities("location", 3)
        npcs = top_entities("npc", 3)
        factions = top_entities("faction", 3)
        items = top_entities("item", 3)
        cultures = top_entities("culture", 3)

        # If no locations, use the most-referenced entity as conceptual location
        if not locations:
            all_sorted = sorted(
                self._entity_registry,
                key=lambda e: ref_counts.get(e["id"], 0),
                reverse=True,
            )
            if all_sorted:
                fallback = all_sorted[0]
                locations = [{
                    "id": fallback["id"],
                    "name": fallback.get("name", fallback["id"]),
                    "entity_type": "location",
                    "description": fallback.get("description", ""),
                }]

        # If no NPCs, pick from factions or cultures
        if not npcs and factions:
            npcs = [{
                "id": f["id"],
                "name": f.get("name", f["id"]),
                "entity_type": "npc",
                "description": f.get("description", ""),
            } for f in factions[:2]]

        pack_id = self._manifest.id
        start_location = locations[0] if locations else {"id": "unknown", "name": "Unknown"}
        start_loc_id = start_location["id"]

        # Build scenario entities
        scenario_entities = []

        # PC
        pc_tags = set()
        for chunk in self._chunks[:20]:
            pc_tags.update(chunk.tags[:3])
        pc_skills = sorted(pc_tags - {"general", "culture", "faction", "npc", "location", "item"})[:5]

        scenario_entities.append({
            "id": "player",
            "type": "pc",
            "name": "Test Explorer",
            "attrs": {
                "background": f"An explorer investigating the world of {self._manifest.name}",
                "skills": pc_skills or ["investigation", "lore", "survival"],
            },
            "tags": ["player"],
        })

        # Location entities
        for loc in locations:
            desc = loc.get("description", "A significant location in this world")
            scenario_entities.append({
                "id": loc["id"],
                "type": "location",
                "name": loc.get("name", loc["id"]),
                "attrs": {
                    "description": desc[:200] if desc else "A notable place",
                    "atmosphere": "Dense with history and significance",
                },
                "tags": ["location"],
            })

        # NPC entities
        for npc in npcs:
            desc = npc.get("description", "A notable figure")
            scenario_entities.append({
                "id": npc["id"],
                "type": "npc",
                "name": npc.get("name", npc["id"]),
                "attrs": {
                    "role": "Notable Figure",
                    "description": desc[:200] if desc else "A notable figure in this world",
                    "threat_level": "low",
                },
                "tags": ["npc"],
            })

        # Facts linking NPCs to locations/factions
        facts = []
        for i, npc in enumerate(npcs):
            if locations:
                loc = locations[i % len(locations)]
                facts.append({
                    "id": f"fact_npc_{i}_location",
                    "subject_id": npc["id"],
                    "predicate": "located_at",
                    "object": loc["id"],
                    "visibility": "known",
                    "tags": ["location"],
                })

        # Threads
        threads = []
        if self._entity_registry:
            # Exploration thread
            top_entity = max(
                self._entity_registry,
                key=lambda e: ref_counts.get(e["id"], 0),
            )
            threads.append({
                "id": "explore_thread",
                "title": f"Explore the World of {self._manifest.name}",
                "status": "active",
                "stakes": {
                    "success": "Discover the secrets of this world",
                    "failure": "Remain ignorant of hidden truths",
                },
                "related_entity_ids": [top_entity["id"]],
                "tags": ["exploration"],
            })

        if factions and len(factions) >= 2:
            threads.append({
                "id": "conflict_thread",
                "title": f"The {factions[0].get('name', 'Unknown')} Conflict",
                "status": "active",
                "stakes": {
                    "success": "Navigate the conflict successfully",
                    "failure": "Get caught in the crossfire",
                },
                "related_entity_ids": [f["id"] for f in factions[:2]],
                "tags": ["conflict"],
            })

        # Clocks
        clocks = [
            {"id": "heat", "name": "Alert", "value": 0, "max": 8,
             "triggers": {"4": "Suspicion grows", "8": "Full alert"},
             "tags": ["pressure"]},
            {"id": "time", "name": "Time", "value": 8, "max": 12,
             "triggers": {"4": "Running low on time", "0": "Time's up"},
             "tags": ["pressure"]},
            {"id": "harm", "name": "Harm", "value": 0, "max": 4,
             "triggers": {"2": "Wounded", "4": "Critical condition"},
             "tags": ["player"]},
        ]

        # Add pack-specific clock from thematic terms
        thematic_terms = [
            e.get("name", "")
            for e in self._entity_registry
            if e.get("entity_type") == "culture"
        ][:1]
        if thematic_terms:
            term = thematic_terms[0]
            clocks.append({
                "id": term.lower().replace(" ", "_"),
                "name": term,
                "value": 0, "max": 6,
                "triggers": {"3": f"{term} intensifies", "6": f"{term} peaks"},
                "tags": ["thematic"],
            })

        # Opening text
        loc_name = start_location.get("name", "an unknown place")
        opening_text = (
            f"You find yourself contemplating {loc_name}. "
            f"The world of {self._manifest.name} stretches before you, "
            f"full of mysteries waiting to be uncovered.\n\n"
            f"What do you do?"
        )

        # Build scenario dict
        scenario = {
            "id": f"{pack_id}_test",
            "name": f"{self._manifest.name} - Test Scenario",
            "description": f"Auto-generated test scenario for {self._manifest.name} content pack",
            "genre": "exploration",
            "estimated_length": "1-2 hours",
            "content_packs": [pack_id],
            "default_system": "noir_standard",
            "calibration": {
                "tone": {
                    "gritty_vs_cinematic": 0.5,
                    "dark_vs_light": 0.5,
                    "moral_complexity": 0.5,
                    "slow_burn_vs_action": 0.5,
                },
                "themes": {"primary": ["exploration"], "secondary": ["discovery"]},
                "risk": {
                    "lethality": "moderate",
                    "failure_mode": "consequential",
                    "permanence": "meaningful",
                    "plot_armor": "moderate",
                },
                "boundaries": {"lines": [], "veils": []},
            },
            "system": {
                "clock_rules": {
                    "enabled": True,
                    "clocks_enabled": [c["id"] for c in clocks],
                },
            },
            "genre_rules": {
                "setting": f"The world of {self._manifest.name}",
                "technology": "As described in source material",
                "society": "As described in source material",
                "tone": "Exploratory",
                "what_works": ["Investigation", "Dialogue", "Exploration"],
                "what_doesnt": ["Breaking lore", "Anachronisms"],
            },
            "clocks": clocks,
            "entities": scenario_entities,
            "facts": facts,
            "relationships": [],
            "threads": threads,
            "starting_scene": {
                "location_id": start_loc_id,
                "present_entity_ids": ["player"] + [n["id"] for n in npcs[:1]],
                "time": {"hour": 12, "minute": 0, "period": "day", "weather": "clear"},
                "constraints": {},
            },
            "opening_text": opening_text,
        }

        # Write scenario file
        scenario_path = Path(scenario_dir)
        scenario_path.mkdir(parents=True, exist_ok=True)
        out_file = scenario_path / f"{pack_id}_test.yaml"
        with open(out_file, "w", encoding="utf-8") as f:
            yaml.dump(scenario, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        report.scenario_path = str(out_file)
        report.scenario_summary = {
            "pc": "Test Explorer",
            "location": start_location.get("name", "Unknown"),
            "npcs": [n.get("name", n["id"]) for n in npcs],
            "factions": [f.get("name", f["id"]) for f in factions],
            "threads": [t["title"] for t in threads],
            "clocks": [f"{c['name']} ({c['value']}/{c['max']})" for c in clocks],
        }

    # ------------------------------------------------------------------
    # Phase 5: Retrieval probes
    # ------------------------------------------------------------------

    def _run_retrieval_probes(self, report: TestReport) -> None:
        """Test lore retrieval with simulated gameplay queries."""
        if not self._retriever or not self._store:
            return

        pack_ids = [self._manifest.id] if self._manifest else []
        probes: list[dict] = []
        all_hit_chunk_ids: set[str] = set()

        ref_counts: Counter = Counter()
        for chunk in self._chunks:
            for ref in chunk.entity_refs:
                ref_counts[ref] += 1

        # Entity lookups: top entities by ref count
        top_entities = sorted(
            self._entity_registry,
            key=lambda e: ref_counts.get(e["id"], 0),
            reverse=True,
        )[:8]

        for ent in top_entities:
            query = LoreQuery(
                keywords=[ent.get("name", ent["id"])],
                entity_ids=[ent["id"]],
                pack_ids=pack_ids,
                max_tokens=2000,
                max_chunks=10,
            )
            result = self._retriever.query(query)
            hit_ids = {c["id"] for c in result.chunks}
            all_hit_chunk_ids.update(hit_ids)
            probes.append({
                "query": ent.get("name", ent["id"]),
                "description": f"Entity lookup: {ent.get('name', ent['id'])}",
                "chunks_found": len(result.chunks),
                "tokens": result.total_tokens,
                "passed": len(result.chunks) > 0,
            })

        # Keyword searches: pick distinctive tags from the pack
        tag_counter: Counter = Counter()
        for chunk in self._chunks:
            for tag in chunk.tags:
                if tag not in TYPE_DIRS.values() and tag != "general":
                    tag_counter[tag] += 1

        top_tags = [tag for tag, _ in tag_counter.most_common(5)]
        for tag in top_tags:
            query = LoreQuery(
                keywords=[tag],
                pack_ids=pack_ids,
                max_tokens=2000,
                max_chunks=10,
            )
            result = self._retriever.query(query)
            hit_ids = {c["id"] for c in result.chunks}
            all_hit_chunk_ids.update(hit_ids)
            probes.append({
                "query": tag,
                "description": f"Keyword search: {tag}",
                "chunks_found": len(result.chunks),
                "tokens": result.total_tokens,
                "passed": len(result.chunks) > 0,
            })

        # Scene simulation: build a scene query if we have scenario data
        if report.scenario_summary:
            location_name = report.scenario_summary.get("location", "")
            npc_names = report.scenario_summary.get("npcs", [])[:2]
            scene_keywords = [location_name] + npc_names
            scene_keywords = [k for k in scene_keywords if k]

            if scene_keywords:
                query = LoreQuery(
                    keywords=scene_keywords,
                    pack_ids=pack_ids,
                    max_tokens=3000,
                    max_chunks=15,
                )
                result = self._retriever.query(query)
                hit_ids = {c["id"] for c in result.chunks}
                all_hit_chunk_ids.update(hit_ids)
                probes.append({
                    "query": " + ".join(scene_keywords),
                    "description": f"Scene simulation: {' + '.join(scene_keywords)}",
                    "chunks_found": len(result.chunks),
                    "tokens": result.total_tokens,
                    "passed": len(result.chunks) > 0,
                })

        # Compute stats
        hits = sum(1 for p in probes if p["passed"])
        total = len(probes)

        report.probes = probes
        report.query_hit_rate = (hits / total) if total > 0 else 0.0
        report.unique_chunks_found = len(all_hit_chunk_ids)
        report.chunk_coverage = (
            len(all_hit_chunk_ids) / len(self._chunks)
            if self._chunks
            else 0.0
        )

    # ------------------------------------------------------------------
    # Phase 6: Issue detection
    # ------------------------------------------------------------------

    def _detect_issues(self, report: TestReport) -> None:
        """Detect potential problems with the pack."""
        issues: list[dict] = []

        # Entity types with 0 files
        entity_types_present = set(report.entities_by_type.keys())
        file_types_present = set(report.files_by_type.keys())

        for etype in entity_types_present:
            entity_list = report.entities_by_type[etype]
            # Map entity type to expected file type
            file_type = etype  # They use the same names
            if file_type not in file_types_present:
                count = len(entity_list)
                issues.append({
                    "severity": "warning",
                    "message": f"0 {etype} files ({count} {etype} entities have no dedicated lore)",
                })

        # Files with no entity_refs
        orphan_count = 0
        for chunk in self._chunks:
            if not chunk.entity_refs:
                orphan_count += 1
        if orphan_count > 0:
            issues.append({
                "severity": "info",
                "message": f"{orphan_count} chunks have no entity_refs (unreachable via manifest lookup)",
            })

        # Very small files
        small_files = []
        for cf in self._files:
            word_count = len(cf.body.split())
            if word_count < 50:
                small_files.append(cf.title)
        if small_files:
            issues.append({
                "severity": "warning",
                "message": f"{len(small_files)} files under 50 words: {', '.join(small_files[:3])}{'...' if len(small_files) > 3 else ''}",
            })

        # Very large files
        large_files = []
        for cf in self._files:
            word_count = len(cf.body.split())
            if word_count > 3000:
                large_files.append(f"{cf.title} ({word_count}w)")
        if large_files:
            issues.append({
                "severity": "info",
                "message": f"{len(large_files)} files over 3000 words: {', '.join(large_files[:3])}{'...' if len(large_files) > 3 else ''}",
            })

        # Pack name matches ID (suggests auto-derived name)
        if self._manifest:
            if self._manifest.name.lower().replace(" ", "") == self._manifest.id.lower().replace("_", ""):
                issues.append({
                    "severity": "warning",
                    "message": f'Pack name "{self._manifest.name}" matches ID verbatim — consider a cleaner display name',
                })

        # Retrieval probes with 0 results
        zero_probes = [p for p in report.probes if not p["passed"]]
        if zero_probes:
            names = [p["query"] for p in zero_probes]
            issues.append({
                "severity": "warning",
                "message": f"{len(zero_probes)} retrieval probes returned 0 results: {', '.join(names[:5])}",
            })

        # Low chunk coverage
        if report.chunk_coverage < 0.20 and report.chunk_count > 0:
            pct = int(report.chunk_coverage * 100)
            issues.append({
                "severity": "warning",
                "message": f"Low chunk coverage: {pct}% of chunks reachable via probes (< 20%)",
            })

        report.issues = issues

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cleanup(self) -> None:
        """Remove temp database directory."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)


# ======================================================================
# Report formatting
# ======================================================================

def _supports_color() -> bool:
    """Check if the terminal supports ANSI color codes."""
    if not hasattr(sys.stdout, "isatty"):
        return False
    if not sys.stdout.isatty():
        return False
    term = os.environ.get("TERM", "")
    if term == "dumb":
        return False
    return True


def _bar(value: int, total: int, width: int = 30) -> str:
    """Render a Unicode bar chart segment."""
    if total <= 0:
        return "\u2591" * width
    filled = int((value / total) * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def format_report(report: TestReport) -> str:
    """Build the formatted terminal report string."""
    color = _supports_color()

    # ANSI codes
    BOLD = "\033[1m" if color else ""
    DIM = "\033[2m" if color else ""
    GREEN = "\033[32m" if color else ""
    YELLOW = "\033[33m" if color else ""
    RED = "\033[31m" if color else ""
    CYAN = "\033[36m" if color else ""
    RESET = "\033[0m" if color else ""

    CHECK = f"{GREEN}\u2713{RESET}" if color else "\u2713"
    CROSS = f"{RED}\u2717{RESET}" if color else "\u2717"
    WARN = f"{YELLOW}\u26a0{RESET}" if color else "\u26a0"

    lines: list[str] = []
    W = 60  # report width

    # Header
    lines.append("")
    lines.append(f"{BOLD}\u2550" * W + RESET)
    title = f"Content Pack Test: {report.pack_name}"
    pad = max(0, (W - len(title)) // 2)
    lines.append(f"{BOLD}{' ' * pad}{title}{RESET}")
    lines.append(f"{BOLD}\u2550" * W + RESET)

    # -- Pack Overview --
    lines.append("")
    lines.append(f"{BOLD}\u2500\u2500 Pack Overview " + "\u2500" * (W - 15) + RESET)
    lines.append("")
    lines.append(f"  ID:       {report.pack_id}")
    lines.append(f"  Name:     {report.pack_name}")
    lines.append(f"  Files:    {report.file_count}")
    lines.append(f"  Chunks:   {report.chunk_count}")
    lines.append(f"  Entities: {report.entity_count}")

    # -- Content Distribution --
    lines.append("")
    lines.append(f"{BOLD}\u2500\u2500 Content Distribution " + "\u2500" * (W - 22) + RESET)
    lines.append("")

    max_count = max(report.files_by_type.values()) if report.files_by_type else 1
    # Sort by count descending
    for ftype, count in sorted(report.files_by_type.items(), key=lambda x: -x[1]):
        pct = int((count / report.file_count) * 100) if report.file_count else 0
        bar = _bar(count, max_count, 25)
        lines.append(f"  {ftype:<10}{bar} {count:>3} ({pct}%)")

    # -- Entity Registry --
    if report.entities_by_type:
        lines.append("")
        lines.append(f"{BOLD}\u2500\u2500 Entity Registry ({report.entity_count} total) " + "\u2500" * max(0, W - 28 - len(str(report.entity_count))) + RESET)
        lines.append("")

        for etype, ents in sorted(report.entities_by_type.items(), key=lambda x: -len(x[1])):
            names = [e.get("name", e["id"]) for e in ents[:5]]
            suffix = ", ..." if len(ents) > 5 else ""
            lines.append(f"  {etype:<10}({len(ents):>3})  {', '.join(names)}{suffix}")

    # -- Sample Content --
    if report.samples:
        lines.append("")
        lines.append(f"{BOLD}\u2500\u2500 Sample Content " + "\u2500" * (W - 17) + RESET)
        lines.append("")

        for sample in report.samples[:9]:  # Up to 3 per type, max 9
            name = sample["name"]
            stype = sample["type"]
            lines.append(f"  {BOLD}{name}{RESET} ({stype})")
            if sample["description"]:
                desc = sample["description"]
                # Wrap long descriptions
                if len(desc) > 70:
                    desc = desc[:67] + "..."
                lines.append(f"    {DIM}\"{desc}\"{RESET}")
            if sample["tags"]:
                lines.append(f"    Tags: [{', '.join(sample['tags'][:6])}]")
            if sample["related"]:
                lines.append(f"    Related: [{', '.join(str(r) for r in sample['related'][:5])}]")
            lines.append(f"    Lore chunks: {sample['chunk_count']} ({sample['tokens']} tokens)")
            lines.append("")

    # -- Test Scenario --
    if report.scenario_path:
        lines.append(f"{BOLD}\u2500\u2500 Test Scenario " + "\u2500" * (W - 16) + RESET)
        lines.append("")
        lines.append(f"  Saved: {report.scenario_path}")
        lines.append("")
        summary = report.scenario_summary
        lines.append(f"  PC:       {summary.get('pc', 'N/A')}")
        lines.append(f"  Start:    {summary.get('location', 'N/A')}")
        if summary.get("npcs"):
            lines.append(f"  NPCs:     {', '.join(summary['npcs'])}")
        if summary.get("factions"):
            lines.append(f"  Factions: {', '.join(summary['factions'])}")
        if summary.get("threads"):
            for i, t in enumerate(summary["threads"], 1):
                lines.append(f"  Thread {i}: \"{t}\"")
        if summary.get("clocks"):
            lines.append(f"  Clocks:   {', '.join(summary['clocks'])}")

    # -- Retrieval Probes --
    if report.probes:
        lines.append("")
        lines.append(f"{BOLD}\u2500\u2500 Retrieval Probes " + "\u2500" * (W - 19) + RESET)
        lines.append("")

        for probe in report.probes:
            mark = CHECK if probe["passed"] else CROSS
            name = probe["query"]
            if len(name) > 25:
                name = name[:22] + "..."
            chunks = probe["chunks_found"]
            tokens = probe["tokens"]
            if probe["passed"]:
                lines.append(f"  {mark} {name:<25} \u2192 {chunks} chunks ({tokens} tokens)")
            else:
                lines.append(f"  {mark} {name:<25} \u2192 0 chunks")

        lines.append("")
        hits = sum(1 for p in report.probes if p["passed"])
        total = len(report.probes)
        lines.append(f"  Queries: {total} run, {hits} hit ({int(report.query_hit_rate * 100)}%)")
        lines.append(
            f"  Coverage: {report.unique_chunks_found}/{report.chunk_count} "
            f"chunks reachable ({int(report.chunk_coverage * 100)}%)"
        )

    # -- Issues --
    lines.append("")
    lines.append(f"{BOLD}\u2500\u2500 Issues " + "\u2500" * (W - 9) + RESET)
    lines.append("")

    if report.issues:
        for issue in report.issues:
            sev = issue["severity"]
            msg = issue["message"]
            if sev == "warning":
                lines.append(f"  {WARN} {msg}")
            elif sev == "error":
                lines.append(f"  {CROSS} {msg}")
            else:
                lines.append(f"  {DIM}\u2139 {msg}{RESET}")
    else:
        lines.append(f"  {CHECK} No issues detected")

    lines.append("")
    lines.append(f"{BOLD}\u2550" * W + RESET)
    lines.append("")

    return "\n".join(lines)
