"""Stage 4: Content Classification and Routing.

Classifies segments along two axes:
  1. Content type (location, npc, faction, culture, item, rules, etc.)
  2. Processing route (lore, systems, or both)

Uses regex-based mechanical pattern detection + LLM batch verification.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from .models import ChapterIntent, ContentType, Route, SegmentEntry, SegmentManifest
from .utils import ensure_dir, write_stage_meta

logger = logging.getLogger(__name__)

# Patterns that indicate mechanical/systems content
MECHANICAL_PATTERNS = [
    r"\d+d\d+",                          # dice notation: 2d6, 1d10
    r"\b\d+\s*[-–]\s*\d+\b",            # ranges: 7-9, 10-12
    r"\bDC\s*\d+",                       # difficulty class
    r"\bHP\b|\bhit\s+points?\b",         # hit points
    r"\bAC\b|\barmor\s+class\b",         # armor class
    r"\+\d+\s+to\b",                     # modifiers: +2 to
    r"\bsave\b.*\bDC\b",                 # saving throw DC
    r"\bthreshold\b",                    # threshold triggers
    r"\btrigger\s*[:=]",                 # trigger definitions
    r"\bescalation\b",                   # escalation mechanics
    r"\bclock\b.*\b\d+/\d+\b",          # clock values: 3/6
    r"\bheat\b.*\b\d+\b",               # heat clock
    r"\bharm\b.*\b\d+\b",               # harm clock
    r"\bcred\b.*\b\d+\b",               # cred clock
    r"\bcritical\s*(success|failure)\b", # critical outcomes
    r"\bmixed\s+success\b",             # mixed results
    r"\baction\s+type\b",               # action type definitions
    r"\bstat\s+block\b",                # stat blocks
    r"\bmodifier\b.*[+-]\d+",           # modifiers with values
]

# Patterns indicating specific content types
TYPE_INDICATORS = {
    ContentType.LOCATION: [
        r"\bdistrict\b", r"\bneighborhood\b", r"\bbar\b", r"\bclub\b",
        r"\bbuilding\b", r"\bstreet\b", r"\balley\b", r"\bfloor\b",
        r"\bentrance\b", r"\bexit\b", r"\blocation\b", r"\bvenue\b",
    ],
    ContentType.NPC: [
        r"\bage\s*[:=]?\s*\d+", r"\bappearance\b", r"\bpersonality\b",
        r"\bmotivation\b", r"\bbackground\b", r"\bconnection\b",
        r"\bescalation\s+profile\b", r"\bthreat\s+level\b",
    ],
    ContentType.FACTION: [
        r"\bfaction\b", r"\borganization\b", r"\bgang\b", r"\bcorporation\b",
        r"\bhierarchy\b", r"\bleadership\b", r"\bterritory\b",
        r"\binfluence\b", r"\brival\b", r"\bally\b",
    ],
    ContentType.CULTURE: [
        r"\bculture\b", r"\bcustom\b", r"\btradition\b", r"\bslang\b",
        r"\bfashion\b", r"\bmusic\b", r"\bfood\b", r"\britual\b",
        r"\bsocial\b", r"\bclass\b",
    ],
    ContentType.ITEM: [
        r"\bweapon\b", r"\barmor\b", r"\bgear\b", r"\bequipment\b",
        r"\bitem\b", r"\bcyberware\b", r"\baugmentation\b",
        r"\bcredstick\b", r"\bdevice\b",
    ],
    ContentType.RULES: [
        r"\brule\b", r"\bmechanic\b", r"\bresolution\b", r"\baction\s+type\b",
        r"\bclock\b", r"\bescalation\b", r"\bcalibration\b",
    ],
    ContentType.TABLE: [
        r"\|.*\|.*\|",   # markdown table
        r"\btable\b.*\bresults?\b",
        r"\bd\d+\s+result\b",  # random table: d6 result
    ],
}


# Route bias: added to mechanical_density before route decision
INTENT_ROUTE_BIAS: dict[ChapterIntent, float] = {
    ChapterIntent.MECHANICS: 2.5,
    ChapterIntent.EQUIPMENT: 1.0,
    ChapterIntent.BESTIARY: 1.5,
    ChapterIntent.REFERENCE: 1.0,
    ChapterIntent.SETTING: -1.0,
    ChapterIntent.FACTIONS: -0.5,
    ChapterIntent.CHARACTERS: -0.5,
    ChapterIntent.NARRATIVE: -2.0,
    ChapterIntent.UNKNOWN: 0.0,
    ChapterIntent.META: 0.0,
}

# Type hints: adds 2.0 virtual keyword matches to hinted content types
INTENT_TYPE_HINTS: dict[ChapterIntent, list[ContentType]] = {
    ChapterIntent.SETTING: [ContentType.LOCATION, ContentType.HISTORY, ContentType.CULTURE],
    ChapterIntent.FACTIONS: [ContentType.FACTION],
    ChapterIntent.MECHANICS: [ContentType.RULES],
    ChapterIntent.CHARACTERS: [ContentType.NPC],
    ChapterIntent.EQUIPMENT: [ContentType.ITEM],
    ChapterIntent.BESTIARY: [ContentType.NPC],
    ChapterIntent.REFERENCE: [ContentType.TABLE, ContentType.RULES],
}


class ContentClassifier:
    """Classifies content segments by type and processing route."""

    def __init__(self, llm_gateway=None, prompt_registry=None, progress_fn=None):
        self.gateway = llm_gateway
        self.registry = prompt_registry
        self._mechanical_re = re.compile(
            "|".join(MECHANICAL_PATTERNS), re.IGNORECASE
        )
        self._progress = progress_fn or (lambda msg: None)

    def classify(
        self,
        manifest: SegmentManifest,
        output_dir: str | Path,
    ) -> SegmentManifest:
        """Classify all segments in the manifest.

        Updates each segment's content_type, route, and classification_confidence.

        Args:
            manifest: Segment manifest from Stage 3.
            output_dir: Directory to write updated manifest.

        Returns:
            Updated SegmentManifest with classifications.
        """
        output_dir = Path(output_dir)
        ensure_dir(output_dir)

        # Phase 1: Rule-based classification
        total = len(manifest.segments)
        for i, seg in enumerate(manifest.segments):
            if (i % 10 == 0) or i == total - 1:
                self._progress(f"Rule-classifying segment {i + 1}/{total}")
            self._rule_classify(seg)

        # Phase 2: LLM batch verification for low-confidence segments
        low_confidence = [
            s for s in manifest.segments
            if s.classification_confidence < 0.7
        ]
        if low_confidence and self.gateway and self.registry:
            self._progress(
                f"LLM-verifying {len(low_confidence)} low-confidence segments"
            )
            self._llm_verify_batch(low_confidence)

        # Write updated manifest
        self._write_manifest(manifest, output_dir)

        write_stage_meta(output_dir, {
            "stage": "classify",
            "status": "complete",
            "total_segments": len(manifest.segments),
            "lore_count": sum(
                1 for s in manifest.segments
                if s.route == Route.LORE
            ),
            "systems_count": sum(
                1 for s in manifest.segments
                if s.route == Route.SYSTEMS
            ),
            "both_count": sum(
                1 for s in manifest.segments
                if s.route == Route.BOTH
            ),
        })

        logger.info(
            "Classified %d segments: %d lore, %d systems, %d both",
            len(manifest.segments),
            sum(1 for s in manifest.segments if s.route == Route.LORE),
            sum(1 for s in manifest.segments if s.route == Route.SYSTEMS),
            sum(1 for s in manifest.segments if s.route == Route.BOTH),
        )
        return manifest

    def _rule_classify(self, segment: SegmentEntry) -> None:
        """Apply rule-based classification to a segment."""
        text = segment.content.lower()
        intent = segment.chapter_intent

        # Detect mechanical content density
        mechanical_matches = self._mechanical_re.findall(text)
        mechanical_density = len(mechanical_matches) / max(segment.word_count, 1) * 100

        # Score content types
        type_scores: dict[ContentType, float] = {}
        for ctype, patterns in TYPE_INDICATORS.items():
            score = 0.0
            for pattern in patterns:
                matches = len(re.findall(pattern, text))
                score += matches
            if score > 0:
                type_scores[ctype] = score

        # Apply type hints from chapter intent (2.0 virtual keyword matches)
        if intent and intent in INTENT_TYPE_HINTS:
            for hinted_type in INTENT_TYPE_HINTS[intent]:
                type_scores[hinted_type] = type_scores.get(hinted_type, 0.0) + 2.0

        # Determine content type
        if type_scores:
            best_type = max(type_scores, key=type_scores.get)
            segment.content_type = best_type
            segment.classification_confidence = min(
                type_scores[best_type] / 5.0, 0.95
            )
        else:
            segment.content_type = ContentType.GENERAL
            segment.classification_confidence = 0.3

        # Apply intent route bias to mechanical density
        adjusted_density = mechanical_density
        if intent:
            adjusted_density += INTENT_ROUTE_BIAS.get(intent, 0.0)

        # Determine route using adjusted density
        if adjusted_density > 2.0:
            if segment.content_type in (ContentType.RULES, ContentType.TABLE):
                segment.route = Route.SYSTEMS
            else:
                segment.route = Route.BOTH
            segment.classification_confidence = max(
                segment.classification_confidence, 0.6
            )
        elif adjusted_density > 0.5:
            segment.route = Route.BOTH
        else:
            segment.route = Route.LORE

        # Hard override: MECHANICS intent should not route to pure LORE
        if intent == ChapterIntent.MECHANICS and segment.route == Route.LORE:
            segment.route = Route.BOTH

    def _llm_verify_batch(self, segments: list[SegmentEntry]) -> None:
        """Use LLM to verify/correct classifications for ambiguous segments."""
        from ..llm.gateway import load_schema

        prompt_tmpl = self.registry.get_prompt("classify")
        schema = load_schema(prompt_tmpl.schema_name)

        # Process in batches of 10
        batch_size = 10
        total_batches = (len(segments) + batch_size - 1) // batch_size
        for i in range(0, len(segments), batch_size):
            batch_num = i // batch_size + 1
            self._progress(f"LLM verify batch {batch_num}/{total_batches}")
            batch = segments[i:i + batch_size]
            batch_data = []
            for seg in batch:
                # Truncate content for classification
                preview = seg.content[:500]
                batch_data.append({
                    "id": seg.id,
                    "title": seg.title,
                    "preview": preview,
                    "current_type": seg.content_type.value if seg.content_type else "general",
                    "current_route": seg.route.value if seg.route else "lore",
                })

            response = self.gateway.run_structured(
                prompt=prompt_tmpl.template,
                input_data={
                    "segments": batch_data,
                },
                schema=schema,
                options={"temperature": 0.2, "max_tokens": 2048},
            )

            # Apply LLM classifications
            classifications = response.content.get("classifications", [])
            seg_map = {s.id: s for s in batch}
            for cls in classifications:
                seg = seg_map.get(cls.get("id"))
                if not seg:
                    continue
                try:
                    seg.content_type = ContentType(cls["content_type"])
                except (ValueError, KeyError):
                    pass
                try:
                    seg.route = Route(cls["route"])
                except (ValueError, KeyError):
                    pass
                seg.classification_confidence = cls.get("confidence", 0.8)

    def _write_manifest(
        self,
        manifest: SegmentManifest,
        output_dir: Path
    ) -> None:
        """Write updated segment manifest with classifications."""
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
                    "classification_confidence": s.classification_confidence,
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
