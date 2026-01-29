"""Tests for Stage 6: Content Pack Assembly."""

import pytest
import yaml
from pathlib import Path

from src.ingest.assemble import PackAssembler
from src.ingest.models import EntityEntry, EntityRegistry, IngestConfig
from src.ingest.utils import read_markdown_with_frontmatter, write_markdown


def _make_enriched_files(tmp_path):
    """Create enriched files on disk and return the file list."""
    enriched_dir = tmp_path / "enriched"
    (enriched_dir / "locations").mkdir(parents=True)
    (enriched_dir / "npcs").mkdir(parents=True)

    # Write a location file
    loc_path = enriched_dir / "locations" / "neon_dragon.md"
    write_markdown(
        loc_path,
        "A seedy bar in the neon district.",
        {"title": "The Neon Dragon", "type": "location", "entity_id": "neon_dragon"},
    )

    # Write an NPC file
    npc_path = enriched_dir / "npcs" / "viktor.md"
    write_markdown(
        npc_path,
        "A dangerous enforcer.",
        {"title": "Viktor Kozlov", "type": "npc", "entity_id": "viktor_kozlov"},
    )

    return [
        {
            "path": str(loc_path),
            "title": "The Neon Dragon",
            "file_type": "location",
            "entity_id": "neon_dragon",
            "frontmatter": {
                "title": "The Neon Dragon",
                "type": "location",
                "entity_id": "neon_dragon",
                "tags": ["bar", "neon-district"],
            },
        },
        {
            "path": str(npc_path),
            "title": "Viktor Kozlov",
            "file_type": "npc",
            "entity_id": "viktor_kozlov",
            "frontmatter": {
                "title": "Viktor Kozlov",
                "type": "npc",
                "entity_id": "viktor_kozlov",
                "tags": ["enforcer", "dangerous"],
            },
        },
    ]


class TestPackAssembler:
    def test_assemble_creates_pack_dir(self, tmp_path):
        enriched_files = _make_enriched_files(tmp_path)
        config = IngestConfig(
            pack_id="test_pack",
            pack_name="Test Pack",
            pack_version="1.0",
        )

        assembler = PackAssembler()
        pack_dir = assembler.assemble(
            enriched_files, config, tmp_path / "output"
        )

        assert pack_dir.exists()
        assert (pack_dir / "pack.yaml").exists()

    def test_pack_manifest_valid(self, tmp_path):
        enriched_files = _make_enriched_files(tmp_path)
        config = IngestConfig(
            pack_id="test_pack",
            pack_name="Test Pack",
            pack_version="1.0",
            pack_layer="sourcebook",
        )

        assembler = PackAssembler()
        pack_dir = assembler.assemble(
            enriched_files, config, tmp_path / "output"
        )

        manifest = yaml.safe_load((pack_dir / "pack.yaml").read_text())
        assert manifest["id"] == "test_pack"
        assert manifest["name"] == "Test Pack"
        assert manifest["version"] == "1.0"

    def test_files_sorted_into_type_dirs(self, tmp_path):
        enriched_files = _make_enriched_files(tmp_path)
        config = IngestConfig(pack_id="test_pack", pack_name="Test Pack")

        assembler = PackAssembler()
        pack_dir = assembler.assemble(
            enriched_files, config, tmp_path / "output"
        )

        locations = list((pack_dir / "locations").glob("*.md"))
        npcs = list((pack_dir / "npcs").glob("*.md"))
        assert len(locations) >= 1
        assert len(npcs) >= 1

    def test_frontmatter_preserved(self, tmp_path):
        enriched_files = _make_enriched_files(tmp_path)
        config = IngestConfig(pack_id="test_pack", pack_name="Test Pack")

        assembler = PackAssembler()
        pack_dir = assembler.assemble(
            enriched_files, config, tmp_path / "output"
        )

        loc_files = list((pack_dir / "locations").glob("*.md"))
        assert len(loc_files) >= 1
        fm, body = read_markdown_with_frontmatter(loc_files[0])
        assert fm["title"] == "The Neon Dragon"
        assert "bar" in fm.get("tags", [])

    def test_assemble_without_registry_backward_compat(self, tmp_path):
        """Assembly without entity_registry still works (backward compat)."""
        enriched_files = _make_enriched_files(tmp_path)
        config = IngestConfig(pack_id="test_pack", pack_name="Test Pack")

        assembler = PackAssembler()
        pack_dir = assembler.assemble(
            enriched_files, config, tmp_path / "output"
        )

        assert pack_dir.exists()
        assert (pack_dir / "pack.yaml").exists()


def _make_enriched_files_with_refs(tmp_path):
    """Create enriched files that reference entities not yet promoted."""
    enriched_dir = tmp_path / "enriched"
    (enriched_dir / "cultures").mkdir(parents=True)

    # Two culture files that both reference "shadow_broker" NPC
    f1_path = enriched_dir / "cultures" / "undercity_politics.md"
    write_markdown(
        f1_path,
        "The shadow broker controls much of the undercity trade. " * 20
        + "Known associates include various faction leaders. " * 10,
        {
            "title": "Undercity Politics",
            "type": "culture",
            "entity_id": "undercity_politics",
            "entity_refs": ["shadow_broker", "undercity_politics"],
        },
    )

    f2_path = enriched_dir / "cultures" / "trade_networks.md"
    write_markdown(
        f2_path,
        "The trade networks run through the shadow broker's channels. " * 20
        + "Black market goods flow through hidden passages. " * 10,
        {
            "title": "Trade Networks",
            "type": "culture",
            "entity_id": "trade_networks",
            "entity_refs": ["shadow_broker", "trade_networks"],
        },
    )

    return [
        {
            "path": str(f1_path),
            "title": "Undercity Politics",
            "file_type": "culture",
            "entity_id": "undercity_politics",
            "frontmatter": {
                "title": "Undercity Politics",
                "type": "culture",
                "entity_id": "undercity_politics",
                "entity_refs": ["shadow_broker", "undercity_politics"],
            },
        },
        {
            "path": str(f2_path),
            "title": "Trade Networks",
            "file_type": "culture",
            "entity_id": "trade_networks",
            "frontmatter": {
                "title": "Trade Networks",
                "type": "culture",
                "entity_id": "trade_networks",
                "entity_refs": ["shadow_broker", "trade_networks"],
            },
        },
    ]


class TestEntityPromotion:
    def test_promotes_npc_from_registry(self, tmp_path):
        """Entity referenced in files but without own file gets promoted."""
        enriched_files = _make_enriched_files_with_refs(tmp_path)
        config = IngestConfig(pack_id="test_pack", pack_name="Test Pack")

        registry = EntityRegistry()
        registry.add(EntityEntry(
            id="shadow_broker",
            name="The Shadow Broker",
            entity_type="npc",
            description="A mysterious figure controlling the undercity trade.",
            source_segments=["seg_0001", "seg_0002"],
        ))

        assembler = PackAssembler()
        pack_dir = assembler.assemble(
            enriched_files, config, tmp_path / "output",
            entity_registry=registry,
        )

        npc_files = list((pack_dir / "npcs").glob("*.md"))
        assert len(npc_files) == 1
        fm, body = read_markdown_with_frontmatter(npc_files[0])
        assert fm["title"] == "The Shadow Broker"
        assert fm["entity_id"] == "shadow_broker"
        assert fm.get("promoted") is True

    def test_no_duplicate_for_existing_primary(self, tmp_path):
        """Entity that already has a primary file is not promoted."""
        enriched_files = _make_enriched_files(tmp_path)
        config = IngestConfig(pack_id="test_pack", pack_name="Test Pack")

        registry = EntityRegistry()
        # "neon_dragon" already has a primary enriched file
        registry.add(EntityEntry(
            id="neon_dragon",
            name="The Neon Dragon",
            entity_type="location",
            description="A bar in the neon district.",
            source_segments=["seg_0001"],
        ))

        assembler = PackAssembler()
        pack_dir = assembler.assemble(
            enriched_files, config, tmp_path / "output",
            entity_registry=registry,
        )

        location_files = list((pack_dir / "locations").glob("*.md"))
        # Should only have the original file, not a promoted duplicate
        assert len(location_files) == 1

    def test_skips_entity_with_insufficient_content(self, tmp_path):
        """Entity with <200 words of aggregated content is not promoted."""
        enriched_dir = tmp_path / "enriched"
        (enriched_dir / "cultures").mkdir(parents=True)
        f1_path = enriched_dir / "cultures" / "short_ref.md"
        write_markdown(
            f1_path,
            "Brief mention of a fixer.",
            {
                "title": "Short Ref",
                "type": "culture",
                "entity_id": "short_ref",
                "entity_refs": ["the_fixer"],
            },
        )

        enriched_files = [{
            "path": str(f1_path),
            "title": "Short Ref",
            "file_type": "culture",
            "entity_id": "short_ref",
            "frontmatter": {
                "title": "Short Ref",
                "type": "culture",
                "entity_id": "short_ref",
                "entity_refs": ["the_fixer"],
            },
        }]

        registry = EntityRegistry()
        registry.add(EntityEntry(
            id="the_fixer",
            name="The Fixer",
            entity_type="npc",
            source_segments=["seg_0001"],
        ))

        config = IngestConfig(pack_id="test_pack", pack_name="Test Pack")
        assembler = PackAssembler()
        pack_dir = assembler.assemble(
            enriched_files, config, tmp_path / "output",
            entity_registry=registry,
        )

        npc_files = list((pack_dir / "npcs").glob("*.md"))
        assert len(npc_files) == 0

    def test_skips_non_promotable_types(self, tmp_path):
        """Entities with general/culture type are not promoted."""
        enriched_files = _make_enriched_files_with_refs(tmp_path)
        config = IngestConfig(pack_id="test_pack", pack_name="Test Pack")

        registry = EntityRegistry()
        registry.add(EntityEntry(
            id="general_concept",
            name="General Concept",
            entity_type="general",
            source_segments=["seg_0001"],
        ))

        assembler = PackAssembler()
        pack_dir = assembler.assemble(
            enriched_files, config, tmp_path / "output",
            entity_registry=registry,
        )

        # No NPC, location, faction, or item files should be created
        for subdir in ["npcs", "locations", "factions", "items"]:
            files = list((pack_dir / subdir).glob("*.md"))
            assert len(files) == 0
