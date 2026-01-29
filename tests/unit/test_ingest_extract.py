"""Tests for Stage 1: PDF Extraction."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.ingest.extract import PDFExtractor
from src.ingest.models import ExtractionResult


class TestPDFExtractor:
    def test_missing_pdf_raises(self, tmp_path):
        pytest.importorskip("fitz", reason="pymupdf not installed")
        extractor = PDFExtractor()
        with pytest.raises(FileNotFoundError):
            extractor.extract(
                pdf_path=tmp_path / "nonexistent.pdf",
                output_dir=tmp_path / "output",
            )

    def test_extract_writes_page_map(self, tmp_path):
        """Test extraction with a mock fitz module."""
        fitz = pytest.importorskip("fitz", reason="pymupdf not installed")

        # Create a minimal mock PDF
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Page 1 text content here."
        mock_page.get_images.return_value = []
        mock_page.rect = MagicMock()
        mock_page.rect.width = 612

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        # Create fake PDF file
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        with patch("src.ingest.extract.PDFExtractor._extract_page_text") as mock_extract:
            mock_extract.return_value = "Page 1 text content here."
            with patch("fitz.open", return_value=mock_doc):
                extractor = PDFExtractor()
                result = extractor.extract(
                    pdf_path=pdf_path,
                    output_dir=tmp_path / "output",
                )

        assert isinstance(result, ExtractionResult)
        assert result.total_pages == 1
        assert len(result.pages) == 1
        assert (tmp_path / "output" / "page_map.json").exists()
        assert (tmp_path / "output" / "stage_meta.json").exists()

    def test_header_footer_stripping(self):
        extractor = PDFExtractor()
        repeated = {"Chapter Title", "Footer Text"}
        text = "Chapter Title\nSome content here.\n42\nFooter Text"
        result = extractor._strip_header_footer(text, repeated)
        assert "Chapter Title" not in result
        assert "Footer Text" not in result
        assert "42" not in result  # page number stripped
        assert "Some content here." in result
