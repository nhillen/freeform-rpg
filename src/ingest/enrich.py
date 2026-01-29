"""Stage 5: Lore Enrichment Pipeline.

Processes lore-routed segments through:
  5a. Global entity extraction → EntityRegistry
  5b. Per-file enrichment → markdown with YAML frontmatter
  5c. Section size validation
  5d. Batch tag generation
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .models import (
    ChapterIntent, ContentType, EntityEntry, EntityRegistry, Route,
    SegmentEntry, SegmentManifest,
)
from .utils import (
    count_words, ensure_dir, slugify, write_markdown,
    write_stage_meta,
)

logger = logging.getLogger(__name__)

# Intents that suggest entity extraction even when content_type is ambiguous
ENTITY_EXTRACTION_INTENTS = {
    ChapterIntent.FACTIONS,
    ChapterIntent.CHARACTERS,
    ChapterIntent.SETTING,
    ChapterIntent.BESTIARY,
    ChapterIntent.EQUIPMENT,
}

# Map ChapterIntent to entity type for ambiguous content types
INTENT_TO_ENTITY_TYPE: dict[ChapterIntent, str] = {
    ChapterIntent.FACTIONS: "faction",
    ChapterIntent.CHARACTERS: "npc",
    ChapterIntent.SETTING: "location",
    ChapterIntent.BESTIARY: "npc",
    ChapterIntent.EQUIPMENT: "item",
}

# Map ContentType to pack directory type
CONTENT_TYPE_TO_FILE_TYPE = {
    ContentType.LOCATION: "location",
    ContentType.NPC: "npc",
    ContentType.FACTION: "faction",
    ContentType.CULTURE: "culture",
    ContentType.ITEM: "item",
    ContentType.EVENT: "general",
    ContentType.HISTORY: "culture",
    ContentType.GENERAL: "general",
}


def _entity_type_from_intent(
    intent: Optional[ChapterIntent],
    content_type: Optional[ContentType],
) -> str:
    """Derive entity type from chapter intent when content_type is ambiguous."""
    if intent and intent in INTENT_TO_ENTITY_TYPE:
        return INTENT_TO_ENTITY_TYPE[intent]
    if content_type:
        return CONTENT_TYPE_TO_FILE_TYPE.get(content_type, "general")
    return "general"


class LoreEnricher:
    """Enriches lore segments with entity extraction, frontmatter, and tags."""

    def __init__(
        self,
        llm_gateway=None,
        prompt_registry=None,
        tag_gateway=None,
        progress_fn=None,
    ):
        """
        Args:
            llm_gateway: LLM gateway for entity extraction and enrichment (Sonnet-class).
            prompt_registry: Prompt registry for loading templates.
            tag_gateway: Optional separate gateway for tag generation (Haiku-class).
            progress_fn: Optional callback for progress updates.
        """
        self.gateway = llm_gateway
        self.registry = prompt_registry
        self.tag_gateway = tag_gateway or llm_gateway
        self._progress = progress_fn or (lambda msg: None)

    def enrich(
        self,
        manifest: SegmentManifest,
        output_dir: str | Path,
    ) -> tuple[list[dict], EntityRegistry]:
        """Run the full lore enrichment pipeline.

        Args:
            manifest: Classified segment manifest.
            output_dir: Directory to write enriched files.

        Returns:
            Tuple of (enriched_files, entity_registry).
            enriched_files is a list of dicts with keys:
                path, title, file_type, entity_id, frontmatter
        """
        output_dir = Path(output_dir)

        # Filter to lore-routed segments
        lore_segments = [
            s for s in manifest.segments
            if s.route in (Route.LORE, Route.BOTH)
        ]

        if not lore_segments:
            logger.warning("No lore segments to enrich")
            return [], EntityRegistry()

        # Stage 5a: Global entity extraction
        self._progress(f"Extracting entities from {len(lore_segments)} lore segments")
        registry = self._extract_entities(lore_segments)
        self._progress(f"Found {len(registry.entities)} entities")

        # Stage 5b: Per-segment enrichment
        self._progress(f"Enriching {len(lore_segments)} segments")
        enriched_files = self._enrich_segments(lore_segments, registry, output_dir)

        # Stage 5c: Size validation
        self._progress("Validating enriched file sizes")
        self._validate_sizes(enriched_files)

        # Stage 5d: Batch tag generation
        self._progress(f"Generating tags for {len(enriched_files)} files")
        self._generate_tags(enriched_files)

        # Write entity registry
        self._write_registry(registry, output_dir)

        write_stage_meta(output_dir, {
            "stage": "enrich",
            "status": "complete",
            "segments_enriched": len(enriched_files),
            "entities_found": len(registry.entities),
        })

        logger.info(
            "Enriched %d segments, found %d entities",
            len(enriched_files), len(registry.entities)
        )
        return enriched_files, registry

    def _extract_entities(
        self,
        segments: list[SegmentEntry]
    ) -> EntityRegistry:
        """Stage 5a: Extract all entities from lore segments."""
        registry = EntityRegistry()

        if not self.gateway or not self.registry:
            # Fallback: create entities from segment titles
            for seg in segments:
                has_entity_type = seg.content_type in (
                    ContentType.NPC, ContentType.LOCATION,
                    ContentType.FACTION, ContentType.ITEM,
                )
                has_entity_intent = (
                    seg.chapter_intent is not None
                    and seg.chapter_intent in ENTITY_EXTRACTION_INTENTS
                )
                if has_entity_type or has_entity_intent:
                    entity_id = slugify(seg.title)
                    # Determine entity type: prefer content_type, fall back to intent
                    if has_entity_type:
                        entity_type = CONTENT_TYPE_TO_FILE_TYPE.get(
                            seg.content_type, "general"
                        )
                    else:
                        entity_type = _entity_type_from_intent(
                            seg.chapter_intent, seg.content_type
                        )
                    registry.add(EntityEntry(
                        id=entity_id,
                        name=seg.title,
                        entity_type=entity_type,
                        source_segments=[seg.id],
                    ))
            return registry

        from ..llm.gateway import load_schema

        prompt_tmpl = self.registry.get_prompt("enrich_entities")
        schema = load_schema(prompt_tmpl.schema_name)

        # Build text summary for entity extraction
        segment_summaries = []
        for seg in segments:
            preview = seg.content[:800]
            summary = {
                "id": seg.id,
                "title": seg.title,
                "type": seg.content_type.value if seg.content_type else "general",
                "preview": preview,
            }
            if seg.chapter_intent:
                summary["chapter_intent"] = seg.chapter_intent.value
            segment_summaries.append(summary)

        # Process in batches to stay within context limits
        all_entities_data = []
        batch_size = 15
        total_batches = (len(segment_summaries) + batch_size - 1) // batch_size
        for i in range(0, len(segment_summaries), batch_size):
            batch_num = i // batch_size + 1
            self._progress(f"Entity extraction batch {batch_num}/{total_batches}")
            batch = segment_summaries[i:i + batch_size]
            response = self.gateway.run_structured(
                prompt=prompt_tmpl.template,
                input_data={"segments": batch},
                schema=schema,
                options={"temperature": 0.3, "max_tokens": 4096},
            )
            all_entities_data.extend(
                response.content.get("entities", [])
            )

        # Build registry, deduplicating by ID
        seen_ids: set[str] = set()
        for ent_data in all_entities_data:
            entity_id = slugify(ent_data.get("name", "unknown"))
            if entity_id in seen_ids:
                continue
            seen_ids.add(entity_id)

            registry.add(EntityEntry(
                id=entity_id,
                name=ent_data.get("name", "Unknown"),
                entity_type=ent_data.get("entity_type", "general"),
                description=ent_data.get("description", ""),
                aliases=ent_data.get("aliases", []),
                related_entities=ent_data.get("related_entities", []),
                source_segments=ent_data.get("source_segments", []),
            ))

        return registry

    def _enrich_segments(
        self,
        segments: list[SegmentEntry],
        registry: EntityRegistry,
        output_dir: Path,
    ) -> list[dict]:
        """Stage 5b: Enrich each segment with frontmatter."""
        enriched_dir = ensure_dir(output_dir / "enriched")
        enriched_files = []
        total = len(segments)

        for seg_idx, seg in enumerate(segments):
            self._progress(
                f"Enriching {seg_idx + 1}/{total}: {seg.title[:35]}"
            )
            file_type = CONTENT_TYPE_TO_FILE_TYPE.get(
                seg.content_type, "general"
            )
            entity_id = slugify(seg.title)

            # Find related entities
            entity_refs = []
            entity = registry.get(entity_id)
            if entity:
                entity_refs = entity.related_entities.copy()
                if entity_id not in entity_refs:
                    entity_refs.insert(0, entity_id)

            # Build frontmatter
            frontmatter = {
                "title": seg.title,
                "type": file_type,
                "entity_id": entity_id,
                "tags": seg.tags.copy(),
                "entity_refs": entity_refs,
            }

            # LLM enrichment if available
            if self.gateway and self.registry:
                enriched = self._llm_enrich_segment(seg, registry, frontmatter)
                if enriched:
                    frontmatter = enriched["frontmatter"]

            # Write enriched markdown
            type_dir = ensure_dir(enriched_dir / f"{file_type}s")
            filename = f"{slugify(seg.title)}.md"
            filepath = type_dir / filename

            write_markdown(filepath, seg.content, frontmatter)

            enriched_files.append({
                "path": str(filepath),
                "title": seg.title,
                "file_type": file_type,
                "entity_id": entity_id,
                "frontmatter": frontmatter,
                "word_count": seg.word_count,
            })

        return enriched_files

    def _llm_enrich_segment(
        self,
        segment: SegmentEntry,
        registry: EntityRegistry,
        base_frontmatter: dict,
    ) -> Optional[dict]:
        """Use LLM to generate enriched frontmatter for a segment."""
        from ..llm.gateway import load_schema

        try:
            prompt_tmpl = self.registry.get_prompt("enrich_segment")
            schema = load_schema(prompt_tmpl.schema_name)
        except FileNotFoundError:
            return None

        # Build entity context
        entity_context = []
        for ent in registry.entities[:20]:
            entity_context.append({
                "id": ent.id,
                "name": ent.name,
                "type": ent.entity_type,
            })

        input_data = {
            "title": segment.title,
            "content": segment.content[:2000],
            "content_type": segment.content_type.value if segment.content_type else "general",
            "known_entities": entity_context,
            "current_frontmatter": base_frontmatter,
        }
        if segment.chapter_intent:
            input_data["chapter_intent"] = segment.chapter_intent.value

        response = self.gateway.run_structured(
            prompt=prompt_tmpl.template,
            input_data=input_data,
            schema=schema,
            options={"temperature": 0.3, "max_tokens": 2048},
        )

        return {
            "frontmatter": response.content.get("frontmatter", base_frontmatter),
        }

    def _validate_sizes(self, enriched_files: list[dict]) -> None:
        """Stage 5c: Validate enriched file sizes."""
        for ef in enriched_files:
            wc = ef.get("word_count", 0)
            if wc < 50:
                logger.warning(
                    "Enriched file '%s' is very small (%d words)",
                    ef["title"], wc
                )
            elif wc > 3000:
                logger.warning(
                    "Enriched file '%s' is very large (%d words)",
                    ef["title"], wc
                )

    def _generate_tags(self, enriched_files: list[dict]) -> None:
        """Stage 5d: Generate tags for enriched files."""
        if not self.tag_gateway or not self.registry:
            return

        from ..llm.gateway import load_schema

        try:
            prompt_tmpl = self.registry.get_prompt("enrich_tags")
            schema = load_schema(prompt_tmpl.schema_name)
        except FileNotFoundError:
            return

        # Process in batches
        batch_size = 20
        total_batches = (len(enriched_files) + batch_size - 1) // batch_size
        for i in range(0, len(enriched_files), batch_size):
            batch_num = i // batch_size + 1
            self._progress(f"Tag generation batch {batch_num}/{total_batches}")
            batch = enriched_files[i:i + batch_size]
            batch_data = [
                {
                    "title": ef["title"],
                    "type": ef["file_type"],
                    "current_tags": ef["frontmatter"].get("tags", []),
                }
                for ef in batch
            ]

            try:
                response = self.tag_gateway.run_structured(
                    prompt=prompt_tmpl.template,
                    input_data={"files": batch_data},
                    schema=schema,
                    options={"temperature": 0.3, "max_tokens": 2048},
                )

                tag_results = response.content.get("tags", [])
                for j, tags_data in enumerate(tag_results):
                    if j < len(batch):
                        new_tags = tags_data.get("tags", [])
                        batch[j]["frontmatter"]["tags"] = list(set(
                            batch[j]["frontmatter"].get("tags", []) + new_tags
                        ))
            except Exception as e:
                logger.warning("Tag generation failed: %s", e)

    def _write_registry(self, registry: EntityRegistry, output_dir: Path) -> None:
        """Write entity registry to JSON."""
        data = {
            "entities": [
                {
                    "id": e.id,
                    "name": e.name,
                    "entity_type": e.entity_type,
                    "description": e.description,
                    "aliases": e.aliases,
                    "related_entities": e.related_entities,
                    "source_segments": e.source_segments,
                }
                for e in registry.entities
            ]
        }
        (output_dir / "entity_registry.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False)
        )
