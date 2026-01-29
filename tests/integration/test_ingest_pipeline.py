"""Integration test: Stages 2-7 using fixture data (no real PDF/LLM).

Tests the full pipeline from pre-extracted page data through to a
validated content pack that installs via the existing PackLoader/Chunker/Indexer.
"""

import pytest
import yaml
from pathlib import Path

from src.ingest.models import (
    ContentType, DocumentStructure, ExtractionResult,
    IngestConfig, PageEntry, Route, SectionNode, SegmentManifest,
)
from src.ingest.structure import StructureDetector
from src.ingest.segment import ContentSegmenter
from src.ingest.classify import ContentClassifier
from src.ingest.enrich import LoreEnricher
from src.ingest.assemble import PackAssembler
from src.ingest.validate import PackValidator


# Fixture: simulated extraction result (as if from a small sourcebook)
FIXTURE_PAGES = [
    PageEntry(
        page_num=1,
        text=(
            "# Undercity Sourcebook\n\n"
            "A guide to the dark depths beneath the neon surface.\n\n"
            "## The Neon District\n\n"
            "The Neon District is the bustling heart of nightlife in the city. "
            "Bars, clubs, and street vendors line the rain-slicked streets. "
            "Holographic signs flicker in every color imaginable, casting "
            "kaleidoscopic reflections on the wet pavement. The district never "
            "sleeps — there's always music, always deals being made, always "
            "someone watching from the shadows. The main strip is called the "
            "Luminous Mile, a stretch of entertainment venues that draws "
            "tourists and locals alike. Behind the glittering facade, "
            "however, darker businesses operate.\n"
        ),
        char_count=500,
    ),
    PageEntry(
        page_num=2,
        text=(
            "## The Neon Dragon Bar\n\n"
            "A seedy establishment on the corner of 5th and Neon. "
            "The building has three floors: the public bar on street level, "
            "a VIP lounge upstairs, and Viktor Kozlov's office on the top floor. "
            "The entrance is marked by a flickering dragon hologram. An alley "
            "behind the club leads to a hidden exit. "
            "The bar is known for cheap synth-beer and expensive information. "
            "Regulars include off-duty security guards, small-time fixers, "
            "and the occasional corporate agent slumming it.\n\n"
            "## The Shadow Market\n\n"
            "Hidden beneath the Neon District, accessed through a service tunnel "
            "near the old metro station. The Shadow Market is where illegal goods "
            "change hands — cyberware, weapons, stolen data, and contraband from "
            "off-world shipments. Stalls are semi-permanent structures made of "
            "shipping containers and scaffolding. The market operates on a trust "
            "system enforced by the Red Dragon syndicate.\n"
        ),
        char_count=700,
    ),
    PageEntry(
        page_num=3,
        text=(
            "# Notable NPCs\n\n"
            "## Viktor Kozlov\n\n"
            "A dangerous enforcer with connections to the Red Dragon syndicate. "
            "Age: 45. Appearance: tall, scarred face, cybernetic left eye. "
            "Personality: cold, calculating, but surprisingly loyal to those "
            "who earn his respect. Background: former military special forces, "
            "discharged after a classified incident. Motivation: protect his "
            "territory and settle old scores with the Nexus Corporation.\n\n"
            "## Mei Lin\n\n"
            "A brilliant hacker and information broker who operates from a "
            "hidden node in the Shadow Market. Age: 28. Appearance: slight build, "
            "short dark hair, always wearing AR glasses. Personality: curious, "
            "sarcastic, fiercely independent. Background: grew up in the district, "
            "self-taught coder. She knows where the bodies are buried — literally "
            "and figuratively. Motivation: expose corporate corruption.\n"
        ),
        char_count=750,
    ),
]


@pytest.fixture
def extraction():
    return ExtractionResult(
        pdf_path="/tmp/undercity_sourcebook.pdf",
        total_pages=3,
        pages=FIXTURE_PAGES,
        output_dir="/tmp/extract",
    )


class TestIngestPipelineIntegration:
    """Integration test: structure → segment → classify → enrich → assemble → validate."""

    def test_full_lore_pipeline(self, extraction, tmp_path):
        """Run stages 2-7 and verify the output installs as a content pack."""
        work = tmp_path / "work"

        # Stage 2: Structure
        detector = StructureDetector()
        structure = detector.detect(extraction, work / "structure")
        assert len(structure.sections) >= 2

        # Stage 3: Segment
        segmenter = ContentSegmenter(min_words=30, max_words=2000)
        manifest = segmenter.segment(structure, work / "segment")
        assert len(manifest.segments) >= 3

        # Stage 4: Classify
        classifier = ContentClassifier()
        manifest = classifier.classify(manifest, work / "classify")
        for seg in manifest.segments:
            assert seg.content_type is not None
            assert seg.route is not None

        # Stage 5: Enrich
        enricher = LoreEnricher()
        enriched_files, entity_registry = enricher.enrich(
            manifest, work / "enrich"
        )
        assert len(enriched_files) >= 3
        assert len(entity_registry.entities) >= 2

        # Stage 6: Assemble
        config = IngestConfig(
            pack_id="undercity_test",
            pack_name="Undercity Test Pack",
            pack_version="1.0",
            pack_layer="sourcebook",
        )
        assembler = PackAssembler()
        pack_dir = assembler.assemble(
            enriched_files, config, work / "assemble"
        )
        assert pack_dir.exists()
        assert (pack_dir / "pack.yaml").exists()

        # Verify pack.yaml content
        pack_manifest = yaml.safe_load((pack_dir / "pack.yaml").read_text())
        assert pack_manifest["id"] == "undercity_test"

        # Count content files
        md_files = list(pack_dir.rglob("*.md"))
        assert len(md_files) >= 3

        # Stage 7: Validate
        validator = PackValidator()
        report = validator.validate(pack_dir, work / "validate")
        assert report.valid is True, f"Validation failed: {report.errors}"

        # Verify installation test passed
        if "installation" in report.stats:
            assert report.stats["installation"]["chunks_created"] > 0

    def test_classification_distribution(self, extraction, tmp_path):
        """Verify segments are classified into multiple types."""
        work = tmp_path / "work"

        detector = StructureDetector()
        structure = detector.detect(extraction, work / "structure")

        segmenter = ContentSegmenter(min_words=30, max_words=2000)
        manifest = segmenter.segment(structure, work / "segment")

        classifier = ContentClassifier()
        manifest = classifier.classify(manifest, work / "classify")

        types = set()
        for seg in manifest.segments:
            if seg.content_type:
                types.add(seg.content_type)

        # Should detect at least locations and NPCs
        assert len(types) >= 2

    def test_entity_extraction_finds_npcs(self, extraction, tmp_path):
        """Verify entity extraction identifies NPCs from the text."""
        work = tmp_path / "work"

        detector = StructureDetector()
        structure = detector.detect(extraction, work / "structure")

        segmenter = ContentSegmenter(min_words=30, max_words=2000)
        manifest = segmenter.segment(structure, work / "segment")

        classifier = ContentClassifier()
        manifest = classifier.classify(manifest, work / "classify")

        enricher = LoreEnricher()
        _, registry = enricher.enrich(manifest, work / "enrich")

        # Should find Viktor and Mei Lin as NPCs
        npc_names = [e.name for e in registry.list_by_type("npc")]
        assert len(npc_names) >= 1

    def test_pack_installs_via_existing_infrastructure(self, extraction, tmp_path):
        """The assembled pack should load via PackLoader and index via Chunker+Indexer."""
        work = tmp_path / "work"

        # Quick pipeline run
        detector = StructureDetector()
        structure = detector.detect(extraction, work / "structure")

        segmenter = ContentSegmenter(min_words=30, max_words=2000)
        manifest = segmenter.segment(structure, work / "segment")

        classifier = ContentClassifier()
        manifest = classifier.classify(manifest, work / "classify")

        enricher = LoreEnricher()
        enriched_files, _ = enricher.enrich(manifest, work / "enrich")

        config = IngestConfig(
            pack_id="install_test",
            pack_name="Install Test Pack",
        )
        assembler = PackAssembler()
        pack_dir = assembler.assemble(enriched_files, config, work / "assemble")

        # Now use the EXISTING content pack infrastructure
        from src.content.pack_loader import PackLoader
        from src.content.chunker import Chunker
        from src.content.indexer import LoreIndexer
        from src.content.vector_store import NullVectorStore
        from src.db.state_store import StateStore

        store = StateStore(str(tmp_path / "install_test.db"))
        store.ensure_schema()

        loader = PackLoader()
        pack_manifest, files = loader.load_pack(pack_dir)
        assert pack_manifest.id == "install_test"
        assert len(files) >= 1

        chunker = Chunker()
        chunks = chunker.chunk_files(files, pack_manifest.id)
        assert len(chunks) >= 1

        indexer = LoreIndexer(store, NullVectorStore())
        stats = indexer.index_pack(pack_manifest, chunks)
        assert stats.chunks_indexed > 0
        assert stats.fts_indexed > 0
