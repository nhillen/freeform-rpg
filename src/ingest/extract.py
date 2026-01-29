"""Stage 1: PDF Text Extraction.

Extracts text from PDF files using PyMuPDF with optional Tesseract OCR fallback.
Handles multi-column layouts, strips headers/footers, and extracts images.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from .models import ExtractionResult, PageEntry
from .utils import ensure_dir, parse_page_range, write_stage_meta

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extracts text and images from PDF files."""

    def extract(
        self,
        pdf_path: str | Path,
        output_dir: str | Path,
        use_ocr: bool = False,
        pages: Optional[str] = None,
        extract_images: bool = False,
        strip_headers_footers: bool = True,
    ) -> ExtractionResult:
        """Extract text from a PDF file.

        Args:
            pdf_path: Path to the PDF file.
            output_dir: Directory to write extracted pages and metadata.
            use_ocr: Use Tesseract OCR for pages with little/no text.
            pages: Page range spec (e.g. "1-5,8") or None for all.
            extract_images: Extract embedded images to disk.
            strip_headers_footers: Attempt to remove repeated headers/footers.

        Returns:
            ExtractionResult with page data and metadata.
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError(
                "pymupdf is required for PDF extraction. "
                "Install with: pip install 'freeform-rpg[ingest]'"
            )

        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)

        # Determine which pages to process
        if pages:
            page_nums = parse_page_range(pages, total_pages)
        else:
            page_nums = list(range(1, total_pages + 1))

        pages_dir = ensure_dir(output_dir / "pages")
        images_dir = ensure_dir(output_dir / "images") if extract_images else None

        # First pass: collect header/footer candidates
        header_footer_lines = set()
        if strip_headers_footers and len(page_nums) > 4:
            header_footer_lines = self._detect_headers_footers(doc, page_nums)

        page_entries: list[PageEntry] = []

        for page_num in page_nums:
            page_idx = page_num - 1  # fitz uses 0-based
            page = doc[page_idx]

            # Extract text
            text = self._extract_page_text(page)
            ocr_used = False

            # OCR fallback for low-text pages
            if use_ocr and len(text.strip()) < 50:
                ocr_text = self._ocr_page(page)
                if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
                    ocr_used = True

            # Strip headers/footers
            if strip_headers_footers and header_footer_lines:
                text = self._strip_header_footer(text, header_footer_lines)

            # Detect and handle two-column layout
            text = self._handle_columns(page, text)

            # Extract images
            image_paths: list[str] = []
            has_images = len(page.get_images()) > 0
            if extract_images and images_dir and has_images:
                image_paths = self._extract_page_images(
                    doc, page, page_num, images_dir
                )

            entry = PageEntry(
                page_num=page_num,
                text=text.strip(),
                has_images=has_images,
                image_paths=image_paths,
                char_count=len(text.strip()),
                ocr_used=ocr_used,
            )
            page_entries.append(entry)

            # Write individual page markdown
            page_file = pages_dir / f"page_{page_num:04d}.md"
            page_file.write_text(text.strip(), encoding="utf-8")

        doc.close()

        # Write page map
        page_map = {
            str(e.page_num): {
                "char_count": e.char_count,
                "has_images": e.has_images,
                "ocr_used": e.ocr_used,
            }
            for e in page_entries
        }
        page_map_path = output_dir / "page_map.json"
        page_map_path.write_text(json.dumps(page_map, indent=2))

        result = ExtractionResult(
            pdf_path=str(pdf_path),
            total_pages=total_pages,
            pages=page_entries,
            output_dir=str(output_dir),
            metadata={
                "pages_extracted": len(page_entries),
                "ocr_used": any(p.ocr_used for p in page_entries),
                "images_extracted": sum(len(p.image_paths) for p in page_entries),
            },
        )

        # Write stage metadata
        write_stage_meta(output_dir, {
            "stage": "extract",
            "status": "complete",
            "pdf_path": str(pdf_path),
            "total_pages": total_pages,
            "pages_extracted": len(page_entries),
            "ocr_used": result.metadata["ocr_used"],
        })

        logger.info(
            "Extracted %d pages from %s", len(page_entries), pdf_path.name
        )
        return result

    def _extract_page_text(self, page) -> str:
        """Extract text from a single page using PyMuPDF."""
        # Use "text" extraction (preserves reading order)
        return page.get_text("text")

    def _handle_columns(self, page, text: str) -> str:
        """Detect and reorder two-column layout if present.

        Heuristic: if text blocks cluster into two distinct horizontal bands,
        we have a two-column layout and should reorder.
        """
        blocks = page.get_text("blocks")
        if len(blocks) < 4:
            return text

        # Get page midpoint
        page_width = page.rect.width
        midpoint = page_width / 2

        left_blocks = []
        right_blocks = []
        full_width_blocks = []

        for block in blocks:
            if block[6] != 0:  # skip image blocks
                continue
            x0, y0, x1, y1 = block[:4]
            block_text = block[4]
            block_width = x1 - x0

            # Full-width block spans > 70% of page
            if block_width > page_width * 0.7:
                full_width_blocks.append((y0, block_text))
            elif x1 <= midpoint + 20:
                left_blocks.append((y0, block_text))
            elif x0 >= midpoint - 20:
                right_blocks.append((y0, block_text))
            else:
                full_width_blocks.append((y0, block_text))

        # Only reorder if we actually have a two-column layout
        if not left_blocks or not right_blocks:
            return text

        # Sort each column by vertical position
        left_blocks.sort(key=lambda b: b[0])
        right_blocks.sort(key=lambda b: b[0])
        full_width_blocks.sort(key=lambda b: b[0])

        # Reconstruct: full-width header, left column, right column, full-width footer
        parts = []
        # Full-width blocks that come before column content
        col_start_y = min(
            left_blocks[0][0] if left_blocks else 9999,
            right_blocks[0][0] if right_blocks else 9999,
        )
        col_end_y = max(
            left_blocks[-1][0] if left_blocks else 0,
            right_blocks[-1][0] if right_blocks else 0,
        )

        for y, t in full_width_blocks:
            if y < col_start_y:
                parts.append(t.strip())

        for _, t in left_blocks:
            parts.append(t.strip())
        for _, t in right_blocks:
            parts.append(t.strip())

        for y, t in full_width_blocks:
            if y > col_end_y:
                parts.append(t.strip())

        return "\n\n".join(parts)

    def _detect_headers_footers(
        self, doc, page_nums: list[int], sample_size: int = 10
    ) -> set[str]:
        """Detect repeated header/footer lines across pages.

        Lines that appear identically on > 50% of sampled pages
        are likely headers or footers.
        """
        # Sample pages evenly
        step = max(1, len(page_nums) // sample_size)
        sample_pages = page_nums[::step][:sample_size]

        first_lines: dict[str, int] = {}
        last_lines: dict[str, int] = {}

        for page_num in sample_pages:
            text = doc[page_num - 1].get_text("text").strip()
            lines = text.split("\n")
            lines = [l.strip() for l in lines if l.strip()]

            if not lines:
                continue

            # First 2 lines (potential header)
            for line in lines[:2]:
                # Normalize: strip page numbers
                normalized = re.sub(r"^\d+\s*$", "", line).strip()
                normalized = re.sub(r"\s*\d+\s*$", "", normalized).strip()
                if normalized and len(normalized) > 3:
                    first_lines[normalized] = first_lines.get(normalized, 0) + 1

            # Last 2 lines (potential footer)
            for line in lines[-2:]:
                normalized = re.sub(r"^\d+\s*$", "", line).strip()
                normalized = re.sub(r"\s*\d+\s*$", "", normalized).strip()
                if normalized and len(normalized) > 3:
                    last_lines[normalized] = last_lines.get(normalized, 0) + 1

        threshold = len(sample_pages) * 0.5
        repeated = set()
        for line, count in {**first_lines, **last_lines}.items():
            if count >= threshold:
                repeated.add(line)

        return repeated

    def _strip_header_footer(self, text: str, repeated_lines: set[str]) -> str:
        """Remove lines matching known headers/footers."""
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            # Also strip pure page number lines
            if re.match(r"^\d+$", stripped):
                continue
            normalized = re.sub(r"\s*\d+\s*$", "", stripped).strip()
            if normalized in repeated_lines:
                continue
            cleaned.append(line)
        return "\n".join(cleaned)

    def _ocr_page(self, page) -> str:
        """OCR a page using Tesseract via pytesseract."""
        try:
            import pytesseract
            from PIL import Image
            import io

            # Render page to image at 300 DPI
            pix = page.get_pixmap(dpi=300)
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))

            return pytesseract.image_to_string(image)
        except ImportError:
            logger.warning("pytesseract/Pillow not installed, skipping OCR")
            return ""
        except Exception as e:
            logger.warning("OCR failed for page: %s", e)
            return ""

    def _extract_page_images(
        self, doc, page, page_num: int, images_dir: Path
    ) -> list[str]:
        """Extract images from a page to disk."""
        try:
            from PIL import Image
            import io
        except ImportError:
            return []

        extracted = []
        for img_idx, img_info in enumerate(page.get_images()):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                if not base_image:
                    continue

                img_bytes = base_image["image"]
                img_ext = base_image.get("ext", "png")
                img_path = images_dir / f"page{page_num:04d}_img{img_idx}.{img_ext}"
                img_path.write_bytes(img_bytes)
                extracted.append(str(img_path))
            except Exception as e:
                logger.debug("Failed to extract image %d from page %d: %s",
                             img_idx, page_num, e)

        return extracted
