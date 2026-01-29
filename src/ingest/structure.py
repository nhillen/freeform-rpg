"""Stage 2: Document Structure Detection.

Detects the hierarchical structure of the extracted PDF text using
font-size heuristics, ALL-CAPS detection, TOC parsing, and optional
LLM assistance for ambiguous cases.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from .models import ChapterIntent, DocumentStructure, ExtractionResult, SectionNode
from .utils import ensure_dir, write_stage_meta, read_stage_meta

logger = logging.getLogger(__name__)

# Keyword patterns for classifying chapter intent from titles
INTENT_KEYWORDS: dict[ChapterIntent, list[str]] = {
    ChapterIntent.SETTING: [
        r"\bworld\b", r"\bsetting\b", r"\bhistory\b", r"\bdarkness\b",
        r"\bplaces?\b", r"\bintroduction\b",
    ],
    ChapterIntent.FACTIONS: [
        r"\btraditions?\b", r"\bfactions?\b", r"\bclans?\b", r"\bsects?\b",
        r"\borganizations?\b",
    ],
    ChapterIntent.MECHANICS: [
        r"\brules?\b", r"\bspheres?\b", r"\bmagic\b", r"\bcombat\b",
        r"\bcharacter\s+creation\b", r"\btraits?\b", r"\bdisciplines?\b",
        r"\bpowers?\b",
    ],
    ChapterIntent.CHARACTERS: [
        r"\bnpcs?\b", r"\bcharacters?\b", r"\barchetypes?\b", r"\btemplates?\b",
    ],
    ChapterIntent.NARRATIVE: [
        r"\bprologue\b", r"\bfiction\b", r"\bchronicle\b", r"\bstory\b",
    ],
    ChapterIntent.REFERENCE: [
        r"\bappendix\b", r"\bglossary\b", r"\bindex\b", r"\btables?\b",
    ],
    ChapterIntent.META: [
        r"\bcopyright\b", r"\bcredits?\b", r"\btable\s+of\s+contents\b",
        r"\bcontents\b", r"\bisbn\b", r"\backnowledg\w+\b",
        # Publishing / legal
        r"\ball\s+rights\s+reserved\b", r"\bpublished\s+by\b",
        r"\bprinted\s+in\b", r"\bedition\b", r"\bforeword\b",
        r"\bcolophon\b", r"\blegal\s+notice\b", r"\btrademark\b",
        # OGL / license
        r"\bopen\s+game\s+licen[sc]e\b", r"\bogl\b",
        # Portuguese (common in WoD PDFs)
        r"\bdireitos\s+reservados\b", r"\bproibid[ao]?\b",
        r"\breproduc[ãa]o\b", r"\btodos\s+os\s+direitos\b",
        r"\bpublicado\s+por\b", r"\bimpresso\s+em\b",
        # Structural noise
        r"^blank\s+page$",
    ],
    ChapterIntent.EQUIPMENT: [
        r"\bequipment\b", r"\bweapons?\b", r"\bgear\b", r"\bitems?\b",
    ],
    ChapterIntent.BESTIARY: [
        r"\bantagonists?\b", r"\bmonsters?\b", r"\bspirits?\b", r"\bcreatures?\b",
    ],
}


class StructureDetector:
    """Detects document hierarchy from extracted pages."""

    def __init__(self, llm_gateway=None, prompt_registry=None, progress_fn=None):
        """
        Args:
            llm_gateway: Optional LLM gateway for ambiguous structure resolution.
            prompt_registry: Optional prompt registry for loading prompt templates.
            progress_fn: Optional callback for progress updates.
        """
        self.gateway = llm_gateway
        self.registry = prompt_registry
        self._progress = progress_fn or (lambda msg: None)

    def detect(
        self,
        extraction: ExtractionResult,
        output_dir: str | Path,
        pdf_path: Optional[str | Path] = None,
    ) -> DocumentStructure:
        """Detect document structure from extracted pages.

        Args:
            extraction: Result from Stage 1 extraction.
            output_dir: Directory to write structure data.
            pdf_path: Original PDF path (for font-size analysis).

        Returns:
            DocumentStructure with section hierarchy.
        """
        output_dir = Path(output_dir)

        # Try font-size analysis if PDF is available
        font_headings = []
        if pdf_path:
            self._progress("Analyzing PDF font sizes")
            font_headings = self._detect_font_headings(Path(pdf_path))

        # Heuristic heading detection from text
        self._progress("Detecting text headings")
        text_headings = self._detect_text_headings(extraction)

        # Merge heading sources, preferring font-based when available
        headings = font_headings if font_headings else text_headings

        # Try to find and parse TOC
        toc_sections = self._parse_toc(extraction)
        if toc_sections:
            headings = self._merge_toc_with_headings(toc_sections, headings)

        # Build section tree
        if headings:
            self._progress(f"Building section tree ({len(headings)} headings)")
            sections = self._build_section_tree(headings, extraction)
        else:
            self._progress("LLM structure detection")
            sections = self._llm_detect_structure(extraction)

        # Classify chapter intent for each root section
        for section in sections:
            section.intent = self._classify_intent(section.title)
            for child in section.children:
                child_intent = self._classify_intent(child.title)
                # Children inherit parent intent unless they have a stronger signal
                child.intent = child_intent if child_intent != ChapterIntent.UNKNOWN else section.intent

        # Detect document title
        title = self._detect_title(extraction, sections)

        structure = DocumentStructure(
            title=title,
            sections=sections,
            metadata={
                "detection_method": "font" if font_headings else
                                   "toc" if toc_sections else
                                   "text_heuristic" if text_headings else
                                   "llm",
                "heading_count": len(headings),
            }
        )

        # Write outputs
        chapters_dir = ensure_dir(output_dir / "chapters")
        self._write_chapter_files(sections, extraction, chapters_dir)

        # Write structure.json
        structure_data = self._structure_to_dict(structure)
        (output_dir / "structure.json").write_text(
            json.dumps(structure_data, indent=2, ensure_ascii=False)
        )

        write_stage_meta(output_dir, {
            "stage": "structure",
            "status": "complete",
            "title": title,
            "sections_found": len(sections),
            "detection_method": structure.metadata["detection_method"],
        })

        logger.info(
            "Detected %d top-level sections in '%s'",
            len(sections), title
        )
        return structure

    def _detect_font_headings(self, pdf_path: Path) -> list[dict]:
        """Detect headings using font-size analysis from the PDF."""
        try:
            import fitz
        except ImportError:
            return []

        if not pdf_path.exists():
            return []

        doc = fitz.open(str(pdf_path))
        font_sizes: dict[float, list[dict]] = {}

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block.get("type") != 0:  # text blocks only
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        size = round(span["size"], 1)
                        text = span["text"].strip()
                        if text and len(text) > 2:
                            if size not in font_sizes:
                                font_sizes[size] = []
                            font_sizes[size].append({
                                "text": text,
                                "page": page_idx + 1,
                                "size": size,
                                "bold": "bold" in span.get("font", "").lower(),
                            })

        doc.close()

        if not font_sizes:
            return []

        # Sort sizes descending — largest fonts are likely headings
        sorted_sizes = sorted(font_sizes.keys(), reverse=True)

        # Body text is the most common font size
        body_size = max(font_sizes, key=lambda s: len(font_sizes[s]))

        headings = []
        for size in sorted_sizes:
            if size <= body_size:
                break
            entries = font_sizes[size]
            # Skip sizes with too many entries (likely body text)
            if len(entries) > 50:
                continue
            level = 1 if size >= body_size * 1.5 else 2
            for entry in entries:
                headings.append({
                    "title": entry["text"],
                    "level": level,
                    "page": entry["page"],
                    "source": "font",
                })

        # Sort by page and vertical position
        headings.sort(key=lambda h: h["page"])
        return headings

    def _detect_text_headings(self, extraction: ExtractionResult) -> list[dict]:
        """Detect headings using text heuristics (ALL-CAPS, markdown headers)."""
        headings = []

        for page_entry in extraction.pages:
            lines = page_entry.text.split("\n")
            for line in lines:
                stripped = line.strip()
                if not stripped or len(stripped) < 3:
                    continue

                # Markdown-style headers
                md_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
                if md_match:
                    level = len(md_match.group(1))
                    headings.append({
                        "title": md_match.group(2).strip(),
                        "level": level,
                        "page": page_entry.page_num,
                        "source": "markdown",
                    })
                    continue

                # ALL-CAPS lines (likely chapter headers)
                if (stripped.isupper() and
                        len(stripped) > 3 and
                        len(stripped) < 80 and
                        not stripped.startswith("•") and
                        not re.match(r"^\d+\.\s", stripped)):
                    headings.append({
                        "title": stripped.title(),
                        "level": 1,
                        "page": page_entry.page_num,
                        "source": "allcaps",
                    })
                    continue

                # Numbered section patterns: "1. Title", "Chapter 1: Title"
                numbered = re.match(
                    r"^(?:Chapter\s+)?(\d+)[.:\s]+\s*([A-Z].{2,60})$",
                    stripped, re.IGNORECASE
                )
                if numbered:
                    headings.append({
                        "title": numbered.group(2).strip(),
                        "level": 1,
                        "page": page_entry.page_num,
                        "source": "numbered",
                    })

        return headings

    def _parse_toc(self, extraction: ExtractionResult) -> list[dict] | None:
        """Try to find and parse a Table of Contents."""
        # Look for TOC in the first 10 pages
        toc_pages = extraction.pages[:10]
        toc_text = ""
        for page in toc_pages:
            lower = page.text.lower()
            if ("table of contents" in lower or
                    "contents" == lower.strip() or
                    lower.strip().startswith("contents")):
                toc_text = page.text
                break

        if not toc_text:
            return None

        # Parse TOC entries: "Title ... page_num" or "Title  page_num"
        entries = []
        for line in toc_text.split("\n"):
            # Match patterns like "Chapter Title.....23" or "Chapter Title  23"
            match = re.match(
                r"^(\s*)(.*?)\s*[.·…\s]{3,}\s*(\d+)\s*$",
                line
            )
            if match:
                indent = len(match.group(1))
                title = match.group(2).strip()
                page = int(match.group(3))
                if title and len(title) > 2:
                    level = 1 if indent < 4 else 2
                    entries.append({
                        "title": title,
                        "level": level,
                        "page": page,
                        "source": "toc",
                    })

        return entries if entries else None

    def _merge_toc_with_headings(
        self,
        toc_entries: list[dict],
        text_headings: list[dict]
    ) -> list[dict]:
        """Merge TOC structure with detected text headings.

        TOC provides reliable hierarchy; text headings confirm positions.
        """
        # If TOC has good coverage, prefer it
        if len(toc_entries) >= 3:
            return toc_entries
        return text_headings if text_headings else toc_entries

    def _build_section_tree(
        self,
        headings: list[dict],
        extraction: ExtractionResult
    ) -> list[SectionNode]:
        """Build a section tree from flat heading list."""
        if not headings:
            return []

        max_page = extraction.total_pages

        # Build flat nodes with page ranges
        nodes: list[SectionNode] = []
        for i, h in enumerate(headings):
            page_end = headings[i + 1]["page"] - 1 if i + 1 < len(headings) else max_page
            page_end = max(h["page"], page_end)

            # Collect content for this section
            content_parts = []
            for page_entry in extraction.pages:
                if h["page"] <= page_entry.page_num <= page_end:
                    content_parts.append(page_entry.text)

            node = SectionNode(
                title=h["title"],
                level=h["level"],
                page_start=h["page"],
                page_end=page_end,
                content="\n\n".join(content_parts),
            )
            nodes.append(node)

        # Nest level-2 nodes under level-1 nodes
        root_sections: list[SectionNode] = []
        current_parent: Optional[SectionNode] = None

        for node in nodes:
            if node.level <= 1:
                root_sections.append(node)
                current_parent = node
            else:
                if current_parent:
                    current_parent.children.append(node)
                else:
                    root_sections.append(node)

        return root_sections

    def _llm_detect_structure(
        self,
        extraction: ExtractionResult
    ) -> list[SectionNode]:
        """Use LLM to detect structure when heuristics fail."""
        if not self.gateway or not self.registry:
            # Return single section with all content
            all_text = "\n\n".join(p.text for p in extraction.pages)
            return [SectionNode(
                title="Document",
                level=1,
                page_start=1,
                page_end=extraction.total_pages,
                content=all_text,
            )]

        from ..llm.gateway import load_schema

        prompt_tmpl = self.registry.get_prompt("structure")
        schema = load_schema(prompt_tmpl.schema_name)

        # Send first ~20 pages for structure analysis
        sample_pages = extraction.pages[:20]
        sample_text = "\n\n---PAGE BREAK---\n\n".join(
            f"[Page {p.page_num}]\n{p.text}" for p in sample_pages
        )

        response = self.gateway.run_structured(
            prompt=prompt_tmpl.template,
            input_data={
                "document_text": sample_text,
                "total_pages": extraction.total_pages,
            },
            schema=schema,
            options={"temperature": 0.3, "max_tokens": 4096},
        )

        # Parse LLM response into SectionNode list
        sections_data = response.content.get("sections", [])
        return self._parse_llm_sections(sections_data, extraction)

    def _parse_llm_sections(
        self,
        sections_data: list[dict],
        extraction: ExtractionResult
    ) -> list[SectionNode]:
        """Parse LLM structure response into SectionNode objects."""
        nodes = []
        for s in sections_data:
            page_start = s.get("page_start", 1)
            page_end = s.get("page_end", extraction.total_pages)

            content_parts = []
            for p in extraction.pages:
                if page_start <= p.page_num <= page_end:
                    content_parts.append(p.text)

            children = []
            for child in s.get("children", []):
                child_start = child.get("page_start", page_start)
                child_end = child.get("page_end", page_end)
                child_content = []
                for p in extraction.pages:
                    if child_start <= p.page_num <= child_end:
                        child_content.append(p.text)

                children.append(SectionNode(
                    title=child.get("title", "Untitled"),
                    level=2,
                    page_start=child_start,
                    page_end=child_end,
                    content="\n\n".join(child_content),
                ))

            nodes.append(SectionNode(
                title=s.get("title", "Untitled"),
                level=1,
                page_start=page_start,
                page_end=page_end,
                content="\n\n".join(content_parts),
                children=children,
            ))

        return nodes

    def _detect_title(
        self,
        extraction: ExtractionResult,
        sections: list[SectionNode]
    ) -> str:
        """Detect the document title."""
        # Try first page
        if extraction.pages:
            first_page = extraction.pages[0].text.strip()
            lines = [l.strip() for l in first_page.split("\n") if l.strip()]
            if lines:
                # First non-empty line on first page is likely the title
                candidate = lines[0]
                if len(candidate) < 100:
                    return candidate

        # Fall back to first section title
        if sections:
            return sections[0].title

        return "Untitled Document"

    def _write_chapter_files(
        self,
        sections: list[SectionNode],
        extraction: ExtractionResult,
        chapters_dir: Path
    ) -> None:
        """Write each section as a separate chapter file."""
        for i, section in enumerate(sections):
            slug = re.sub(r"[^a-z0-9]+", "_", section.title.lower()).strip("_")
            filename = f"{i + 1:02d}_{slug}.md"
            filepath = chapters_dir / filename

            parts = [f"# {section.title}\n"]
            if section.content:
                parts.append(section.content)

            for child in section.children:
                parts.append(f"\n## {child.title}\n")
                if child.content:
                    parts.append(child.content)

            filepath.write_text("\n".join(parts), encoding="utf-8")

    def _classify_intent(self, title: str) -> ChapterIntent:
        """Classify a section's intent from its title using keyword matching.

        Scores each intent by pattern match count. Short titles (<=5 words)
        matching META get priority to avoid ambiguity with titles like
        "Introduction and Contents".
        """
        lower_title = title.lower()
        word_count = len(lower_title.split())

        scores: dict[ChapterIntent, int] = {}
        for intent, patterns in INTENT_KEYWORDS.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, lower_title):
                    score += 1
            if score > 0:
                scores[intent] = score

        if not scores:
            return ChapterIntent.UNKNOWN

        # Short titles matching META get priority (avoids "Introduction and Contents" → SETTING)
        if ChapterIntent.META in scores and word_count <= 5:
            return ChapterIntent.META

        return max(scores, key=scores.get)

    def _structure_to_dict(self, structure: DocumentStructure) -> dict:
        """Serialize DocumentStructure to a JSON-compatible dict."""
        def node_to_dict(node: SectionNode) -> dict:
            return {
                "title": node.title,
                "level": node.level,
                "page_start": node.page_start,
                "page_end": node.page_end,
                "intent": node.intent.value if node.intent else None,
                "children": [node_to_dict(c) for c in node.children],
            }

        return {
            "title": structure.title,
            "sections": [node_to_dict(s) for s in structure.sections],
            "metadata": structure.metadata,
        }
