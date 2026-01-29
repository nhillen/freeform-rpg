"""Stage 6: Content Pack Assembly.

Assembles enriched lore files into a content pack directory structure
compatible with the existing PackLoader/Chunker/Indexer pipeline.
Optionally promotes entities from the registry into standalone pack files.
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Optional

import yaml

from .models import EntityRegistry, IngestConfig
from .utils import (
    count_words, ensure_dir, read_markdown_with_frontmatter, slugify,
    write_markdown, write_stage_meta,
)

logger = logging.getLogger(__name__)

# Pack directory types
PACK_TYPE_DIRS = ["locations", "npcs", "factions", "culture", "items"]


class PackAssembler:
    """Assembles enriched files into a content pack directory."""

    def assemble(
        self,
        enriched_files: list[dict],
        config: IngestConfig,
        output_dir: str | Path,
        entity_registry: Optional[EntityRegistry] = None,
    ) -> Path:
        """Assemble a content pack from enriched files.

        Args:
            enriched_files: List of enriched file dicts from LoreEnricher.
            config: Pipeline configuration with pack metadata.
            output_dir: Directory to create the pack in.
            entity_registry: Optional entity registry for entity-to-file promotion.

        Returns:
            Path to the assembled content pack directory.
        """
        output_dir = Path(output_dir)
        pack_dir = ensure_dir(output_dir / slugify(config.pack_id or config.pack_name))

        # Create type subdirectories
        for type_dir in PACK_TYPE_DIRS:
            ensure_dir(pack_dir / type_dir)

        # Write pack.yaml manifest
        self._write_manifest(config, pack_dir, len(enriched_files))

        # Copy enriched files to pack structure
        file_count = 0
        for ef in enriched_files:
            src_path = Path(ef["path"])
            if not src_path.exists():
                logger.warning("Source file not found: %s", src_path)
                continue

            file_type = ef.get("file_type", "general")
            target_dir = self._get_type_dir(file_type, pack_dir)

            # Normalize filename
            filename = slugify(ef.get("title", src_path.stem)) + ".md"
            target_path = target_dir / filename

            # Read source and rewrite with cleaned frontmatter
            frontmatter, body = read_markdown_with_frontmatter(src_path)

            # Merge/update frontmatter from enrichment
            ef_fm = ef.get("frontmatter", {})
            if ef_fm:
                frontmatter.update(ef_fm)

            # Ensure required frontmatter fields
            frontmatter.setdefault("title", ef.get("title", "Untitled"))
            frontmatter.setdefault("type", file_type)
            frontmatter.setdefault("entity_id", slugify(ef.get("title", "untitled")))

            write_markdown(target_path, body, frontmatter)
            file_count += 1

        # Promote entities that don't have their own files yet
        promoted_count = 0
        if entity_registry:
            promoted_count = self._promote_entities(
                entity_registry, enriched_files, pack_dir
            )
            file_count += promoted_count

        write_stage_meta(output_dir, {
            "stage": "assemble",
            "status": "complete",
            "pack_dir": str(pack_dir),
            "files_assembled": file_count,
            "promoted_entities": promoted_count,
        })

        logger.info(
            "Assembled content pack '%s' with %d files (%d promoted) at %s",
            config.pack_name, file_count, promoted_count, pack_dir
        )
        return pack_dir

    def _write_manifest(
        self,
        config: IngestConfig,
        pack_dir: Path,
        file_count: int,
    ) -> None:
        """Write pack.yaml manifest."""
        manifest = {
            "id": config.pack_id or slugify(config.pack_name),
            "name": config.pack_name or "Untitled Pack",
            "version": config.pack_version,
            "description": config.pack_description,
            "layer": config.pack_layer,
            "author": config.pack_author,
            "tags": [],
            "source": "pdf_ingest",
            "file_count": file_count,
        }

        manifest_path = pack_dir / "pack.yaml"
        manifest_path.write_text(
            yaml.dump(manifest, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )

    def _get_type_dir(self, file_type: str, pack_dir: Path) -> Path:
        """Map file type to pack subdirectory."""
        type_map = {
            "location": "locations",
            "npc": "npcs",
            "faction": "factions",
            "culture": "culture",
            "item": "items",
        }
        subdir = type_map.get(file_type, "culture")  # default to culture for general
        return ensure_dir(pack_dir / subdir)

    # Entity type → pack subdirectory for promotion
    _PROMOTABLE_TYPES = {
        "npc": "npcs",
        "location": "locations",
        "faction": "factions",
        "item": "items",
    }

    def _promote_entities(
        self,
        registry: EntityRegistry,
        enriched_files: list[dict],
        pack_dir: Path,
    ) -> int:
        """Promote entities from the registry into standalone pack files.

        Entities that appear in entity_refs of enriched files but don't have
        their own primary file get a standalone file aggregating relevant
        excerpts from their source segments.

        Returns:
            Number of promoted entity files created.
        """
        # Build set of entity_ids that already have their own primary file
        existing_primary_ids: set[str] = set()
        for ef in enriched_files:
            eid = ef.get("entity_id", "")
            if eid:
                existing_primary_ids.add(eid)

        # Build reverse index: entity_id → enriched files referencing it
        ref_index: dict[str, list[dict]] = {}
        for ef in enriched_files:
            fm = ef.get("frontmatter", {})
            for ref_id in fm.get("entity_refs", []):
                if ref_id not in ref_index:
                    ref_index[ref_id] = []
                ref_index[ref_id].append(ef)

        promoted = 0
        for entity in registry.entities:
            # Only promote promotable types (npc, location, faction, item)
            subdir = self._PROMOTABLE_TYPES.get(entity.entity_type)
            if not subdir:
                continue

            # Skip if already has a primary file
            if entity.id in existing_primary_ids:
                continue

            # Collect body text from referencing files
            ref_files = ref_index.get(entity.id, [])
            excerpts: list[str] = []
            total_words = 0

            for rf in ref_files:
                src_path = Path(rf["path"])
                if src_path.exists():
                    _, body = read_markdown_with_frontmatter(src_path)
                    if body:
                        excerpts.append(body)
                        total_words += count_words(body)

            # Only promote if we have enough content (>=200 words)
            if total_words < 200:
                continue

            # Build the promoted file
            body_parts = []
            if entity.description:
                body_parts.append(entity.description)

            for excerpt in excerpts:
                body_parts.append(excerpt)

            body = "\n\n".join(body_parts)

            frontmatter = {
                "title": entity.name,
                "type": entity.entity_type,
                "entity_id": entity.id,
                "entity_refs": entity.related_entities,
                "tags": [],
                "promoted": True,
            }
            if entity.aliases:
                frontmatter["aliases"] = entity.aliases

            target_dir = ensure_dir(pack_dir / subdir)
            filename = slugify(entity.name) + ".md"
            target_path = target_dir / filename

            write_markdown(target_path, body, frontmatter)
            promoted += 1
            logger.info(
                "Promoted entity '%s' (%s) → %s (%d words)",
                entity.name, entity.entity_type, target_path.name, count_words(body)
            )

        return promoted
