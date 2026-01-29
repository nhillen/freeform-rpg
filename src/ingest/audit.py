"""Post-ingest audit tool.

Analyzes a pipeline work directory to assess content retention,
quality, and coverage. Reports issues and performs spot-checks
against source material.
"""

import json
import logging
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

from .utils import count_words, read_markdown_with_frontmatter, read_stage_meta

logger = logging.getLogger(__name__)

# Patterns suggesting non-content leaked through
NON_CONTENT_PATTERNS = [
    re.compile(r"\bisbn[\s:\-]*[\dxX\-]{10,}", re.IGNORECASE),
    re.compile(r"\ball\s+rights\s+reserved\b", re.IGNORECASE),
    re.compile(r"\bdireitos\s+reservados\b", re.IGNORECASE),
    re.compile(r"\btodos\s+os\s+direitos\b", re.IGNORECASE),
    re.compile(r"\bopen\s+game\s+licen[sc]e\b", re.IGNORECASE),
    re.compile(r"^page\s+\d+$", re.IGNORECASE | re.MULTILINE),
]


@dataclass
class SpotCheckResult:
    """Result of checking a single source page against pack content."""
    page_num: int
    source_terms: list[str]
    terms_found: list[str]
    terms_missing: list[str]
    coverage_pct: float


@dataclass
class AuditReport:
    """Full audit report for a pipeline run."""
    # Source stats (from 01_extract)
    source_pages: int = 0
    source_words: int = 0

    # Segment stats (from 03_segment)
    segment_count: int = 0
    segment_avg_words: int = 0
    meta_filtered: int = 0
    segments_per_page: float = 0.0

    # Pack stats (from 06_assemble)
    pack_files: int = 0
    pack_words: int = 0
    retention_pct: float = 0.0
    files_by_dir: dict[str, int] = field(default_factory=dict)

    # Entity stats (from 05_lore)
    entity_count: int = 0
    entities_by_type: dict[str, int] = field(default_factory=dict)
    orphaned_entities: int = 0

    # Quality checks
    empty_dirs: list[str] = field(default_factory=list)
    stub_files: list[str] = field(default_factory=list)
    non_content_files: list[str] = field(default_factory=list)

    # Spot checks
    spot_checks: list[SpotCheckResult] = field(default_factory=list)
    avg_spot_coverage: float = 0.0

    # Computed issues
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "source": {
                "pages": self.source_pages,
                "words": self.source_words,
            },
            "segments": {
                "count": self.segment_count,
                "avg_words": self.segment_avg_words,
                "meta_filtered": self.meta_filtered,
                "per_page": round(self.segments_per_page, 2),
            },
            "pack": {
                "files": self.pack_files,
                "words": self.pack_words,
                "retention_pct": round(self.retention_pct, 1),
                "files_by_dir": self.files_by_dir,
            },
            "entities": {
                "count": self.entity_count,
                "by_type": self.entities_by_type,
                "orphaned": self.orphaned_entities,
            },
            "quality": {
                "empty_dirs": self.empty_dirs,
                "stub_files": self.stub_files,
                "non_content_files": self.non_content_files,
            },
            "spot_checks": [
                {
                    "page": sc.page_num,
                    "terms_total": len(sc.source_terms),
                    "terms_found": len(sc.terms_found),
                    "terms_missing": sc.terms_missing,
                    "coverage_pct": round(sc.coverage_pct, 1),
                }
                for sc in self.spot_checks
            ],
            "avg_spot_coverage": round(self.avg_spot_coverage, 1),
            "issues": self.issues,
        }


class IngestAuditor:
    """Audits a pipeline work directory for content quality and coverage."""

    def __init__(self, work_dir: str | Path):
        self.work_dir = Path(work_dir)

    def audit(self, samples: int = 5) -> AuditReport:
        """Run the full audit.

        Args:
            samples: Number of random source pages to spot-check.

        Returns:
            AuditReport with findings.
        """
        report = AuditReport()

        self._check_source_stats(report)
        self._check_segment_stats(report)
        self._check_pack_stats(report)
        self._check_entity_stats(report)
        self._check_quality(report)
        self._spot_check(report, samples)
        self._compute_issues(report)

        return report

    def _check_source_stats(self, report: AuditReport) -> None:
        """Gather source stats from 01_extract."""
        extract_dir = self.work_dir / "01_extract"
        if not extract_dir.exists():
            return

        meta = read_stage_meta(extract_dir) or {}
        report.source_pages = meta.get("total_pages", 0)

        # Count words from extracted pages
        pages_dir = extract_dir / "pages"
        if pages_dir.exists():
            total_words = 0
            page_count = 0
            for page_file in pages_dir.glob("page_*.md"):
                text = page_file.read_text(encoding="utf-8")
                total_words += count_words(text)
                page_count += 1
            report.source_words = total_words
            if not report.source_pages:
                report.source_pages = page_count

    def _check_segment_stats(self, report: AuditReport) -> None:
        """Gather segment stats from 03_segment."""
        segment_dir = self.work_dir / "03_segment"
        if not segment_dir.exists():
            return

        meta = read_stage_meta(segment_dir) or {}
        report.segment_count = meta.get("segment_count", 0)
        total_words = meta.get("total_words", 0)
        if report.segment_count:
            report.segment_avg_words = total_words // report.segment_count

        report.meta_filtered = meta.get("meta_filtered", 0)

        if report.source_pages:
            report.segments_per_page = report.segment_count / report.source_pages

    def _check_pack_stats(self, report: AuditReport) -> None:
        """Gather pack stats from 06_assemble."""
        assemble_dir = self.work_dir / "06_assemble"
        if not assemble_dir.exists():
            return

        # Find the pack directory (first subdirectory)
        pack_dir = None
        for child in assemble_dir.iterdir():
            if child.is_dir() and child.name != "__pycache__":
                pack_dir = child
                break

        if not pack_dir:
            return

        total_files = 0
        total_words = 0
        for subdir in pack_dir.iterdir():
            if not subdir.is_dir() or subdir.name.startswith("."):
                continue
            md_files = list(subdir.glob("*.md"))
            count = len(md_files)
            report.files_by_dir[subdir.name] = count
            total_files += count

            for md_file in md_files:
                _, body = read_markdown_with_frontmatter(md_file)
                total_words += count_words(body)

        report.pack_files = total_files
        report.pack_words = total_words

        if report.source_words > 0:
            report.retention_pct = (total_words / report.source_words) * 100

    def _check_entity_stats(self, report: AuditReport) -> None:
        """Gather entity stats from 05_lore."""
        lore_dir = self.work_dir / "05_lore"
        if not lore_dir.exists():
            return

        registry_path = lore_dir / "entity_registry.json"
        if not registry_path.exists():
            return

        data = json.loads(registry_path.read_text(encoding="utf-8"))
        entities = data.get("entities", [])
        report.entity_count = len(entities)

        by_type: dict[str, int] = {}
        entity_ids = set()
        for e in entities:
            etype = e.get("entity_type", "unknown")
            by_type[etype] = by_type.get(etype, 0) + 1
            entity_ids.add(e.get("id", ""))
        report.entities_by_type = by_type

        # Check for orphaned entities (not referenced in any enriched file)
        enriched_dir = lore_dir / "enriched"
        if enriched_dir.exists():
            referenced_ids: set[str] = set()
            for type_dir in enriched_dir.iterdir():
                if type_dir.is_dir():
                    for md_file in type_dir.glob("*.md"):
                        fm, _ = read_markdown_with_frontmatter(md_file)
                        for ref in fm.get("entity_refs", []):
                            referenced_ids.add(ref)
                        eid = fm.get("entity_id", "")
                        if eid:
                            referenced_ids.add(eid)

            orphaned = entity_ids - referenced_ids
            report.orphaned_entities = len(orphaned)

    def _check_quality(self, report: AuditReport) -> None:
        """Check for quality issues in the assembled pack."""
        assemble_dir = self.work_dir / "06_assemble"
        if not assemble_dir.exists():
            return

        pack_dir = None
        for child in assemble_dir.iterdir():
            if child.is_dir() and child.name != "__pycache__":
                pack_dir = child
                break

        if not pack_dir:
            return

        expected_dirs = ["locations", "npcs", "factions", "culture", "items"]
        for dirname in expected_dirs:
            dirpath = pack_dir / dirname
            if not dirpath.exists():
                report.empty_dirs.append(dirname)
            else:
                md_files = list(dirpath.glob("*.md"))
                if not md_files:
                    report.empty_dirs.append(dirname)

        # Check for stub files and non-content
        for md_file in pack_dir.rglob("*.md"):
            if md_file.name == "pack.yaml":
                continue
            size = md_file.stat().st_size
            if size < 500:
                report.stub_files.append(
                    f"{md_file.relative_to(pack_dir)} ({size}B)"
                )
            else:
                _, body = read_markdown_with_frontmatter(md_file)
                for pattern in NON_CONTENT_PATTERNS:
                    if pattern.search(body):
                        report.non_content_files.append(
                            str(md_file.relative_to(pack_dir))
                        )
                        break

    def _spot_check(self, report: AuditReport, n: int) -> None:
        """Spot-check N random source pages against pack content."""
        extract_dir = self.work_dir / "01_extract"
        pages_dir = extract_dir / "pages"
        if not pages_dir.exists():
            return

        assemble_dir = self.work_dir / "06_assemble"
        if not assemble_dir.exists():
            return

        # Find pack dir
        pack_dir = None
        for child in assemble_dir.iterdir():
            if child.is_dir() and child.name != "__pycache__":
                pack_dir = child
                break
        if not pack_dir:
            return

        # Collect all pack text for searching
        pack_text = ""
        for md_file in pack_dir.rglob("*.md"):
            if md_file.name == "pack.yaml":
                continue
            _, body = read_markdown_with_frontmatter(md_file)
            pack_text += " " + body.lower()

        # Select random pages
        page_files = sorted(pages_dir.glob("page_*.md"))
        if not page_files:
            return

        sample_count = min(n, len(page_files))
        sampled = random.sample(page_files, sample_count)

        for page_file in sampled:
            page_num = int(page_file.stem.split("_")[1])
            text = page_file.read_text(encoding="utf-8")

            # Extract distinctive terms: capitalized multi-word phrases
            terms = self._extract_distinctive_terms(text)

            found = []
            missing = []
            for term in terms:
                if term.lower() in pack_text:
                    found.append(term)
                else:
                    missing.append(term)

            coverage = (len(found) / len(terms) * 100) if terms else 0.0
            report.spot_checks.append(SpotCheckResult(
                page_num=page_num,
                source_terms=terms,
                terms_found=found,
                terms_missing=missing,
                coverage_pct=coverage,
            ))

        if report.spot_checks:
            report.avg_spot_coverage = sum(
                sc.coverage_pct for sc in report.spot_checks
            ) / len(report.spot_checks)

    def _extract_distinctive_terms(self, text: str) -> list[str]:
        """Extract distinctive terms from page text for spot-checking.

        Looks for capitalized multi-word phrases (proper nouns, game terms).
        """
        # Find sequences of 2+ capitalized words
        pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
        matches = pattern.findall(text)

        # Deduplicate and limit
        seen: set[str] = set()
        terms: list[str] = []
        for m in matches:
            if m not in seen and len(m) > 5:
                seen.add(m)
                terms.append(m)
                if len(terms) >= 10:
                    break

        return terms

    def _compute_issues(self, report: AuditReport) -> None:
        """Flag quality issues based on collected stats."""
        issues = []

        if report.retention_pct > 0 and report.retention_pct < 30:
            issues.append(
                f"Low content retention: {report.retention_pct:.1f}% "
                f"({report.pack_words}/{report.source_words} words)"
            )

        if report.empty_dirs:
            issues.append(
                f"Empty pack directories: {', '.join(report.empty_dirs)}"
            )

        if report.pack_files > 0:
            for dirname, count in report.files_by_dir.items():
                pct = count / report.pack_files * 100
                if pct > 60:
                    issues.append(
                        f"Concentration: {pct:.0f}% of files ({count}/{report.pack_files}) "
                        f"in {dirname}/"
                    )

        if len(report.stub_files) > 5:
            issues.append(
                f"Many stub files: {len(report.stub_files)} files under 500 bytes"
            )

        if report.segments_per_page > 0 and report.segments_per_page < 0.3:
            issues.append(
                f"Low segment density: {report.segments_per_page:.2f} segments/page "
                f"(expected >=0.3)"
            )

        if report.orphaned_entities > 0:
            issues.append(
                f"Orphaned entities: {report.orphaned_entities} entities not referenced "
                f"in any enriched file"
            )

        if report.non_content_files:
            issues.append(
                f"Non-content detected in {len(report.non_content_files)} pack files "
                f"(legal/copyright/structural noise)"
            )

        if report.avg_spot_coverage > 0 and report.avg_spot_coverage < 50:
            issues.append(
                f"Low spot-check coverage: {report.avg_spot_coverage:.0f}% of distinctive "
                f"terms found in pack"
            )

        report.issues = issues

    def format_report(self, report: AuditReport) -> str:
        """Render the audit report for terminal display."""
        lines = []
        lines.append("=" * 60)
        lines.append("INGEST AUDIT REPORT")
        lines.append("=" * 60)

        # Source
        lines.append("")
        lines.append("SOURCE")
        lines.append(f"  Pages: {report.source_pages}")
        lines.append(f"  Words: {report.source_words:,}")

        # Segments
        lines.append("")
        lines.append("SEGMENTS")
        lines.append(f"  Count: {report.segment_count}")
        lines.append(f"  Avg words: {report.segment_avg_words}")
        lines.append(f"  META filtered: {report.meta_filtered}")
        lines.append(f"  Per page: {report.segments_per_page:.2f}")

        # Pack
        lines.append("")
        lines.append("PACK")
        lines.append(f"  Files: {report.pack_files}")
        lines.append(f"  Words: {report.pack_words:,}")
        lines.append(f"  Retention: {report.retention_pct:.1f}%")
        if report.files_by_dir:
            lines.append("  By directory:")
            for dirname, count in sorted(
                report.files_by_dir.items(), key=lambda x: -x[1]
            ):
                pct = (count / max(report.pack_files, 1)) * 100
                lines.append(f"    {dirname}/: {count} ({pct:.0f}%)")

        # Entities
        lines.append("")
        lines.append("ENTITIES")
        lines.append(f"  Total: {report.entity_count}")
        if report.entities_by_type:
            for etype, count in sorted(
                report.entities_by_type.items(), key=lambda x: -x[1]
            ):
                lines.append(f"    {etype}: {count}")
        if report.orphaned_entities:
            lines.append(f"  Orphaned: {report.orphaned_entities}")

        # Quality
        lines.append("")
        lines.append("QUALITY")
        if report.empty_dirs:
            lines.append(f"  Empty dirs: {', '.join(report.empty_dirs)}")
        if report.stub_files:
            lines.append(f"  Stub files ({len(report.stub_files)}):")
            for sf in report.stub_files[:10]:
                lines.append(f"    - {sf}")
            if len(report.stub_files) > 10:
                lines.append(f"    ... and {len(report.stub_files) - 10} more")
        if report.non_content_files:
            lines.append(f"  Non-content files ({len(report.non_content_files)}):")
            for ncf in report.non_content_files[:5]:
                lines.append(f"    - {ncf}")
            if len(report.non_content_files) > 5:
                lines.append(
                    f"    ... and {len(report.non_content_files) - 5} more"
                )

        # Spot checks
        if report.spot_checks:
            lines.append("")
            lines.append("SPOT CHECKS")
            for sc in report.spot_checks:
                status = "OK" if sc.coverage_pct >= 50 else "LOW"
                lines.append(
                    f"  Page {sc.page_num}: {sc.coverage_pct:.0f}% "
                    f"({len(sc.terms_found)}/{len(sc.source_terms)} terms) [{status}]"
                )
                if sc.terms_missing:
                    missing_preview = ", ".join(sc.terms_missing[:3])
                    if len(sc.terms_missing) > 3:
                        missing_preview += f" (+{len(sc.terms_missing) - 3} more)"
                    lines.append(f"    Missing: {missing_preview}")
            lines.append(
                f"  Average coverage: {report.avg_spot_coverage:.0f}%"
            )

        # Issues
        lines.append("")
        if report.issues:
            lines.append(f"ISSUES ({len(report.issues)})")
            for issue in report.issues:
                lines.append(f"  ! {issue}")
        else:
            lines.append("ISSUES: None found")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)
