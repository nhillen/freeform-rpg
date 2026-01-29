"""Tests for Stage 7: Content Pack Validation."""

import pytest
import yaml
from pathlib import Path

from src.ingest.validate import PackValidator, ValidationReport
from src.ingest.utils import write_markdown


def _make_pack(tmp_path, pack_id="test_pack"):
    """Create a minimal valid content pack."""
    pack_dir = tmp_path / pack_id
    pack_dir.mkdir()

    # Write manifest
    manifest = {
        "id": pack_id,
        "name": "Test Pack",
        "version": "1.0",
        "layer": "sourcebook",
        "description": "A test content pack",
    }
    (pack_dir / "pack.yaml").write_text(yaml.dump(manifest))

    # Write a location file
    locs_dir = pack_dir / "locations"
    locs_dir.mkdir()
    write_markdown(
        locs_dir / "neon_dragon.md",
        "# The Neon Dragon\n\nA seedy bar in the neon district.",
        {"title": "The Neon Dragon", "type": "location", "entity_id": "neon_dragon"},
    )

    # Write an NPC file
    npcs_dir = pack_dir / "npcs"
    npcs_dir.mkdir()
    write_markdown(
        npcs_dir / "viktor.md",
        "# Viktor Kozlov\n\nA dangerous enforcer with connections.",
        {"title": "Viktor Kozlov", "type": "npc", "entity_id": "viktor_kozlov"},
    )

    return pack_dir


class TestPackValidator:
    def test_valid_pack_passes(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        validator = PackValidator()
        report = validator.validate(pack_dir)

        assert report.valid is True
        assert len(report.errors) == 0

    def test_missing_manifest_fails(self, tmp_path):
        pack_dir = tmp_path / "bad_pack"
        pack_dir.mkdir()

        validator = PackValidator()
        report = validator.validate(pack_dir)

        assert report.valid is False
        assert any("pack.yaml" in e for e in report.errors)

    def test_missing_id_fails(self, tmp_path):
        pack_dir = tmp_path / "no_id"
        pack_dir.mkdir()
        (pack_dir / "pack.yaml").write_text(yaml.dump({"name": "Test"}))

        validator = PackValidator()
        report = validator.validate(pack_dir)

        assert report.valid is False
        assert any("id" in e for e in report.errors)

    def test_installation_test(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        validator = PackValidator()
        report = validator.validate(pack_dir, output_dir=tmp_path / "report")

        assert report.valid is True
        assert "installation" in report.stats
        assert report.stats["installation"]["chunks_created"] > 0

    def test_retrieval_spot_check(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        validator = PackValidator()
        report = validator.validate(pack_dir)

        if "retrieval" in report.stats:
            assert report.stats["retrieval"]["queries_run"] > 0

    def test_empty_pack_warns(self, tmp_path):
        pack_dir = tmp_path / "empty_pack"
        pack_dir.mkdir()
        (pack_dir / "pack.yaml").write_text(yaml.dump({
            "id": "empty", "name": "Empty Pack"
        }))

        validator = PackValidator()
        report = validator.validate(pack_dir)

        assert report.valid is True  # Not an error, just a warning
        assert any("No markdown" in w or "0 chunks" in w for w in report.warnings)
