"""Tests for the ingest audit tool."""

import json
import pytest
from pathlib import Path

from src.ingest.audit import AuditReport, IngestAuditor
from src.ingest.utils import write_markdown, write_stage_meta


def _build_minimal_work_dir(tmp_path):
    """Build a minimal pipeline work directory for testing."""
    work = tmp_path / "work"

    # 01_extract
    extract_dir = work / "01_extract"
    pages_dir = extract_dir / "pages"
    pages_dir.mkdir(parents=True)
    write_stage_meta(extract_dir, {
        "stage": "extract",
        "status": "complete",
        "total_pages": 3,
    })
    for i in range(1, 4):
        (pages_dir / f"page_{i:04d}.md").write_text(
            f"Page {i} content. The Shadow Broker controls the district. " * 50
        )

    # 03_segment
    segment_dir = work / "03_segment"
    segment_dir.mkdir(parents=True)
    write_stage_meta(segment_dir, {
        "stage": "segment",
        "status": "complete",
        "segment_count": 5,
        "total_words": 500,
        "meta_filtered": 1,
    })

    # 05_lore
    lore_dir = work / "05_lore"
    lore_dir.mkdir(parents=True)
    enriched_dir = lore_dir / "enriched" / "cultures"
    enriched_dir.mkdir(parents=True)

    write_markdown(
        enriched_dir / "politics.md",
        "The Shadow Broker controls the district politics. " * 20,
        {
            "title": "District Politics",
            "type": "culture",
            "entity_id": "district_politics",
            "entity_refs": ["shadow_broker", "district_politics"],
        },
    )

    (lore_dir / "entity_registry.json").write_text(json.dumps({
        "entities": [
            {
                "id": "shadow_broker",
                "name": "The Shadow Broker",
                "entity_type": "npc",
                "description": "A mysterious figure.",
                "aliases": [],
                "related_entities": [],
                "source_segments": ["seg_0001"],
            },
            {
                "id": "district_politics",
                "name": "District Politics",
                "entity_type": "general",
                "description": "",
                "aliases": [],
                "related_entities": ["shadow_broker"],
                "source_segments": ["seg_0002"],
            },
        ]
    }))

    # 06_assemble
    assemble_dir = work / "06_assemble"
    pack_dir = assemble_dir / "test_pack"
    for subdir in ["locations", "npcs", "factions", "culture", "items"]:
        (pack_dir / subdir).mkdir(parents=True)

    write_markdown(
        pack_dir / "culture" / "politics.md",
        "The Shadow Broker controls the district politics. " * 20,
        {"title": "District Politics", "type": "culture"},
    )

    # pack.yaml
    (pack_dir / "pack.yaml").write_text("id: test_pack\nname: Test Pack\n")

    return work


class TestIngestAuditor:
    def test_basic_audit_runs(self, tmp_path):
        work = _build_minimal_work_dir(tmp_path)
        auditor = IngestAuditor(work)
        report = auditor.audit(samples=1)

        assert isinstance(report, AuditReport)
        assert report.source_pages == 3
        assert report.source_words > 0
        assert report.segment_count == 5

    def test_pack_stats(self, tmp_path):
        work = _build_minimal_work_dir(tmp_path)
        auditor = IngestAuditor(work)
        report = auditor.audit(samples=0)

        assert report.pack_files == 1
        assert report.pack_words > 0
        assert report.retention_pct > 0

    def test_entity_stats(self, tmp_path):
        work = _build_minimal_work_dir(tmp_path)
        auditor = IngestAuditor(work)
        report = auditor.audit(samples=0)

        assert report.entity_count == 2
        assert "npc" in report.entities_by_type

    def test_empty_dirs_detected(self, tmp_path):
        work = _build_minimal_work_dir(tmp_path)
        auditor = IngestAuditor(work)
        report = auditor.audit(samples=0)

        # locations, npcs, factions, items should be empty
        assert len(report.empty_dirs) >= 3

    def test_issues_computed(self, tmp_path):
        work = _build_minimal_work_dir(tmp_path)
        auditor = IngestAuditor(work)
        report = auditor.audit(samples=0)

        # Should detect empty dirs at minimum
        assert len(report.issues) > 0

    def test_spot_check(self, tmp_path):
        work = _build_minimal_work_dir(tmp_path)
        auditor = IngestAuditor(work)
        report = auditor.audit(samples=2)

        assert len(report.spot_checks) == 2
        for sc in report.spot_checks:
            assert sc.page_num >= 1

    def test_format_report(self, tmp_path):
        work = _build_minimal_work_dir(tmp_path)
        auditor = IngestAuditor(work)
        report = auditor.audit(samples=1)

        text = auditor.format_report(report)
        assert "INGEST AUDIT REPORT" in text
        assert "SOURCE" in text
        assert "SEGMENTS" in text
        assert "PACK" in text

    def test_to_dict(self, tmp_path):
        work = _build_minimal_work_dir(tmp_path)
        auditor = IngestAuditor(work)
        report = auditor.audit(samples=0)

        d = report.to_dict()
        assert "source" in d
        assert "segments" in d
        assert "pack" in d
        assert "issues" in d
        # Should be JSON-serializable
        json.dumps(d)

    def test_nonexistent_work_dir(self, tmp_path):
        auditor = IngestAuditor(tmp_path / "nonexistent")
        report = auditor.audit(samples=0)

        # Should not crash, just return empty report
        assert report.source_pages == 0
        assert report.pack_files == 0

    def test_concentration_issue(self, tmp_path):
        """Detects when >60% of files are in one directory."""
        work = _build_minimal_work_dir(tmp_path)
        # Add more culture files to create concentration
        pack_dir = work / "06_assemble" / "test_pack" / "culture"
        for i in range(5):
            write_markdown(
                pack_dir / f"extra_{i}.md",
                f"Extra content for file {i}. " * 30,
                {"title": f"Extra {i}", "type": "culture"},
            )

        auditor = IngestAuditor(work)
        report = auditor.audit(samples=0)

        # All 6 files are in culture/ → 100% concentration
        concentration_issues = [
            i for i in report.issues if "Concentration" in i
        ]
        assert len(concentration_issues) >= 1
