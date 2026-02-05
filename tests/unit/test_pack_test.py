"""Tests for pack-test command: PackTester analysis, scenario gen, probes, report."""

import json
import pytest
import yaml
from pathlib import Path

from src.ingest.pack_test import PackTester, TestReport, format_report
from src.ingest.utils import write_markdown


def _make_pack(tmp_path, pack_id="test_pack", pack_name="Test Pack", files=None):
    """Create a content pack with configurable files.

    If files is None, creates a default set with locations, NPCs, and factions.
    """
    pack_dir = tmp_path / pack_id
    pack_dir.mkdir()

    manifest = {
        "id": pack_id,
        "name": pack_name,
        "version": "1.0",
        "layer": "sourcebook",
        "description": "A test content pack for testing",
    }
    (pack_dir / "pack.yaml").write_text(yaml.dump(manifest))

    if files is None:
        files = _default_files()

    for file_def in files:
        subdir = pack_dir / file_def["dir"]
        subdir.mkdir(exist_ok=True)
        write_markdown(
            subdir / file_def["filename"],
            file_def["body"],
            file_def.get("frontmatter", {}),
        )

    return pack_dir


def _default_files():
    """A minimal set of content files covering multiple types."""
    return [
        {
            "dir": "locations",
            "filename": "shadow_realm.md",
            "body": (
                "# Shadow Realm\n\n"
                "A dark dimension between worlds where shadows gain sentience. "
                "The realm exists at the edge of perception, accessible only through "
                "ancient rituals or moments of extreme emotional distress. "
                "Travelers report whispered voices and shifting landscapes."
            ),
            "frontmatter": {
                "title": "Shadow Realm",
                "type": "location",
                "entity_id": "shadow_realm",
                "tags": ["dark", "otherworld", "dangerous"],
                "entity_refs": ["shadow_realm", "dark_council"],
            },
        },
        {
            "dir": "locations",
            "filename": "crystal_tower.md",
            "body": (
                "# Crystal Tower\n\n"
                "A towering spire of crystallized magic that serves as the "
                "headquarters of the Mage Council. Its halls shimmer with "
                "arcane energy and ancient knowledge lines every wall. "
                "Only those deemed worthy may enter its inner sanctum."
            ),
            "frontmatter": {
                "title": "Crystal Tower",
                "type": "location",
                "entity_id": "crystal_tower",
                "tags": ["magic", "headquarters", "council"],
                "entity_refs": ["crystal_tower", "mage_council"],
            },
        },
        {
            "dir": "npcs",
            "filename": "elder_mage.md",
            "body": (
                "# Elder Mage Aldric\n\n"
                "The oldest living practitioner of the arcane arts. "
                "Aldric has served three generations of the Council and "
                "guards secrets that could reshape reality itself. "
                "His wisdom is matched only by his caution."
            ),
            "frontmatter": {
                "title": "Elder Mage Aldric",
                "type": "npc",
                "entity_id": "elder_mage",
                "tags": ["wise", "ancient", "council"],
                "entity_refs": ["elder_mage", "mage_council"],
            },
        },
        {
            "dir": "npcs",
            "filename": "shadow_knight.md",
            "body": (
                "# Shadow Knight Varek\n\n"
                "A warrior who draws power from the Shadow Realm. "
                "Once a paladin of light, Varek was corrupted during an expedition "
                "into the darkness. Now he serves the Dark Council, hunting "
                "those who oppose the shadow's spread."
            ),
            "frontmatter": {
                "title": "Shadow Knight Varek",
                "type": "npc",
                "entity_id": "shadow_knight",
                "tags": ["warrior", "corrupted", "shadow"],
                "entity_refs": ["shadow_knight", "dark_council", "shadow_realm"],
            },
        },
        {
            "dir": "factions",
            "filename": "mage_council.md",
            "body": (
                "# The Mage Council\n\n"
                "The governing body of all magic users in the known world. "
                "Founded centuries ago to prevent magical catastrophes, the Council "
                "now maintains order through a complex system of laws and enforcement. "
                "Their power is immense but their unity is fragile."
                "\n\n## Structure\n\n"
                "The Council consists of twelve seats, each representing a different "
                "school of magic. Decisions require a simple majority."
            ),
            "frontmatter": {
                "title": "The Mage Council",
                "type": "faction",
                "entity_id": "mage_council",
                "tags": ["government", "magic", "authority"],
                "entity_refs": ["mage_council", "elder_mage", "crystal_tower"],
            },
        },
        {
            "dir": "factions",
            "filename": "dark_council.md",
            "body": (
                "# The Dark Council\n\n"
                "A shadowy organization that seeks to harness the power of the "
                "Shadow Realm for their own purposes. Operating in secret, they "
                "infiltrate governments and magical institutions alike. "
                "Their ultimate goal is the merging of the shadow and material worlds."
            ),
            "frontmatter": {
                "title": "The Dark Council",
                "type": "faction",
                "entity_id": "dark_council",
                "tags": ["shadow", "secret", "antagonist"],
                "entity_refs": ["dark_council", "shadow_realm", "shadow_knight"],
            },
        },
        {
            "dir": "culture",
            "filename": "arcane_traditions.md",
            "body": (
                "# Arcane Traditions\n\n"
                "The practice of magic follows ancient traditions passed down "
                "through apprenticeship. Each school of magic has its own rituals, "
                "philosophies, and methods of channeling arcane energy. "
                "The tension between tradition and innovation drives magical progress."
            ),
            "frontmatter": {
                "title": "Arcane Traditions",
                "type": "culture",
                "entity_id": "arcane_traditions",
                "tags": ["magic", "tradition", "ritual"],
                "entity_refs": ["arcane_traditions", "mage_council"],
            },
        },
    ]


class TestPackTesterBasic:
    """Basic load and analysis tests."""

    def test_loads_and_reports_pack_info(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        assert report.pack_id == "test_pack"
        assert report.pack_name == "Test Pack"
        assert report.file_count == 7
        assert report.chunk_count > 0

    def test_file_distribution(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        assert report.files_by_type["location"] == 2
        assert report.files_by_type["npc"] == 2
        assert report.files_by_type["faction"] == 2
        assert report.files_by_type["culture"] == 1

    def test_chunk_distribution(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        # Should have chunks for each file type
        assert "location" in report.chunks_by_type
        assert "npc" in report.chunks_by_type
        assert "faction" in report.chunks_by_type
        assert report.chunks_by_type["faction"] >= 2  # mage_council has H2 section

    def test_entities_derived_from_files(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        # Should derive entities from file entity_ids
        assert report.entity_count >= 7
        assert "location" in report.entities_by_type
        assert "npc" in report.entities_by_type
        assert "faction" in report.entities_by_type

    def test_samples_populated(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        assert len(report.samples) > 0
        sample = report.samples[0]
        assert "name" in sample
        assert "type" in sample
        assert "chunk_count" in sample
        assert sample["chunk_count"] >= 0


class TestPackTesterScenario:
    """Test scenario generation."""

    def test_scenario_generated(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        scenario_dir = tmp_path / "scenarios"
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=True, scenario_dir=str(scenario_dir))

        assert report.scenario_path is not None
        assert Path(report.scenario_path).exists()

    def test_scenario_is_valid_yaml(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        scenario_dir = tmp_path / "scenarios"
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=True, scenario_dir=str(scenario_dir))

        scenario = yaml.safe_load(Path(report.scenario_path).read_text())
        assert scenario["id"] == "test_pack_test"
        assert "entities" in scenario
        assert "clocks" in scenario
        assert "threads" in scenario
        assert "starting_scene" in scenario
        assert "opening_text" in scenario

    def test_scenario_has_pc_entity(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        scenario_dir = tmp_path / "scenarios"
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=True, scenario_dir=str(scenario_dir))

        scenario = yaml.safe_load(Path(report.scenario_path).read_text())
        pc_entities = [e for e in scenario["entities"] if e["type"] == "pc"]
        assert len(pc_entities) == 1
        assert pc_entities[0]["name"] == "Test Explorer"

    def test_scenario_references_pack(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        scenario_dir = tmp_path / "scenarios"
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=True, scenario_dir=str(scenario_dir))

        scenario = yaml.safe_load(Path(report.scenario_path).read_text())
        assert "test_pack" in scenario["content_packs"]

    def test_scenario_summary_populated(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        scenario_dir = tmp_path / "scenarios"
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=True, scenario_dir=str(scenario_dir))

        summary = report.scenario_summary
        assert summary["pc"] == "Test Explorer"
        assert len(summary["clocks"]) >= 3
        assert len(summary["threads"]) >= 1

    def test_no_scenario_flag(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        assert report.scenario_path is None
        assert report.scenario_summary == {}


class TestPackTesterProbes:
    """Test retrieval probe system."""

    def test_probes_run(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        assert len(report.probes) > 0

    def test_entity_probes_find_chunks(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        # At least some entity probes should return chunks
        entity_probes = [p for p in report.probes if "Entity lookup" in p["description"]]
        hits = [p for p in entity_probes if p["passed"]]
        assert len(hits) > 0

    def test_query_hit_rate_calculated(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        assert 0.0 <= report.query_hit_rate <= 1.0
        assert report.unique_chunks_found >= 0

    def test_chunk_coverage_calculated(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        assert 0.0 <= report.chunk_coverage <= 1.0


class TestPackTesterIssues:
    """Test issue detection."""

    def test_name_matches_id_warning(self, tmp_path):
        # Pack name matches ID verbatim
        pack_dir = _make_pack(tmp_path, pack_id="testpack", pack_name="Testpack")
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        name_issues = [i for i in report.issues if "matches ID" in i["message"]]
        assert len(name_issues) == 1

    def test_clean_name_no_warning(self, tmp_path):
        pack_dir = _make_pack(tmp_path, pack_id="test_pack", pack_name="Test Pack: Adventures")
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        name_issues = [i for i in report.issues if "matches ID" in i["message"]]
        assert len(name_issues) == 0

    def test_small_files_detected(self, tmp_path):
        # Create a pack with a tiny file
        files = [
            {
                "dir": "locations",
                "filename": "tiny.md",
                "body": "# Tiny\n\nSmall.",
                "frontmatter": {"title": "Tiny", "type": "location", "entity_id": "tiny"},
            },
            {
                "dir": "npcs",
                "filename": "normal_npc.md",
                "body": (
                    "# Normal NPC\n\n"
                    "This is a normal NPC with enough text to not trigger the "
                    "small file warning. They have a detailed backstory and "
                    "many interesting characteristics that make them suitable "
                    "for gameplay encounters. Their motivations are complex and "
                    "their relationships with other entities are well-defined. "
                    "This should be well over fifty words by now hopefully."
                ),
                "frontmatter": {"title": "Normal NPC", "type": "npc", "entity_id": "normal_npc"},
            },
        ]
        pack_dir = _make_pack(tmp_path, files=files)
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        small_issues = [i for i in report.issues if "under 50 words" in i["message"]]
        assert len(small_issues) == 1

    def test_missing_type_files_detected(self, tmp_path):
        """Entity registry has locations but pack has no location files."""
        # Create pack with only faction files
        files = [
            {
                "dir": "factions",
                "filename": "guild.md",
                "body": (
                    "# The Guild\n\n"
                    "A powerful organization controlling trade routes. "
                    "They maintain a network of agents across all major cities "
                    "and enforce their monopoly through both legal and illegal means."
                ),
                "frontmatter": {
                    "title": "The Guild",
                    "type": "faction",
                    "entity_id": "the_guild",
                    "tags": ["trade", "power"],
                },
            },
        ]
        pack_dir = _make_pack(tmp_path, files=files)

        # Place an entity registry with a location entity next to the pack
        registry = {
            "entities": [
                {"id": "the_guild", "name": "The Guild", "entity_type": "faction",
                 "description": "Trade guild", "aliases": [], "related_entities": [],
                 "source_segments": []},
                {"id": "market_square", "name": "Market Square", "entity_type": "location",
                 "description": "Central trading area", "aliases": [], "related_entities": [],
                 "source_segments": []},
            ]
        }
        # Write to a location the tester checks
        assemble_dir = pack_dir.parent
        lore_dir = assemble_dir.parent / "05_lore"
        lore_dir.mkdir(parents=True, exist_ok=True)
        # The tester looks relative to pack_dir: pack_dir.parent.parent / "05_lore"
        # pack_dir = tmp_path / "test_pack"
        # So we need: tmp_path.parent / "05_lore" — that won't work.
        # Instead, create the expected structure: .../06_assemble/test_pack/
        real_pack_dir = tmp_path / "06_assemble" / "test_pack"
        real_pack_dir.mkdir(parents=True)
        # Copy pack contents
        import shutil
        for item in pack_dir.iterdir():
            dest = real_pack_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        # Write entity registry at expected location
        lore_dir = tmp_path / "05_lore"
        lore_dir.mkdir(parents=True, exist_ok=True)
        (lore_dir / "entity_registry.json").write_text(json.dumps(registry))

        tester = PackTester(real_pack_dir)
        report = tester.test(generate_scenario=False)

        # Should warn about 0 location files with location entities
        type_issues = [i for i in report.issues if "location" in i["message"] and "0" in i["message"]]
        assert len(type_issues) >= 1


class TestReportFormatting:
    """Test report output formatting."""

    def test_format_returns_string(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        output = report.format()
        assert isinstance(output, str)
        assert len(output) > 100

    def test_format_contains_sections(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        output = report.format()
        assert "Pack Overview" in output
        assert "Content Distribution" in output
        assert "Retrieval Probes" in output
        assert "Issues" in output

    def test_format_contains_pack_name(self, tmp_path):
        pack_dir = _make_pack(tmp_path, pack_name="My Fantasy World")
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        output = report.format()
        assert "My Fantasy World" in output

    def test_format_empty_report(self):
        """Formatting an empty report should not crash."""
        report = TestReport()
        output = format_report(report)
        assert isinstance(output, str)
        assert "Pack Overview" in output

    def test_format_with_scenario(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        scenario_dir = tmp_path / "scenarios"
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=True, scenario_dir=str(scenario_dir))

        output = report.format()
        assert "Test Scenario" in output
        assert "Test Explorer" in output


class TestPackTesterCleanup:
    """Test that temp resources are cleaned up."""

    def test_temp_dir_cleaned_up(self, tmp_path):
        pack_dir = _make_pack(tmp_path)
        tester = PackTester(pack_dir)
        report = tester.test(generate_scenario=False)

        # After test(), the temp dir should be removed
        assert tester._temp_dir is not None
        assert not Path(tester._temp_dir).exists()

    def test_cleanup_on_error(self, tmp_path):
        """Temp dir should be cleaned even if an error occurs mid-test."""
        pack_dir = tmp_path / "nonexistent"
        tester = PackTester(pack_dir)

        with pytest.raises(Exception):
            tester.test(generate_scenario=False)

        # Cleanup should have run (temp_dir may not have been set if error was early)
        if tester._temp_dir:
            assert not Path(tester._temp_dir).exists()
