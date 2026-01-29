"""Tests for ingest pipeline utility functions."""

import json
import pytest
from pathlib import Path

from src.ingest.utils import (
    slugify, count_words, parse_page_range,
    write_stage_meta, read_stage_meta,
    write_manifest, read_manifest,
    write_markdown, read_markdown_with_frontmatter,
    ensure_dir,
)


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello_world"

    def test_special_chars(self):
        assert slugify("The Neon Dragon Bar & Grill") == "the_neon_dragon_bar_grill"

    def test_empty(self):
        assert slugify("") == "untitled"

    def test_numbers(self):
        assert slugify("Chapter 1: Overview") == "chapter_1_overview"

    def test_dashes(self):
        assert slugify("some-hyphenated-thing") == "some_hyphenated_thing"


class TestCountWords:
    def test_basic(self):
        assert count_words("one two three") == 3

    def test_empty(self):
        assert count_words("") == 0

    def test_whitespace(self):
        assert count_words("  hello   world  ") == 2


class TestParsePageRange:
    def test_single(self):
        assert parse_page_range("5", 10) == [5]

    def test_range(self):
        assert parse_page_range("1-3", 10) == [1, 2, 3]

    def test_mixed(self):
        assert parse_page_range("1-3,5", 10) == [1, 2, 3, 5]

    def test_all(self):
        assert parse_page_range("all", 5) == [1, 2, 3, 4, 5]

    def test_clamps_to_total(self):
        assert parse_page_range("1-100", 5) == [1, 2, 3, 4, 5]

    def test_deduplicates(self):
        assert parse_page_range("1-3,2-4", 10) == [1, 2, 3, 4]


class TestStageMetadata:
    def test_write_and_read(self, tmp_path):
        meta = {"stage": "extract", "status": "complete"}
        write_stage_meta(tmp_path / "stage1", meta)
        result = read_stage_meta(tmp_path / "stage1")
        assert result == meta

    def test_read_missing(self, tmp_path):
        assert read_stage_meta(tmp_path / "nonexistent") is None


class TestManifest:
    def test_write_and_read(self, tmp_path):
        data = {"key": "value", "list": [1, 2, 3]}
        path = tmp_path / "manifest.json"
        write_manifest(path, data)
        result = read_manifest(path)
        assert result == data


class TestMarkdown:
    def test_write_without_frontmatter(self, tmp_path):
        path = tmp_path / "test.md"
        write_markdown(path, "Hello world")
        assert path.read_text() == "Hello world"

    def test_write_with_frontmatter(self, tmp_path):
        path = tmp_path / "test.md"
        write_markdown(path, "Hello world", {"title": "Test"})
        content = path.read_text()
        assert content.startswith("---")
        assert "title: Test" in content
        assert "Hello world" in content

    def test_roundtrip(self, tmp_path):
        path = tmp_path / "test.md"
        fm = {"title": "Test", "type": "location"}
        write_markdown(path, "Body text here", fm)
        result_fm, result_body = read_markdown_with_frontmatter(path)
        assert result_fm["title"] == "Test"
        assert result_fm["type"] == "location"
        assert result_body == "Body text here"

    def test_read_no_frontmatter(self, tmp_path):
        path = tmp_path / "test.md"
        path.write_text("Just plain text")
        fm, body = read_markdown_with_frontmatter(path)
        assert fm == {}
        assert body == "Just plain text"


class TestEnsureDir:
    def test_creates_dir(self, tmp_path):
        new_dir = tmp_path / "a" / "b" / "c"
        result = ensure_dir(new_dir)
        assert result.exists()
        assert result.is_dir()
        assert result == new_dir

    def test_existing_dir(self, tmp_path):
        result = ensure_dir(tmp_path)
        assert result == tmp_path
