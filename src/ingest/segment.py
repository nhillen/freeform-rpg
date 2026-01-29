"""Stage 3: Content Segmentation.

Splits structured document sections into content segments of appropriate
size (100-1500 words) for RAG indexing. Uses header-boundary splitting
for clean chapters and LLM assistance for mixed-content chapters.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from .models import (
    ChapterIntent, DocumentStructure, SectionNode, SegmentEntry, SegmentManifest
)
from .utils import count_words, ensure_dir, slugify, write_stage_meta

logger = logging.getLogger(__name__)


class ContentSegmenter:
    """Segments document sections into indexable chunks."""

    def __init__(
        self,
        llm_gateway=None,
        prompt_registry=None,
        min_words: int = 100,
        max_words: int = 1500,
        target_words: int = 400,
        progress_fn=None,
    ):
        self.gateway = llm_gateway
        self.registry = prompt_registry
        self.min_words = min_words
        self.max_words = max_words
        self.target_words = target_words
        self._progress = progress_fn or (lambda msg: None)

    def segment(
        self,
        structure: DocumentStructure,
        output_dir: str | Path,
    ) -> SegmentManifest:
        """Segment a structured document into content chunks.

        Args:
            structure: Document structure from Stage 2.
            output_dir: Directory to write segments.

        Returns:
            SegmentManifest with all segments.
        """
        output_dir = Path(output_dir)
        segments: list[SegmentEntry] = []
        seg_counter = 0
        filtered_count = 0
        total_sections = len(structure.sections)

        for sec_idx, section in enumerate(structure.sections):
            self._progress(
                f"Section {sec_idx + 1}/{total_sections}: {section.title[:40]}"
            )
            # Filter META-intent sections (copyright, credits, ToC)
            if section.intent == ChapterIntent.META:
                logger.info("Filtered META section: '%s'", section.title)
                filtered_count += 1
                continue

            section_segments = self._segment_section(section, seg_counter)
            segments.extend(section_segments)
            seg_counter += len(section_segments)

            # Also process children
            for child in section.children:
                if child.intent == ChapterIntent.META:
                    logger.info("Filtered META child section: '%s'", child.title)
                    filtered_count += 1
                    continue
                child_segments = self._segment_section(child, seg_counter)
                segments.extend(child_segments)
                seg_counter += len(child_segments)

        # Secondary META content filter
        pre_filter = len(segments)
        segments = [s for s in segments if not self._is_meta_content(s)]
        secondary_filtered = pre_filter - len(segments)
        if secondary_filtered:
            logger.info("Secondary META filter removed %d segments", secondary_filtered)
        filtered_count += secondary_filtered

        # Enforce size constraints
        self._progress(f"Enforcing size constraints on {len(segments)} segments")
        segments = self._enforce_sizes(segments)

        total_words = sum(s.word_count for s in segments)
        manifest = SegmentManifest(
            segments=segments,
            total_words=total_words,
            metadata={
                "segment_count": len(segments),
                "avg_words": total_words // max(len(segments), 1),
                "meta_filtered": filtered_count,
            }
        )

        # Write outputs
        self._write_segments(segments, output_dir)
        self._write_manifest(manifest, output_dir)

        write_stage_meta(output_dir, {
            "stage": "segment",
            "status": "complete",
            "segment_count": len(segments),
            "total_words": total_words,
        })

        logger.info("Created %d segments (%d total words)", len(segments), total_words)
        return manifest

    def _segment_section(
        self,
        section: SectionNode,
        start_id: int
    ) -> list[SegmentEntry]:
        """Segment a single section by header boundaries."""
        content = section.content
        if not content or not content.strip():
            return []

        word_count = count_words(content)

        # Always try header-boundary splitting first
        sub_sections = self._split_by_headers(content)

        if len(sub_sections) > 1:
            segments = []
            for i, sub in enumerate(sub_sections):
                sub_title = sub["title"] or f"{section.title} (Part {i + 1})"
                sub_wc = count_words(sub["content"])
                segments.append(SegmentEntry(
                    id=f"seg_{start_id + i:04d}",
                    title=sub_title,
                    content=sub["content"].strip(),
                    source_section=section.title,
                    page_start=section.page_start,
                    page_end=section.page_end,
                    word_count=sub_wc,
                    chapter_intent=section.intent,
                ))
            return segments

        # No sub-headers found — fits in one segment?
        if word_count <= self.max_words:
            return [SegmentEntry(
                id=f"seg_{start_id:04d}",
                title=section.title,
                content=content.strip(),
                source_section=section.title,
                page_start=section.page_start,
                page_end=section.page_end,
                word_count=word_count,
                chapter_intent=section.intent,
            )]

        # Large section with no sub-headers — try LLM splitting
        if self.gateway and self.registry:
            return self._llm_split_section(section, start_id)

        # Fallback: paragraph-boundary splitting
        return self._paragraph_split(section, start_id)

    def _split_by_headers(self, content: str) -> list[dict]:
        """Split content by markdown headers (H2, H3)."""
        lines = content.split("\n")
        sections = []
        current_title = ""
        current_lines: list[str] = []

        for line in lines:
            header_match = re.match(r"^(#{2,4})\s+(.+)$", line)
            if header_match:
                # Flush current section
                if current_lines or current_title:
                    sections.append({
                        "title": current_title,
                        "content": "\n".join(current_lines),
                    })
                current_title = header_match.group(2).strip()
                current_lines = []
            else:
                current_lines.append(line)

        # Flush remaining
        if current_lines or current_title:
            sections.append({
                "title": current_title,
                "content": "\n".join(current_lines),
            })

        return sections

    def _paragraph_split(
        self,
        section: SectionNode,
        start_id: int
    ) -> list[SegmentEntry]:
        """Split by paragraph boundaries to stay within word limits."""
        paragraphs = re.split(r"\n\s*\n", section.content)
        segments = []
        current_parts: list[str] = []
        current_words = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            para_words = count_words(para)

            if current_words + para_words > self.max_words and current_parts:
                # Flush current segment
                seg_id = start_id + len(segments)
                segments.append(SegmentEntry(
                    id=f"seg_{seg_id:04d}",
                    title=f"{section.title} (Part {len(segments) + 1})",
                    content="\n\n".join(current_parts),
                    source_section=section.title,
                    page_start=section.page_start,
                    page_end=section.page_end,
                    word_count=current_words,
                    chapter_intent=section.intent,
                ))
                current_parts = []
                current_words = 0

            current_parts.append(para)
            current_words += para_words

        # Flush remaining
        if current_parts:
            seg_id = start_id + len(segments)
            segments.append(SegmentEntry(
                id=f"seg_{seg_id:04d}",
                title=f"{section.title}" + (
                    f" (Part {len(segments) + 1})" if segments else ""
                ),
                content="\n\n".join(current_parts),
                source_section=section.title,
                page_start=section.page_start,
                page_end=section.page_end,
                word_count=current_words,
                chapter_intent=section.intent,
            ))

        return segments

    def _llm_split_section(
        self,
        section: SectionNode,
        start_id: int
    ) -> list[SegmentEntry]:
        """Use LLM to determine optimal split points for mixed content."""
        from ..llm.gateway import load_schema

        prompt_tmpl = self.registry.get_prompt("segment")
        schema = load_schema(prompt_tmpl.schema_name)

        # Truncate if needed to fit in context
        content = section.content
        if count_words(content) > 5000:
            words = content.split()
            content = " ".join(words[:5000])

        response = self.gateway.run_structured(
            prompt=prompt_tmpl.template,
            input_data={
                "section_title": section.title,
                "section_content": content,
                "target_words": self.target_words,
                "max_words": self.max_words,
            },
            schema=schema,
            options={"temperature": 0.3, "max_tokens": 4096},
        )

        segments_data = response.content.get("segments", [])
        segments = []
        for i, seg_data in enumerate(segments_data):
            seg_id = start_id + i
            seg_content = seg_data.get("content", "")
            segments.append(SegmentEntry(
                id=f"seg_{seg_id:04d}",
                title=seg_data.get("title", f"{section.title} (Part {i + 1})"),
                content=seg_content,
                source_section=section.title,
                page_start=section.page_start,
                page_end=section.page_end,
                word_count=count_words(seg_content),
                chapter_intent=section.intent,
            ))

        # Fallback if LLM produced nothing useful
        if not segments:
            return self._paragraph_split(section, start_id)

        return segments

    # Patterns indicating non-content (legal, copyright, structural noise)
    _META_BODY_PATTERNS = [
        re.compile(r"\bisbn[\s:\-]*[\dxX\-]{10,}", re.IGNORECASE),
        re.compile(r"\ball\s+rights\s+reserved\b", re.IGNORECASE),
        re.compile(r"\bopen\s+game\s+licen[sc]e\b", re.IGNORECASE),
        re.compile(r"\bdireitos\s+reservados\b", re.IGNORECASE),
        re.compile(r"\btodos\s+os\s+direitos\b", re.IGNORECASE),
        re.compile(r"\bproibid[ao]?\b", re.IGNORECASE),
        re.compile(r"\breproduc[ãa]o\b", re.IGNORECASE),
        re.compile(r"\bpublicado\s+por\b", re.IGNORECASE),
    ]

    def _is_meta_content(self, segment: SegmentEntry) -> bool:
        """Check if a segment contains non-content (legal, copyright, noise).

        Returns True if the segment should be filtered out.
        """
        content = segment.content.strip()

        # Very short all-caps text is likely a header/footer artifact
        if len(content) < 100 and content == content.upper() and content.replace(" ", "").isalpha():
            logger.debug("Filtered short all-caps segment: '%s'", segment.title)
            return True

        # Check for legal/copyright body patterns
        match_count = sum(1 for pat in self._META_BODY_PATTERNS if pat.search(content))
        # If multiple meta patterns match, it's almost certainly boilerplate
        if match_count >= 2:
            logger.debug("Filtered meta-body segment (%d matches): '%s'", match_count, segment.title)
            return True

        # Very short segment dominated by a single meta pattern
        if match_count >= 1 and segment.word_count < 50:
            logger.debug("Filtered short meta segment: '%s'", segment.title)
            return True

        return False

    def _enforce_sizes(self, segments: list[SegmentEntry]) -> list[SegmentEntry]:
        """Merge undersized segments and split oversized ones."""
        result: list[SegmentEntry] = []

        i = 0
        while i < len(segments):
            seg = segments[i]

            # Merge undersized segments with the next one
            if seg.word_count < self.min_words and i + 1 < len(segments):
                next_seg = segments[i + 1]
                merged = SegmentEntry(
                    id=seg.id,
                    title=seg.title,
                    content=seg.content + "\n\n" + next_seg.content,
                    source_section=seg.source_section,
                    page_start=seg.page_start,
                    page_end=next_seg.page_end,
                    word_count=seg.word_count + next_seg.word_count,
                    chapter_intent=seg.chapter_intent,
                )
                result.append(merged)
                i += 2
                continue

            # Split oversized segments by paragraph
            if seg.word_count > self.max_words * 1.5:
                parts = self._force_split(seg)
                result.extend(parts)
                i += 1
                continue

            result.append(seg)
            i += 1

        return result

    def _force_split(self, segment: SegmentEntry) -> list[SegmentEntry]:
        """Force-split an oversized segment by paragraphs, then by word count."""
        paragraphs = re.split(r"\n\s*\n", segment.content)

        # If no paragraph breaks, split by word count directly
        if len(paragraphs) <= 1:
            return self._word_boundary_split(segment)

        parts: list[SegmentEntry] = []
        current_lines: list[str] = []
        current_words = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            wc = count_words(para)

            if current_words + wc > self.max_words and current_lines:
                parts.append(SegmentEntry(
                    id=f"{segment.id}_p{len(parts)}",
                    title=f"{segment.title} (Part {len(parts) + 1})",
                    content="\n\n".join(current_lines),
                    source_section=segment.source_section,
                    page_start=segment.page_start,
                    page_end=segment.page_end,
                    word_count=current_words,
                    chapter_intent=segment.chapter_intent,
                ))
                current_lines = []
                current_words = 0

            current_lines.append(para)
            current_words += wc

        if current_lines:
            parts.append(SegmentEntry(
                id=f"{segment.id}_p{len(parts)}",
                title=segment.title + (
                    f" (Part {len(parts) + 1})" if parts else ""
                ),
                content="\n\n".join(current_lines),
                source_section=segment.source_section,
                page_start=segment.page_start,
                page_end=segment.page_end,
                word_count=current_words,
                chapter_intent=segment.chapter_intent,
            ))

        return parts if parts else [segment]

    def _word_boundary_split(self, segment: SegmentEntry) -> list[SegmentEntry]:
        """Split a segment by word count when there are no paragraph breaks."""
        words = segment.content.split()
        parts: list[SegmentEntry] = []

        for i in range(0, len(words), self.max_words):
            chunk_words = words[i:i + self.max_words]
            chunk_text = " ".join(chunk_words)
            parts.append(SegmentEntry(
                id=f"{segment.id}_p{len(parts)}",
                title=f"{segment.title} (Part {len(parts) + 1})",
                content=chunk_text,
                source_section=segment.source_section,
                page_start=segment.page_start,
                page_end=segment.page_end,
                word_count=len(chunk_words),
                chapter_intent=segment.chapter_intent,
            ))

        return parts if parts else [segment]

    def _write_segments(
        self,
        segments: list[SegmentEntry],
        output_dir: Path
    ) -> None:
        """Write segment files organized by type."""
        segments_dir = ensure_dir(output_dir / "segments")
        for seg in segments:
            slug = slugify(seg.title)
            filename = f"{seg.id}_{slug}.md"
            filepath = segments_dir / filename
            filepath.write_text(
                f"# {seg.title}\n\n{seg.content}",
                encoding="utf-8"
            )

    def _write_manifest(
        self,
        manifest: SegmentManifest,
        output_dir: Path
    ) -> None:
        """Write segment manifest JSON."""
        data = {
            "segments": [
                {
                    "id": s.id,
                    "title": s.title,
                    "source_section": s.source_section,
                    "page_start": s.page_start,
                    "page_end": s.page_end,
                    "word_count": s.word_count,
                    "content_type": s.content_type.value if s.content_type else None,
                    "route": s.route.value if s.route else None,
                    "chapter_intent": s.chapter_intent.value if s.chapter_intent else None,
                    "tags": s.tags,
                }
                for s in manifest.segments
            ],
            "total_words": manifest.total_words,
            "metadata": manifest.metadata,
        }
        (output_dir / "segment_manifest.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False)
        )
