"""Tests for Stage 2: Structure Detection."""

import pytest
from pathlib import Path

from src.ingest.models import DocumentStructure, ExtractionResult, PageEntry, SectionNode
from src.ingest.structure import StructureDetector


def _make_extraction(pages_text: list[str]) -> ExtractionResult:
    """Helper to build an ExtractionResult from page texts."""
    pages = [
        PageEntry(page_num=i + 1, text=text, char_count=len(text))
        for i, text in enumerate(pages_text)
    ]
    return ExtractionResult(
        pdf_path="/tmp/test.pdf",
        total_pages=len(pages),
        pages=pages,
    )


class TestStructureDetector:
    def test_detect_markdown_headings(self, tmp_path):
        extraction = _make_extraction([
            "# Chapter 1: The Undercity\n\nContent about the undercity.",
            "# Chapter 2: The Surface\n\nContent about the surface.",
        ])

        detector = StructureDetector()
        structure = detector.detect(extraction, tmp_path / "output")

        assert isinstance(structure, DocumentStructure)
        assert len(structure.sections) == 2
        assert structure.sections[0].title == "Chapter 1: The Undercity"
        assert structure.sections[1].title == "Chapter 2: The Surface"

    def test_detect_allcaps_headings(self, tmp_path):
        extraction = _make_extraction([
            "NEON DISTRICT\n\nThe neon district is a vibrant area.",
            "SHADOW MARKET\n\nThe shadow market hides in darkness.",
        ])

        detector = StructureDetector()
        structure = detector.detect(extraction, tmp_path / "output")

        assert len(structure.sections) >= 2
        titles = [s.title for s in structure.sections]
        assert "Neon District" in titles
        assert "Shadow Market" in titles

    def test_detect_numbered_sections(self, tmp_path):
        extraction = _make_extraction([
            "1. Introduction\n\nWelcome to the world.\n\n2. Setting\n\nThe year is 2077.",
        ])

        detector = StructureDetector()
        structure = detector.detect(extraction, tmp_path / "output")

        assert len(structure.sections) >= 2

    def test_fallback_single_section(self, tmp_path):
        extraction = _make_extraction([
            "Just plain text without any headers or structure at all.",
        ])

        detector = StructureDetector()
        structure = detector.detect(extraction, tmp_path / "output")

        # Should still produce at least one section
        assert len(structure.sections) >= 1

    def test_writes_output_files(self, tmp_path):
        extraction = _make_extraction([
            "# Chapter 1\n\nContent here.",
        ])

        detector = StructureDetector()
        output_dir = tmp_path / "output"
        detector.detect(extraction, output_dir)

        assert (output_dir / "structure.json").exists()
        assert (output_dir / "chapters").is_dir()
        assert (output_dir / "stage_meta.json").exists()

    def test_title_detection(self, tmp_path):
        extraction = _make_extraction([
            "Undercity Sourcebook\n\nA guide to the dark depths.",
        ])

        detector = StructureDetector()
        structure = detector.detect(extraction, tmp_path / "output")

        assert structure.title == "Undercity Sourcebook"


class TestIntentClassification:
    """Tests for chapter intent classification, including expanded META patterns."""

    def _classify(self, title: str):
        detector = StructureDetector()
        return detector._classify_intent(title)

    def test_basic_meta_copyright(self):
        from src.ingest.models import ChapterIntent
        assert self._classify("Copyright") == ChapterIntent.META

    def test_meta_ogl(self):
        from src.ingest.models import ChapterIntent
        assert self._classify("OGL") == ChapterIntent.META

    def test_meta_open_game_license(self):
        from src.ingest.models import ChapterIntent
        assert self._classify("Open Game License") == ChapterIntent.META

    def test_meta_legal_notice(self):
        from src.ingest.models import ChapterIntent
        assert self._classify("Legal Notice") == ChapterIntent.META

    def test_meta_foreword(self):
        from src.ingest.models import ChapterIntent
        assert self._classify("Foreword") == ChapterIntent.META

    def test_meta_portuguese_direitos(self):
        from src.ingest.models import ChapterIntent
        assert self._classify("Direitos Reservados") == ChapterIntent.META

    def test_meta_portuguese_publicado(self):
        from src.ingest.models import ChapterIntent
        assert self._classify("Publicado Por") == ChapterIntent.META

    def test_meta_portuguese_proibido(self):
        from src.ingest.models import ChapterIntent
        assert self._classify("Proibido") == ChapterIntent.META

    def test_meta_all_rights_reserved(self):
        from src.ingest.models import ChapterIntent
        assert self._classify("All Rights Reserved") == ChapterIntent.META

    def test_non_meta_setting(self):
        from src.ingest.models import ChapterIntent
        assert self._classify("The World of Darkness") == ChapterIntent.SETTING

    def test_non_meta_factions(self):
        from src.ingest.models import ChapterIntent
        assert self._classify("The Traditions") == ChapterIntent.FACTIONS
