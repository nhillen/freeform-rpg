"""Stage 6: Content Pack Assembly.

Assembles enriched lore files into a content pack directory structure
compatible with the existing PackLoader/Chunker/Indexer pipeline.
Optionally promotes entities from the registry into standalone pack files.

Supports draft mode for human review before final pack assembly:
- Outputs to draft/{pack_id}/ instead of content_packs/
- Generates REVIEW_NEEDED.md listing low-confidence extractions
- Generates EXTRACTION_REPORT.md with extraction details
- Can be promoted to content_packs/ via `freeform-rpg promote-draft`
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
PACK_TYPE_DIRS = ["locations", "npcs", "factions", "culture", "items", "storytelling"]


class PackAssembler:
    """Assembles enriched files into a content pack directory."""

    def assemble(
        self,
        enriched_files: list[dict],
        config: IngestConfig,
        output_dir: str | Path,
        entity_registry: Optional[EntityRegistry] = None,
        guidance_dir: Optional[Path] = None,
    ) -> Path:
        """Assemble a content pack from enriched files.

        Args:
            enriched_files: List of enriched file dicts from LoreEnricher.
            config: Pipeline configuration with pack metadata.
            output_dir: Directory to create the pack in.
            entity_registry: Optional entity registry for entity-to-file promotion.
            guidance_dir: Optional path to GM guidance extraction output.

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

        # Copy GM guidance files to storytelling directory
        guidance_count = 0
        if guidance_dir:
            guidance_count = self._copy_guidance_files(guidance_dir, pack_dir)
            file_count += guidance_count

        # In draft mode, write review markers
        if config.draft_mode:
            self._write_draft_markers(pack_dir, config, enriched_files)

        write_stage_meta(output_dir, {
            "stage": "assemble",
            "status": "complete",
            "pack_dir": str(pack_dir),
            "files_assembled": file_count,
            "promoted_entities": promoted_count,
            "draft_mode": config.draft_mode,
        })

        mode_label = "draft" if config.draft_mode else "content pack"
        logger.info(
            "Assembled %s '%s' with %d files (%d promoted) at %s",
            mode_label, config.pack_name, file_count, promoted_count, pack_dir
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

    def _copy_guidance_files(
        self,
        guidance_dir: Path,
        pack_dir: Path,
    ) -> int:
        """Copy GM guidance files from extraction output to pack storytelling directory.

        Returns:
            Number of files copied.
        """
        src_storytelling = guidance_dir / "storytelling"
        if not src_storytelling.exists():
            return 0

        dst_storytelling = ensure_dir(pack_dir / "storytelling")
        copied = 0

        for src_file in src_storytelling.glob("*.md"):
            dst_file = dst_storytelling / src_file.name
            shutil.copy2(src_file, dst_file)
            copied += 1
            logger.debug("Copied guidance file: %s", src_file.name)

        # Also copy the review file to pack root if it exists
        review_file = guidance_dir / "gm_guidance_review.md"
        if review_file.exists():
            shutil.copy2(review_file, pack_dir / "gm_guidance_review.md")

        if copied:
            logger.info("Copied %d GM guidance files to storytelling/", copied)

        return copied

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

    def _write_draft_markers(
        self,
        pack_dir: Path,
        config: IngestConfig,
        enriched_files: list[dict],
    ) -> None:
        """Write draft mode review markers.

        Creates:
        - REVIEW_NEEDED.md: Items requiring manual review
        - DRAFT_README.md: Instructions for review and promotion
        """
        lines = [
            "# Draft Pack: Review Needed",
            "",
            f"This is a **draft** content pack that requires manual review before use.",
            "",
            "## How to Review",
            "",
            "1. Check each content file for accuracy",
            "2. Verify entity relationships in frontmatter",
            "3. Check systems/ directory for mechanical extraction accuracy",
            "4. Review storytelling/ for GM guidance content",
            "",
            "## How to Promote",
            "",
            "Once reviewed, promote to a final content pack:",
            "",
            "```bash",
            f"freeform-rpg promote-draft {pack_dir}",
            "```",
            "",
            "## Contents Summary",
            "",
        ]

        # Count files by type
        type_counts: dict[str, int] = {}
        for type_dir in PACK_TYPE_DIRS:
            dir_path = pack_dir / type_dir
            if dir_path.exists():
                count = len(list(dir_path.glob("*.md")))
                if count > 0:
                    type_counts[type_dir] = count

        for type_name, count in sorted(type_counts.items()):
            lines.append(f"- **{type_name}/**: {count} files")

        lines.append("")

        # List files with low confidence (if available in frontmatter)
        low_conf_files = []
        for ef in enriched_files:
            conf = ef.get("frontmatter", {}).get("classification_confidence", 1.0)
            if conf < 0.5:
                low_conf_files.append({
                    "title": ef.get("title", "Unknown"),
                    "type": ef.get("file_type", "general"),
                    "confidence": conf,
                })

        if low_conf_files:
            lines.append("## Low Confidence Items")
            lines.append("")
            lines.append("These items had low classification confidence and should be reviewed:")
            lines.append("")
            for item in low_conf_files:
                lines.append(f"- **{item['title']}** ({item['type']}): {item['confidence']:.0%} confidence")
            lines.append("")

        # Write the review needed file
        review_path = pack_dir / "REVIEW_NEEDED.md"
        review_path.write_text("\n".join(lines))

        # Write draft readme
        readme_lines = [
            f"# {config.pack_name or 'Untitled Pack'} (DRAFT)",
            "",
            "**Status:** Draft - Requires Review",
            "",
            "This pack was generated by the PDF ingest pipeline and requires",
            "manual review before use in gameplay.",
            "",
            "See `REVIEW_NEEDED.md` for review instructions.",
            "",
            "---",
            "",
            f"*Generated from: {config.pdf_path}*",
        ]
        readme_path = pack_dir / "DRAFT_README.md"
        readme_path.write_text("\n".join(readme_lines))

        logger.info("Wrote draft review markers to %s", pack_dir)
