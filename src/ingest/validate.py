"""Stage 7: Content Pack Validation.

Validates the assembled content pack by:
  1. Structural checks (pack.yaml, required dirs, file format)
  2. Installation test (in-memory DB via PackLoader/Chunker/Indexer)
  3. Retrieval spot-checks (FTS5 queries against indexed content)
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from .utils import write_stage_meta

logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    """Validation results for an assembled content pack."""
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


class PackValidator:
    """Validates assembled content packs against engine requirements."""

    def validate(
        self,
        pack_dir: str | Path,
        output_dir: str | Path | None = None,
    ) -> ValidationReport:
        """Run full validation on an assembled content pack.

        Args:
            pack_dir: Path to the content pack directory.
            output_dir: Optional directory to write validation report.

        Returns:
            ValidationReport with results.
        """
        pack_dir = Path(pack_dir)
        report = ValidationReport()

        # Phase 1: Structural validation
        self._validate_structure(pack_dir, report)

        # Phase 2: Installation test
        if report.valid:
            self._validate_installation(pack_dir, report)

        # Phase 3: Retrieval spot-checks
        if report.valid:
            self._validate_retrieval(pack_dir, report)

        if output_dir:
            write_stage_meta(Path(output_dir), {
                "stage": "validate",
                "status": "complete" if report.valid else "failed",
                "valid": report.valid,
                "errors": report.errors,
                "warnings": report.warnings,
                "stats": report.stats,
            })

        log_fn = logger.info if report.valid else logger.error
        log_fn(
            "Pack validation %s: %d errors, %d warnings",
            "PASSED" if report.valid else "FAILED",
            len(report.errors),
            len(report.warnings),
        )
        return report

    def _validate_structure(self, pack_dir: Path, report: ValidationReport) -> None:
        """Check directory structure and file format."""
        # Check pack.yaml exists
        manifest_path = pack_dir / "pack.yaml"
        if not manifest_path.exists():
            report.add_error("Missing pack.yaml manifest")
            return

        # Validate manifest
        try:
            import yaml
            data = yaml.safe_load(manifest_path.read_text())
            if not isinstance(data, dict):
                report.add_error("pack.yaml is not a valid YAML mapping")
                return
            if not data.get("id"):
                report.add_error("pack.yaml missing 'id' field")
            if not data.get("name"):
                report.add_error("pack.yaml missing 'name' field")
        except Exception as e:
            report.add_error(f"Invalid pack.yaml: {e}")
            return

        # Check for content files
        md_files = list(pack_dir.rglob("*.md"))
        if not md_files:
            report.add_warning("No markdown content files found")

        report.stats["manifest"] = data
        report.stats["file_count"] = len(md_files)

        # Validate each markdown file
        valid_files = 0
        for md_file in md_files:
            try:
                text = md_file.read_text(encoding="utf-8")
                if text.startswith("---"):
                    # Has frontmatter — validate it
                    parts = text.split("---", 2)
                    if len(parts) >= 3:
                        import yaml
                        fm = yaml.safe_load(parts[1])
                        if not isinstance(fm, dict):
                            report.add_warning(
                                f"{md_file.name}: frontmatter is not a mapping"
                            )
                            continue
                        if not fm.get("title"):
                            report.add_warning(
                                f"{md_file.name}: missing 'title' in frontmatter"
                            )
                valid_files += 1
            except Exception as e:
                report.add_warning(f"Error reading {md_file.name}: {e}")

        report.stats["valid_files"] = valid_files

    def _validate_installation(
        self,
        pack_dir: Path,
        report: ValidationReport
    ) -> None:
        """Test that the pack can be loaded and indexed."""
        try:
            from src.content.pack_loader import PackLoader
            from src.content.chunker import Chunker
            from src.content.indexer import LoreIndexer
            from src.content.vector_store import NullVectorStore
            from src.db.state_store import StateStore
        except ImportError as e:
            report.add_warning(f"Cannot run installation test: {e}")
            return

        import tempfile
        import os

        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = StateStore(db_path)
            store.ensure_schema()

            loader = PackLoader()
            manifest, files = loader.load_pack(pack_dir)

            chunker = Chunker()
            chunks = chunker.chunk_files(files, manifest.id)

            indexer = LoreIndexer(store, NullVectorStore())
            stats = indexer.index_pack(manifest, chunks)

            report.stats["installation"] = {
                "pack_id": manifest.id,
                "files_loaded": len(files),
                "chunks_created": stats.chunks_indexed,
                "fts_indexed": stats.fts_indexed,
            }

            if stats.chunks_indexed == 0:
                report.add_warning("Pack installed but produced 0 chunks")

        except Exception as e:
            report.add_error(f"Installation test failed: {e}")
        finally:
            os.unlink(db_path)

    def _validate_retrieval(
        self,
        pack_dir: Path,
        report: ValidationReport
    ) -> None:
        """Run retrieval spot-checks against indexed content."""
        try:
            from src.content.pack_loader import PackLoader
            from src.content.chunker import Chunker
            from src.content.indexer import LoreIndexer
            from src.content.retriever import LoreRetriever, LoreQuery
            from src.content.vector_store import NullVectorStore
            from src.db.state_store import StateStore
        except ImportError:
            return

        import tempfile
        import os

        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = StateStore(db_path)
            store.ensure_schema()

            loader = PackLoader()
            manifest, files = loader.load_pack(pack_dir)

            chunker = Chunker()
            chunks = chunker.chunk_files(files, manifest.id)

            indexer = LoreIndexer(store, NullVectorStore())
            indexer.index_pack(manifest, chunks)

            retriever = LoreRetriever(store, NullVectorStore())

            # Spot-check: search for the first 3 file titles
            hits = 0
            queries_run = 0
            for f in files[:3]:
                query = LoreQuery(
                    keywords=f.title.split()[:3],
                    entity_ids=[],
                    chunk_types=[],
                    pack_ids=[manifest.id],
                )
                result = retriever.query(query)
                queries_run += 1
                if result.chunks:
                    hits += 1

            report.stats["retrieval"] = {
                "queries_run": queries_run,
                "queries_with_results": hits,
            }

            if queries_run > 0 and hits == 0:
                report.add_warning(
                    "Retrieval spot-check: no results for any test query"
                )

        except Exception as e:
            report.add_warning(f"Retrieval spot-check failed: {e}")
        finally:
            os.unlink(db_path)
