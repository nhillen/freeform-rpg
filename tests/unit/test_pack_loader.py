"""Tests for content pack loader."""

import pytest
from pathlib import Path

from src.content.pack_loader import PackLoader, PackManifest, ContentFile, _split_frontmatter


TEST_PACK_DIR = Path(__file__).parent.parent / "content_packs" / "test_pack"


class TestPackManifest:
    """Test manifest parsing."""

    def test_parse_manifest(self):
        loader = PackLoader()
        manifest, files = loader.load_pack(TEST_PACK_DIR)
        assert manifest.id == "test_pack"
        assert manifest.name == "Test Pack"
        assert manifest.version == "1.0"
        assert manifest.layer == "adventure"

    def test_manifest_tags(self):
        loader = PackLoader()
        manifest, _ = loader.load_pack(TEST_PACK_DIR)
        assert "test" in manifest.tags
        assert "cyberpunk" in manifest.tags


class TestPackValidation:
    """Test pack validation."""

    def test_valid_pack(self):
        loader = PackLoader()
        result = loader.validate_pack(TEST_PACK_DIR)
        assert result.valid
        assert len(result.errors) == 0
        assert result.file_count >= 2

    def test_missing_directory(self, tmp_path):
        loader = PackLoader()
        result = loader.validate_pack(tmp_path / "nonexistent")
        assert not result.valid
        assert "Not a directory" in result.errors[0]

    def test_missing_manifest(self, tmp_path):
        loader = PackLoader()
        result = loader.validate_pack(tmp_path)
        assert not result.valid
        assert "Missing pack.yaml" in result.errors[0]

    def test_empty_pack_warns(self, tmp_path):
        # Create minimal valid manifest with no content files
        (tmp_path / "pack.yaml").write_text("id: empty\nname: Empty Pack\n")
        loader = PackLoader()
        result = loader.validate_pack(tmp_path)
        assert result.valid  # Empty pack is valid, just warned
        assert any("No content files" in w for w in result.warnings)


class TestLoadPack:
    """Test full pack loading."""

    def test_loads_all_files(self):
        loader = PackLoader()
        manifest, files = loader.load_pack(TEST_PACK_DIR)
        assert len(files) >= 2
        file_types = {f.file_type for f in files}
        assert "location" in file_types
        assert "npc" in file_types

    def test_location_file_parsed(self):
        loader = PackLoader()
        _, files = loader.load_pack(TEST_PACK_DIR)
        location_files = [f for f in files if f.file_type == "location"]
        assert len(location_files) >= 1
        neon = [f for f in location_files if f.entity_id == "neon_dragon"][0]
        assert neon.title == "The Neon Dragon"
        assert "undercity" in neon.frontmatter.get("tags", [])

    def test_npc_file_parsed(self):
        loader = PackLoader()
        _, files = loader.load_pack(TEST_PACK_DIR)
        npc_files = [f for f in files if f.file_type == "npc"]
        assert len(npc_files) >= 1
        viktor = [f for f in npc_files if f.entity_id == "viktor"][0]
        assert viktor.title == "Viktor Volkov"
        assert "fixer" in viktor.frontmatter.get("tags", [])

    def test_invalid_pack_raises(self, tmp_path):
        loader = PackLoader()
        with pytest.raises(ValueError, match="Invalid content pack"):
            loader.load_pack(tmp_path / "nonexistent")


class TestListPacks:
    """Test listing packs in a directory."""

    def test_list_packs(self):
        loader = PackLoader()
        packs_dir = TEST_PACK_DIR.parent  # tests/content_packs/
        manifests = loader.list_packs(packs_dir)
        assert len(manifests) >= 1
        assert any(m.id == "test_pack" for m in manifests)

    def test_list_packs_empty(self, tmp_path):
        loader = PackLoader()
        manifests = loader.list_packs(tmp_path)
        assert manifests == []

    def test_list_packs_nonexistent_dir(self, tmp_path):
        loader = PackLoader()
        manifests = loader.list_packs(tmp_path / "nope")
        assert manifests == []


class TestParseContentFile:
    """Test individual content file parsing."""

    def test_frontmatter_extraction(self):
        loader = PackLoader()
        cf = loader.parse_content_file(
            TEST_PACK_DIR / "locations" / "neon_dragon.md",
            "location"
        )
        assert cf.frontmatter["entity_id"] == "neon_dragon"
        assert cf.title == "The Neon Dragon"
        assert cf.file_type == "location"

    def test_no_frontmatter(self, tmp_path):
        md = tmp_path / "plain.md"
        md.write_text("# Simple File\n\nJust some content.")
        loader = PackLoader()
        cf = loader.parse_content_file(md, "general")
        assert cf.title == "Simple File"
        assert cf.frontmatter == {}

    def test_title_from_filename(self, tmp_path):
        md = tmp_path / "dark_alley.md"
        md.write_text("Some content without headers.")
        loader = PackLoader()
        cf = loader.parse_content_file(md, "location")
        assert cf.title == "Dark Alley"

    def test_type_override_from_frontmatter(self, tmp_path):
        md = tmp_path / "special.md"
        md.write_text("---\ntype: faction\n---\n# The Org\n\nContent.")
        loader = PackLoader()
        cf = loader.parse_content_file(md, "general")
        assert cf.file_type == "faction"


class TestSplitFrontmatter:
    """Test frontmatter splitting utility."""

    def test_with_frontmatter(self):
        fm, body = _split_frontmatter("---\ntitle: Test\n---\nBody text.")
        assert fm["title"] == "Test"
        assert body == "Body text."

    def test_without_frontmatter(self):
        fm, body = _split_frontmatter("Just plain text.")
        assert fm == {}
        assert body == "Just plain text."

    def test_empty_frontmatter(self):
        fm, body = _split_frontmatter("---\n---\nBody.")
        assert fm == {}
        assert body == "Body."

    def test_invalid_yaml_frontmatter(self):
        fm, body = _split_frontmatter("---\n[invalid yaml\n---\nBody.")
        assert fm == {}
