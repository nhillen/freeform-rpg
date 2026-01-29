"""Full PDF-to-Content Pack Pipeline Orchestrator.

Orchestrates all ingest stages, manages work directories, and supports
stage-level resumption via stage_meta.json checkpoints.

Use ``from_stage`` to re-run from a specific stage onwards — earlier
stages are loaded from their on-disk outputs, and the target stage
(plus everything downstream) is cleared and re-executed.
"""

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Optional

from .models import (
    ChapterIntent, ContentType, DocumentStructure, EntityEntry,
    EntityRegistry, ExtractionResult, IngestConfig, PageEntry,
    Route, SectionNode, SegmentEntry, SegmentManifest,
    SystemsExtractionManifest,
)
from .utils import ensure_dir, read_stage_meta

logger = logging.getLogger(__name__)

# Canonical stage ordering and directory names
STAGE_ORDER = [
    "extract", "structure", "segment", "classify",
    "enrich", "assemble", "validate", "systems",
]

STAGE_DIRS = {
    "extract": "01_extract",
    "structure": "02_structure",
    "segment": "03_segment",
    "classify": "04_classify",
    "enrich": "05_lore",
    "assemble": "06_assemble",
    "validate": "07_validate",
    "systems": "08_systems",
}


class IngestPipeline:
    """Orchestrates the full PDF-to-content-pack pipeline."""

    def __init__(
        self,
        config: IngestConfig,
        sonnet_gateway=None,
        haiku_gateway=None,
        prompt_registry=None,
    ):
        """
        Args:
            config: Pipeline configuration.
            sonnet_gateway: LLM gateway for quality-critical stages (enrichment, entities).
            haiku_gateway: LLM gateway for cheap stages (classify, structure, tags).
            prompt_registry: Prompt registry for loading templates.
        """
        self.config = config
        self.sonnet = sonnet_gateway
        self.haiku = haiku_gateway or sonnet_gateway
        self.registry = prompt_registry
        self._timings: dict[str, float] = {}
        self._progress_fn = None  # Set by InstrumentedPipeline for spinner updates

    def run(
        self,
        resume: bool = True,
        from_stage: Optional[str] = None,
    ) -> dict:
        """Run the full pipeline.

        Args:
            resume: If True, skip stages that have completed stage_meta.json.
            from_stage: If set, clear this stage and all downstream stages
                before running, then resume earlier stages from disk.
                Implies resume=True. Valid values: extract, structure,
                segment, classify, enrich, assemble, validate, systems.

        Returns:
            Dict with pipeline results:
                pack_dir, validation_report, systems_report, timings
        """
        work_dir = self.config.get_work_dir()
        ensure_dir(work_dir)

        # --from-stage implies resume for upstream stages
        if from_stage:
            self._clear_from_stage(from_stage, work_dir)
            resume = True

        logger.info("Starting ingest pipeline: %s", self.config.pdf_path)
        logger.info("Work directory: %s", work_dir)

        # Stage 1: Extract
        extract_dir = work_dir / "01_extract"
        extraction = self._run_stage(
            "extract", extract_dir, resume,
            self._stage_extract, extract_dir,
            loader=self._load_extraction,
        )

        # Stage 2: Structure
        structure_dir = work_dir / "02_structure"
        structure = self._run_stage(
            "structure", structure_dir, resume,
            self._stage_structure, extraction, structure_dir,
            loader=self._load_structure,
        )

        # Stage 3: Segment
        segment_dir = work_dir / "03_segment"
        manifest = self._run_stage(
            "segment", segment_dir, resume,
            self._stage_segment, structure, segment_dir,
            loader=self._load_segment_manifest,
        )

        # Stage 4: Classify
        classify_dir = work_dir / "04_classify"
        manifest = self._run_stage(
            "classify", classify_dir, resume,
            self._stage_classify, manifest, classify_dir,
            loader=self._load_segment_manifest,
        )

        # Stage 5: Lore Enrichment + Assembly
        lore_dir = work_dir / "05_lore"
        enriched_files, entity_registry = self._run_stage(
            "enrich", lore_dir, resume,
            self._stage_enrich, manifest, lore_dir,
            loader=self._load_enriched,
        )

        # Stage 6: Assemble Pack
        assemble_dir = work_dir / "06_assemble"
        pack_dir = self._run_stage(
            "assemble", assemble_dir, resume,
            self._stage_assemble, enriched_files, assemble_dir, entity_registry,
            loader=self._load_pack_dir,
        )

        # Stage 7: Validate Pack
        validate_dir = work_dir / "07_validate"
        validation_report = self._run_stage(
            "validate", validate_dir, resume,
            self._stage_validate, pack_dir, validate_dir,
            loader=self._load_validation,
        )

        # Systems path (optional)
        systems_report = None
        if not self.config.skip_systems:
            systems_dir = work_dir / "08_systems"
            systems_report = self._run_stage(
                "systems", systems_dir, resume,
                self._stage_systems, manifest, entity_registry, systems_dir,
                loader=self._load_systems_validation,
            )

        # Write pipeline summary
        summary = {
            "pdf_path": self.config.pdf_path,
            "pack_dir": str(pack_dir),
            "pack_valid": validation_report.valid if validation_report else False,
            "validation_errors": validation_report.errors if validation_report else [],
            "systems_valid": (
                systems_report.valid if systems_report else None
            ),
            "timings": self._timings,
        }
        (work_dir / "pipeline_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False)
        )

        logger.info("Pipeline complete. Pack at: %s", pack_dir)
        return summary

    def _clear_from_stage(self, from_stage: str, work_dir: Path) -> None:
        """Clear the target stage and all downstream stage directories."""
        if from_stage not in STAGE_ORDER:
            raise ValueError(
                f"Unknown stage: {from_stage}. "
                f"Valid stages: {', '.join(STAGE_ORDER)}"
            )

        idx = STAGE_ORDER.index(from_stage)
        for stage_name in STAGE_ORDER[idx:]:
            stage_dir = work_dir / STAGE_DIRS[stage_name]
            if stage_dir.exists():
                shutil.rmtree(stage_dir)
                logger.info("Cleared stage: %s (%s)", stage_name, stage_dir)

    def _run_stage(self, name, stage_dir, resume, fn, *args, loader=None):
        """Run a pipeline stage with resumption support.

        If ``resume`` is True and the stage has a completed checkpoint,
        the ``loader`` callable is used to reconstruct the stage result
        from its on-disk outputs instead of re-running.
        """
        stage_dir = Path(stage_dir)

        # Resume: load from disk if stage already completed
        if resume and loader:
            meta = read_stage_meta(stage_dir)
            if meta and meta.get("status") == "complete":
                logger.info("Resuming — loading completed stage: %s", name)
                start = time.time()
                result = loader(stage_dir)
                elapsed = time.time() - start
                self._timings[name] = round(elapsed * 1000)
                logger.info(
                    "Stage '%s' loaded from disk in %.1fs", name, elapsed
                )
                return result

        ensure_dir(stage_dir)
        start = time.time()
        try:
            result = fn(*args)
            elapsed = time.time() - start
            self._timings[name] = round(elapsed * 1000)
            logger.info("Stage '%s' completed in %.1fs", name, elapsed)
            return result
        except Exception as e:
            elapsed = time.time() - start
            self._timings[name] = round(elapsed * 1000)
            logger.error("Stage '%s' failed after %.1fs: %s", name, elapsed, e)
            raise

    # ------------------------------------------------------------------
    # Stage loaders (reconstruct results from on-disk outputs)
    # ------------------------------------------------------------------

    def _load_extraction(self, stage_dir: Path) -> ExtractionResult:
        """Load ExtractionResult from stage 1 output."""
        from .utils import read_manifest

        page_map = read_manifest(stage_dir / "page_map.json")
        meta = read_stage_meta(stage_dir) or {}

        pages = []
        pages_dir = stage_dir / "pages"
        if pages_dir.exists():
            for page_file in sorted(pages_dir.glob("page_*.md")):
                page_num = int(page_file.stem.split("_")[1])
                text = page_file.read_text(encoding="utf-8")
                info = page_map.get(str(page_num), {})
                pages.append(PageEntry(
                    page_num=page_num,
                    text=text,
                    char_count=info.get("char_count", len(text)),
                    has_images=info.get("has_images", False),
                    ocr_used=info.get("ocr_used", False),
                ))

        return ExtractionResult(
            pdf_path=meta.get("pdf_path", self.config.pdf_path),
            total_pages=meta.get("total_pages", len(pages)),
            pages=pages,
            output_dir=str(stage_dir),
        )

    def _load_structure(self, stage_dir: Path) -> DocumentStructure:
        """Load DocumentStructure from stage 2 output."""
        from .utils import read_manifest

        data = read_manifest(stage_dir / "structure.json")

        def parse_node(d, default_level=1):
            intent = None
            if d.get("intent"):
                try:
                    intent = ChapterIntent(d["intent"])
                except ValueError:
                    pass
            children = [parse_node(c, 2) for c in d.get("children", [])]
            return SectionNode(
                title=d.get("title", "Untitled"),
                level=d.get("level", default_level),
                page_start=d.get("page_start", 1),
                page_end=d.get("page_end", 1),
                children=children,
                content=d.get("content", ""),
                intent=intent,
            )

        sections = [parse_node(s) for s in data.get("sections", [])]

        # Load chapter content from files
        chapters_dir = stage_dir / "chapters"
        if chapters_dir.exists():
            for i, section in enumerate(sections):
                for chapter_file in chapters_dir.glob(f"{i + 1:02d}_*.md"):
                    section.content = chapter_file.read_text(encoding="utf-8")
                    break

        return DocumentStructure(
            title=data.get("title", "Untitled"),
            sections=sections,
            metadata=data.get("metadata", {}),
        )

    def _load_segment_manifest(self, stage_dir: Path) -> SegmentManifest:
        """Load SegmentManifest from stage 3 or 4 output."""
        from .utils import read_manifest

        data = read_manifest(stage_dir / "segment_manifest.json")

        segments = []
        segments_dir = stage_dir / "segments"
        for s in data.get("segments", []):
            # Load content from segment file
            content = ""
            if segments_dir.exists():
                for seg_file in segments_dir.glob(f"{s['id']}_*.md"):
                    raw = seg_file.read_text(encoding="utf-8")
                    lines = raw.split("\n")
                    if lines and lines[0].startswith("# "):
                        content = "\n".join(lines[1:]).strip()
                    else:
                        content = raw.strip()
                    break

            content_type = None
            if s.get("content_type"):
                try:
                    content_type = ContentType(s["content_type"])
                except ValueError:
                    pass

            route = None
            if s.get("route"):
                try:
                    route = Route(s["route"])
                except ValueError:
                    pass

            chapter_intent = None
            if s.get("chapter_intent"):
                try:
                    chapter_intent = ChapterIntent(s["chapter_intent"])
                except ValueError:
                    pass

            segments.append(SegmentEntry(
                id=s["id"],
                title=s.get("title", ""),
                content=content,
                source_section=s.get("source_section", ""),
                page_start=s.get("page_start", 0),
                page_end=s.get("page_end", 0),
                word_count=s.get("word_count", 0),
                content_type=content_type,
                route=route,
                classification_confidence=s.get("classification_confidence", 0.0),
                tags=s.get("tags", []),
                chapter_intent=chapter_intent,
            ))

        return SegmentManifest(
            segments=segments,
            total_words=data.get("total_words", 0),
            metadata=data.get("metadata", {}),
        )

    def _load_enriched(self, stage_dir: Path) -> tuple[list[dict], EntityRegistry]:
        """Load enriched files list and entity registry from stage 5 output."""
        from .utils import read_manifest, read_markdown_with_frontmatter

        # Load enriched files
        enriched_dir = stage_dir / "enriched"
        files = []
        if enriched_dir.exists():
            for type_dir in sorted(enriched_dir.iterdir()):
                if type_dir.is_dir():
                    for md_file in sorted(type_dir.glob("*.md")):
                        fm, body = read_markdown_with_frontmatter(md_file)
                        files.append({
                            "path": str(md_file),
                            "title": fm.get("title", md_file.stem),
                            "file_type": fm.get("type", "general"),
                            "entity_id": fm.get("entity_id", md_file.stem),
                            "frontmatter": fm,
                        })

        # Load entity registry
        registry = EntityRegistry()
        registry_path = stage_dir / "entity_registry.json"
        if registry_path.exists():
            reg_data = read_manifest(registry_path)
            for e in reg_data.get("entities", []):
                registry.add(EntityEntry(
                    id=e.get("id", ""),
                    name=e.get("name", ""),
                    entity_type=e.get("entity_type", "general"),
                    description=e.get("description", ""),
                    aliases=e.get("aliases", []),
                    related_entities=e.get("related_entities", []),
                    source_segments=e.get("source_segments", []),
                ))

        return files, registry

    def _load_pack_dir(self, stage_dir: Path) -> Path:
        """Load pack directory path from stage 6 output."""
        # The pack is assembled inside the stage dir under the pack_id subdir
        for child in stage_dir.iterdir():
            if child.is_dir():
                return child
        return stage_dir

    def _load_validation(self, stage_dir: Path):
        """Load ValidationReport from stage 7 output."""
        from .validate import ValidationReport

        meta = read_stage_meta(stage_dir) or {}
        report = ValidationReport(
            valid=meta.get("valid", True),
            errors=meta.get("errors", []),
            warnings=meta.get("warnings", []),
            stats=meta.get("stats", {}),
        )
        return report

    def _load_systems_validation(self, stage_dir: Path):
        """Load SystemsValidationReport from stage 8 output."""
        from .systems_validate import SystemsValidationReport

        meta = read_stage_meta(stage_dir) or {}
        report = SystemsValidationReport(
            valid=meta.get("valid", True),
            errors=meta.get("errors", []),
            warnings=meta.get("warnings", []),
            stats=meta.get("stats", {}),
        )
        return report

    # ------------------------------------------------------------------
    # Individual stage implementations
    # ------------------------------------------------------------------

    def _stage_extract(self, output_dir: Path) -> ExtractionResult:
        """Stage 1: PDF extraction."""
        from .extract import PDFExtractor

        extractor = PDFExtractor()
        return extractor.extract(
            pdf_path=self.config.pdf_path,
            output_dir=output_dir,
            use_ocr=self.config.use_ocr,
            extract_images=self.config.extract_images,
        )

    def _stage_structure(
        self,
        extraction: ExtractionResult,
        output_dir: Path,
    ) -> DocumentStructure:
        """Stage 2: Structure detection."""
        from .structure import StructureDetector

        detector = StructureDetector(
            llm_gateway=self.haiku,
            prompt_registry=self.registry,
            progress_fn=self._progress_fn,
        )
        return detector.detect(
            extraction=extraction,
            output_dir=output_dir,
            pdf_path=self.config.pdf_path,
        )

    def _stage_segment(
        self,
        structure: DocumentStructure,
        output_dir: Path,
    ) -> SegmentManifest:
        """Stage 3: Content segmentation."""
        from .segment import ContentSegmenter

        segmenter = ContentSegmenter(
            llm_gateway=self.haiku,
            prompt_registry=self.registry,
            min_words=self.config.min_segment_words,
            max_words=self.config.max_segment_words,
            target_words=self.config.target_segment_words,
            progress_fn=self._progress_fn,
        )
        return segmenter.segment(structure=structure, output_dir=output_dir)

    def _stage_classify(
        self,
        manifest: SegmentManifest,
        output_dir: Path,
    ) -> SegmentManifest:
        """Stage 4: Classification."""
        from .classify import ContentClassifier

        classifier = ContentClassifier(
            llm_gateway=self.haiku,
            prompt_registry=self.registry,
            progress_fn=self._progress_fn,
        )
        return classifier.classify(manifest=manifest, output_dir=output_dir)

    def _stage_enrich(
        self,
        manifest: SegmentManifest,
        output_dir: Path,
    ) -> tuple[list[dict], EntityRegistry]:
        """Stage 5: Lore enrichment."""
        from .enrich import LoreEnricher

        enricher = LoreEnricher(
            llm_gateway=self.sonnet,
            prompt_registry=self.registry,
            tag_gateway=self.haiku,
            progress_fn=self._progress_fn,
        )
        return enricher.enrich(manifest=manifest, output_dir=output_dir)

    def _stage_assemble(
        self,
        enriched_files: list[dict],
        output_dir: Path,
        entity_registry: Optional[EntityRegistry] = None,
    ) -> Path:
        """Stage 6: Content pack assembly."""
        from .assemble import PackAssembler

        assembler = PackAssembler()
        return assembler.assemble(
            enriched_files=enriched_files,
            config=self.config,
            output_dir=output_dir,
            entity_registry=entity_registry,
        )

    def _stage_validate(self, pack_dir: Path, output_dir: Path):
        """Stage 7: Pack validation."""
        from .validate import PackValidator

        validator = PackValidator()
        return validator.validate(
            pack_dir=pack_dir,
            output_dir=output_dir,
        )

    def _stage_systems(
        self,
        manifest: SegmentManifest,
        entity_registry: EntityRegistry,
        output_dir: Path,
    ):
        """Stages S1-S3: Systems extraction, assembly, validation."""
        from .systems_extract import SystemsExtractor
        from .systems_assemble import SystemsAssembler
        from .systems_validate import SystemsValidator

        # S1: Extract - use raw pages for better mechanical data extraction
        extract_dir = ensure_dir(output_dir / "extract")
        work_dir = self.config.get_work_dir()
        raw_pages_dir = work_dir / "01_extract" / "pages"

        extractor = SystemsExtractor(
            llm_gateway=self.haiku,
            prompt_registry=self.registry,
        )
        extraction = extractor.extract(
            manifest=manifest,
            output_dir=extract_dir,
            raw_pages_dir=raw_pages_dir if raw_pages_dir.exists() else None,
        )

        # S2: Assemble
        assemble_dir = ensure_dir(output_dir / "assemble")
        assembler = SystemsAssembler()
        assembler.assemble(
            extraction=extraction,
            output_dir=assemble_dir,
        )

        # S3: Validate
        validator = SystemsValidator()
        return validator.validate(
            configs_dir=assemble_dir,
            entity_registry=entity_registry,
            output_dir=output_dir,
        )
