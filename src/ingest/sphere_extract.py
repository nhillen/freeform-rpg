"""Dedicated extractor for ranked power systems (Spheres, Disciplines, etc.).

Processes source text section-by-section to extract detailed ranked abilities
without hitting context limits.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SPHERE_EXTRACT_PROMPT = """Extract the ranked abilities for this magic school/sphere/discipline.

## Source Text:
{source_text}

## Instructions:
This text describes a magic school called "{school_name}". Extract all ranked abilities (usually marked with bullet points • or numbers 1-5).

For each rank level, extract:
- rank: The numeric level (1-5)
- name: The ability name at this rank
- description: What this ability allows you to do
- capabilities: Specific things you CAN do at this rank (as a list)
- limitations: What you CANNOT do at this rank (if mentioned)
- conjunctional_uses: Effects when combined with other spheres (if mentioned)

Also extract any named sample effects/rotes mentioned.

Return JSON:
{{
  "school_name": "{school_name}",
  "description": "What this school governs",
  "specialties": ["specialty1", "specialty2"],
  "ranks": [
    {{
      "rank": 1,
      "name": "Ability Name",
      "description": "Full description",
      "capabilities": ["can do X", "can do Y"],
      "limitations": ["cannot do Z"],
      "conjunctional_uses": [{{"combined_with": "Other Sphere", "effect": "what happens"}}]
    }}
  ],
  "sample_rotes": [
    {{"name": "Rote Name", "rank_required": 2, "description": "What it does"}}
  ]
}}
"""


class SphereExtractor:
    """Extracts detailed ranked abilities from magic school descriptions."""

    def __init__(self, llm_gateway):
        self.gateway = llm_gateway

    def extract_sphere(
        self,
        school_name: str,
        source_text: str,
    ) -> Optional[dict]:
        """Extract ranked abilities for a single sphere/school.

        Args:
            school_name: Name of the school (e.g., "Correspondence")
            source_text: Text describing this school's abilities

        Returns:
            Dict with school details and ranked abilities
        """
        prompt = SPHERE_EXTRACT_PROMPT.format(
            source_text=source_text[:40000],  # Increased limit for full rank coverage
            school_name=school_name,
        )

        permissive_schema = {
            "type": "object",
            "additionalProperties": True
        }

        try:
            response = self.gateway.run_structured(
                prompt=prompt,
                input_data={},
                schema=permissive_schema,
                options={"temperature": 0.2, "max_tokens": 4000},
            )

            if isinstance(response.content, dict):
                return response.content
            return None

        except Exception as e:
            logger.warning("Sphere extraction failed for %s: %s", school_name, e)
            return None

    def extract_all_spheres(
        self,
        pages_dir: Path,
        sphere_page_ranges: dict[str, tuple[int, int]],
    ) -> list[dict]:
        """Extract all spheres from their respective page ranges.

        Args:
            pages_dir: Directory containing page_NNNN.md files
            sphere_page_ranges: Dict mapping sphere name to (start_page, end_page)

        Returns:
            List of extracted sphere dicts
        """
        results = []

        for sphere_name, (start_page, end_page) in sphere_page_ranges.items():
            logger.info("Extracting %s (pages %d-%d)...", sphere_name, start_page, end_page)

            # Load pages for this sphere
            text_parts = []
            for page_num in range(start_page, end_page + 1):
                page_path = pages_dir / f"page_{page_num:04d}.md"
                if page_path.exists():
                    text_parts.append(page_path.read_text())

            if not text_parts:
                logger.warning("No pages found for %s", sphere_name)
                continue

            source_text = "\n\n---\n\n".join(text_parts)

            # Extract this sphere
            result = self.extract_sphere(sphere_name, source_text)
            if result:
                results.append(result)
                logger.info("  Extracted %d ranks for %s",
                           len(result.get("ranks", [])), sphere_name)

        return results


def _page_has_ranked_abilities(content: str) -> bool:
    """Check if a page contains ranked ability markers (• or • •, etc.)."""
    # WoD uses bullet points for ranks: •, • •, • • •, etc.
    # Look for "• " followed by a capitalized word (ability name)
    return bool(re.search(r"^• +[A-Z]", content, re.MULTILINE))


def _page_has_sphere_specialties(content: str, sphere_name: str) -> bool:
    """Check if page has sphere header followed by Specialties line."""
    # Pattern: sphere name on its own line, then Specialties: within a few lines
    pattern = rf"{sphere_name}\s*\n\s*\nSpecialties:"
    return bool(re.search(pattern, content))


def find_sphere_page_ranges(pages_dir: Path) -> dict[str, tuple[int, int]]:
    """Auto-detect page ranges for each sphere by scanning for headers.

    Validates that detected pages contain actual ranked abilities (• markers)
    to distinguish detail pages from overview/theory pages that merely mention
    sphere names.

    Args:
        pages_dir: Directory containing page_NNNN.md files

    Returns:
        Dict mapping sphere name to (start_page, end_page)
    """
    # Known WoD Mage spheres
    sphere_names = [
        "Correspondence", "Entropy", "Forces", "Life",
        "Matter", "Mind", "Prime", "Spirit", "Time"
    ]

    sphere_starts = {}

    # Scan pages for sphere detail sections (not just mentions)
    page_files = sorted(pages_dir.glob("page_*.md"))
    for page_path in page_files:
        page_num = int(page_path.stem.split("_")[1])
        content = page_path.read_text()

        for sphere in sphere_names:
            if sphere in sphere_starts:
                continue  # Already found this sphere's detail page

            # Method 1: Sphere name followed by "Specialties:" (strongest signal)
            if _page_has_sphere_specialties(content, sphere):
                sphere_starts[sphere] = page_num
                logger.debug("Found %s (via Specialties) at page %d", sphere, page_num)
                continue

            # Method 2: Sphere header + ranked abilities on same page
            has_header = bool(re.search(rf"^\s*{sphere}\s*$", content, re.MULTILINE))
            has_ranks = _page_has_ranked_abilities(content)

            if has_header and has_ranks:
                sphere_starts[sphere] = page_num
                logger.debug("Found %s (via ranked abilities) at page %d", sphere, page_num)

    # For any spheres not found, try a broader search looking for
    # pages with ranked abilities that mention the sphere name anywhere
    for sphere in sphere_names:
        if sphere in sphere_starts:
            continue

        for page_path in page_files:
            page_num = int(page_path.stem.split("_")[1])
            content = page_path.read_text()

            # Sphere mentioned anywhere + has ranked abilities
            if sphere in content and _page_has_ranked_abilities(content):
                # Verify this isn't already assigned to another sphere
                if page_num not in sphere_starts.values():
                    sphere_starts[sphere] = page_num
                    logger.debug("Found %s (fallback) at page %d", sphere, page_num)
                    break

    # Calculate ranges (each sphere ends where the next begins)
    # Include the next sphere's start page since spheres often share pages
    # (e.g., Mind rank 5 and Prime rank 1 can both be on page 141)
    ranges = {}
    sorted_spheres = sorted(sphere_starts.items(), key=lambda x: x[1])

    for i, (sphere, start) in enumerate(sorted_spheres):
        if i + 1 < len(sorted_spheres):
            # Include next sphere's start page (they may share it)
            end = sorted_spheres[i + 1][1]
        else:
            # Last sphere - extend a few pages
            end = start + 10

        ranges[sphere] = (start, end)

    return ranges


def extract_spheres_from_pdf(
    pages_dir: Path,
    output_path: Path,
    llm_gateway,
) -> list[dict]:
    """Main entry point for sphere extraction.

    Args:
        pages_dir: Directory with extracted PDF pages
        output_path: Where to write the output YAML
        llm_gateway: LLM gateway instance

    Returns:
        List of extracted sphere dicts
    """
    import yaml

    # Find sphere page ranges
    ranges = find_sphere_page_ranges(pages_dir)
    if not ranges:
        logger.warning("No sphere sections found")
        return []

    logger.info("Found %d spheres: %s", len(ranges), list(ranges.keys()))

    # Extract each sphere
    extractor = SphereExtractor(llm_gateway)
    spheres = extractor.extract_all_spheres(pages_dir, ranges)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.dump({"spheres": spheres}, default_flow_style=False, allow_unicode=True),
        encoding="utf-8"
    )

    logger.info("Wrote %d spheres to %s", len(spheres), output_path)
    return spheres
