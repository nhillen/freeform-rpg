"""Stage: GM Guidance Extraction.

Extracts storytelling advice, GM techniques, pacing guidance, and other
meta-narrative content from sourcebooks. This content can inform core
prompts and provide pack-specific guidance.

Two output destinations:
1. Pack-specific → storytelling/ directory (genre-specific tips)
2. Universal → Candidates for core prompt refinement (narrator_v0.txt, etc.)
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from .models import (
    ExtractionConfig,
    GuidanceChunk,
    GuidanceExtractionResult,
    Route,
    SegmentEntry,
    SegmentManifest,
)
from .utils import ensure_dir, write_markdown, write_stage_meta

logger = logging.getLogger(__name__)

# Default chapter indicators for GM guidance (when no config provided)
DEFAULT_CHAPTER_INDICATORS = [
    "storytelling", "running the game", "game mastering", "for the gm",
    "referee", "dungeon master", "narrator", "the story", "chronicle",
    "campaign", "adventures", "scenarios", "playing the game",
]

# Default content patterns for GM guidance detection
DEFAULT_CONTENT_PATTERNS = [
    (r"(GM|DM|Storyteller|Referee|Narrator)\s+(should|can|might|may|must)", "gm_technique", 0.8),
    (r"(players|characters)\s+(feel|experience|encounter|discover)", "player_experience", 0.7),
    (r"\b(pacing|tension|escalat|de-escalat|rhythm|flow)\b", "pacing_advice", 0.7),
    (r"\b(mood|tone|atmosphere|ambiance|feel|genre)\b", "tone_guidance", 0.6),
    (r"\b(scene|encounter|session|chapter)\s+(type|kind|example|structure)", "scene_archetype", 0.7),
    (r"\b(consider|try|avoid|remember|don't forget|keep in mind)\b", "advice_language", 0.5),
]

# Patterns that indicate universal vs genre-specific advice
UNIVERSAL_INDICATORS = [
    r"all\s+(games?|rpgs?|stories)",
    r"in\s+any\s+(game|story|scenario)",
    r"general\s+(advice|principle|rule)",
    r"always\s+(consider|remember|try)",
    r"fundamental\s+(principle|technique)",
]

GENRE_SPECIFIC_INDICATORS = [
    r"horror\s+(game|story|scenario)",
    r"(gothic|punk|noir|fantasy|sci-?fi)",
    r"world\s+of\s+darkness",
    r"vampire|werewolf|mage|changeling",
    r"this\s+(setting|world|game)",
]


class GuidanceExtractor:
    """Extracts GM guidance and storytelling advice from sourcebook content."""

    def __init__(
        self,
        llm_gateway=None,
        prompt_registry=None,
        extraction_config: Optional[ExtractionConfig] = None,
    ):
        self.gateway = llm_gateway
        self.registry = prompt_registry
        self.config = extraction_config

    def extract(
        self,
        manifest: SegmentManifest,
        output_dir: str | Path,
        raw_pages_dir: str | Path | None = None,
    ) -> GuidanceExtractionResult:
        """Extract GM guidance from segments.

        Args:
            manifest: Classified segment manifest.
            output_dir: Directory to write extraction results.
            raw_pages_dir: Optional path to raw extracted pages.

        Returns:
            GuidanceExtractionResult with extracted chunks.
        """
        output_dir = Path(output_dir)
        ensure_dir(output_dir)

        # Get chapter indicators from config or use defaults
        chapter_indicators = self._get_chapter_indicators()
        content_patterns = self._get_content_patterns()

        # Find segments likely to contain GM guidance
        guidance_segments = self._identify_guidance_segments(
            manifest.segments, chapter_indicators
        )

        if not guidance_segments:
            logger.info("No GM guidance segments identified")
            return GuidanceExtractionResult()

        logger.info("Found %d potential guidance segments", len(guidance_segments))

        # Extract guidance chunks from segments
        all_chunks: list[GuidanceChunk] = []
        for seg in guidance_segments:
            chunks = self._extract_chunks_from_segment(seg, content_patterns)
            all_chunks.extend(chunks)

        # Classify chunks as universal vs genre-specific
        universal = []
        genre_specific = []
        for chunk in all_chunks:
            chunk.is_universal = self._is_universal_advice(chunk.content)
            if chunk.is_universal:
                universal.append(chunk)
            else:
                genre_specific.append(chunk)

        result = GuidanceExtractionResult(
            chunks=all_chunks,
            universal_candidates=universal,
            genre_specific=genre_specific,
            metadata={
                "segments_analyzed": len(guidance_segments),
                "total_chunks": len(all_chunks),
                "universal_count": len(universal),
                "genre_specific_count": len(genre_specific),
            },
        )

        # Write outputs
        self._write_outputs(output_dir, result)

        write_stage_meta(output_dir, {
            "stage": "gm_guidance_extract",
            "status": "complete",
            "chunks_extracted": len(all_chunks),
            "universal_candidates": len(universal),
            "genre_specific": len(genre_specific),
        })

        logger.info(
            "Extracted %d guidance chunks (%d universal, %d genre-specific)",
            len(all_chunks), len(universal), len(genre_specific)
        )
        return result

    def _get_chapter_indicators(self) -> list[str]:
        """Get chapter indicators from config or use defaults."""
        if self.config and self.config.extraction.gm_guidance.chapter_indicators:
            return [i.lower() for i in self.config.extraction.gm_guidance.chapter_indicators]
        return DEFAULT_CHAPTER_INDICATORS

    def _get_content_patterns(self) -> list[tuple[re.Pattern, str, float]]:
        """Get compiled content patterns from config or use defaults."""
        patterns = []

        if self.config and self.config.extraction.gm_guidance.content_patterns:
            for p in self.config.extraction.gm_guidance.content_patterns:
                try:
                    compiled = re.compile(p.pattern, re.IGNORECASE)
                    patterns.append((compiled, p.meaning, p.confidence))
                except re.error:
                    logger.warning("Invalid pattern in config: %s", p.pattern)

        # Add defaults if no config patterns
        if not patterns:
            for pattern, meaning, conf in DEFAULT_CONTENT_PATTERNS:
                try:
                    compiled = re.compile(pattern, re.IGNORECASE)
                    patterns.append((compiled, meaning, conf))
                except re.error:
                    pass

        return patterns

    def _identify_guidance_segments(
        self,
        segments: list[SegmentEntry],
        chapter_indicators: list[str],
    ) -> list[SegmentEntry]:
        """Identify segments likely to contain GM guidance.

        Criteria:
        1. Source section title matches chapter indicators
        2. Content contains guidance patterns
        3. Segment is routed to LORE or BOTH (not pure SYSTEMS)
        """
        guidance_segments = []

        for seg in segments:
            # Skip pure systems segments
            if seg.route == Route.SYSTEMS:
                continue

            # Check source section title
            source_lower = seg.source_section.lower() if seg.source_section else ""
            title_match = any(ind in source_lower for ind in chapter_indicators)

            # Check segment title
            seg_title_lower = seg.title.lower() if seg.title else ""
            seg_title_match = any(ind in seg_title_lower for ind in chapter_indicators)

            if title_match or seg_title_match:
                guidance_segments.append(seg)

        return guidance_segments

    def _extract_chunks_from_segment(
        self,
        segment: SegmentEntry,
        content_patterns: list[tuple[re.Pattern, str, float]],
    ) -> list[GuidanceChunk]:
        """Extract guidance chunks from a segment.

        Looks for paragraphs that match guidance patterns and
        extracts them as discrete chunks.
        """
        chunks: list[GuidanceChunk] = []
        content = segment.content

        # Split into paragraphs
        paragraphs = re.split(r'\n\s*\n', content)

        for i, para in enumerate(paragraphs):
            if len(para.strip()) < 50:  # Skip very short paragraphs
                continue

            # Check each pattern
            best_match = None
            best_confidence = 0.0

            for pattern, meaning, base_confidence in content_patterns:
                matches = pattern.findall(para)
                if matches:
                    # Boost confidence based on number of matches
                    confidence = min(base_confidence + (len(matches) * 0.05), 0.95)
                    if confidence > best_confidence:
                        best_match = meaning
                        best_confidence = confidence

            # Only extract if we have a meaningful match
            if best_match and best_confidence >= 0.5:
                chunk_id = f"{segment.id}_chunk_{i}"
                chunks.append(GuidanceChunk(
                    id=chunk_id,
                    category=best_match,
                    content=para.strip(),
                    source_page=segment.page_start,
                    source_section=segment.source_section,
                    is_universal=False,  # Will be set later
                    confidence=best_confidence,
                    tags=[],
                ))

        return chunks

    def _is_universal_advice(self, content: str) -> bool:
        """Determine if advice is universal (applicable to any game) or genre-specific.

        Universal advice can be considered for core prompt refinement.
        Genre-specific advice stays in the pack's storytelling/ directory.
        """
        content_lower = content.lower()

        # Check for universal indicators
        universal_score = 0
        for pattern in UNIVERSAL_INDICATORS:
            if re.search(pattern, content_lower):
                universal_score += 1

        # Check for genre-specific indicators
        genre_score = 0
        for pattern in GENRE_SPECIFIC_INDICATORS:
            if re.search(pattern, content_lower):
                genre_score += 1

        # Universal if more universal indicators than genre-specific
        # and at least one universal indicator present
        return universal_score > genre_score and universal_score > 0

    def _write_outputs(self, output_dir: Path, result: GuidanceExtractionResult) -> None:
        """Write extraction outputs."""
        # Write all chunks as JSON
        chunks_data = [
            {
                "id": c.id,
                "category": c.category,
                "content": c.content,
                "source_page": c.source_page,
                "source_section": c.source_section,
                "is_universal": c.is_universal,
                "confidence": c.confidence,
                "tags": c.tags,
            }
            for c in result.chunks
        ]
        (output_dir / "guidance_chunks.json").write_text(
            json.dumps(chunks_data, indent=2, ensure_ascii=False)
        )

        # Write review file for universal candidates
        self._write_review_file(output_dir, result)

        # Write storytelling directory files (grouped by category)
        storytelling_dir = ensure_dir(output_dir / "storytelling")
        self._write_storytelling_files(storytelling_dir, result)

    def _write_review_file(self, output_dir: Path, result: GuidanceExtractionResult) -> None:
        """Write gm_guidance_review.md with candidates for core prompt refinement."""
        lines = [
            "# GM Guidance Review",
            "",
            "This file lists extracted GM guidance that may be candidates for",
            "core prompt refinement (narrator_v0.txt, planner_v0.txt, etc.).",
            "",
            "## Review Process",
            "",
            "1. Read each universal candidate below",
            "2. Decide if it should be added to core prompts",
            "3. If yes, add to appropriate prompt file in src/prompts/",
            "4. Genre-specific advice stays in pack's storytelling/ directory",
            "",
            "---",
            "",
        ]

        # Universal candidates
        if result.universal_candidates:
            lines.append("## Universal Candidates (Consider for Core Prompts)")
            lines.append("")
            for chunk in result.universal_candidates:
                lines.append(f"### [{chunk.category}] {chunk.confidence:.0%} confidence")
                lines.append("")
                lines.append(f"> {chunk.content[:500]}...")
                lines.append("")
                lines.append(f"*Source: {chunk.source_section}, page {chunk.source_page}*")
                lines.append("")
                lines.append("---")
                lines.append("")
        else:
            lines.append("*No universal candidates found.*")
            lines.append("")

        # Genre-specific summary
        if result.genre_specific:
            lines.append("## Genre-Specific (Keep in Pack)")
            lines.append("")
            lines.append(f"Found {len(result.genre_specific)} genre-specific guidance chunks.")
            lines.append("These will be included in the pack's storytelling/ directory.")
            lines.append("")

            # Group by category
            by_category: dict[str, int] = {}
            for chunk in result.genre_specific:
                by_category[chunk.category] = by_category.get(chunk.category, 0) + 1

            for cat, count in sorted(by_category.items()):
                lines.append(f"- **{cat}**: {count} chunks")

        (output_dir / "gm_guidance_review.md").write_text("\n".join(lines))

    def _write_storytelling_files(
        self,
        storytelling_dir: Path,
        result: GuidanceExtractionResult,
    ) -> None:
        """Write storytelling files grouped by category."""
        # Group chunks by category
        by_category: dict[str, list[GuidanceChunk]] = {}
        for chunk in result.chunks:
            if chunk.category not in by_category:
                by_category[chunk.category] = []
            by_category[chunk.category].append(chunk)

        # Write a file per category
        for category, chunks in by_category.items():
            filename = f"{category}.md"
            filepath = storytelling_dir / filename

            lines = [
                f"# {category.replace('_', ' ').title()}",
                "",
                f"*{len(chunks)} guidance excerpts*",
                "",
                "---",
                "",
            ]

            for chunk in sorted(chunks, key=lambda c: -c.confidence):
                universal_tag = " [UNIVERSAL]" if chunk.is_universal else ""
                lines.append(f"## {chunk.confidence:.0%} confidence{universal_tag}")
                lines.append("")
                lines.append(chunk.content)
                lines.append("")
                lines.append(f"*Source: {chunk.source_section}*")
                lines.append("")
                lines.append("---")
                lines.append("")

            filepath.write_text("\n".join(lines))
            logger.debug("Wrote %d chunks to %s", len(chunks), filepath)
