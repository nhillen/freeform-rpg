"""
Interactive guided flow for the PDF-to-Content-Pack ingest pipeline.

Launched by `freeform-rpg pack-ingest` with no arguments.
Walks the user through PDF selection, metadata, pipeline options,
runs the pipeline with progress display, and offers pack installation.
"""

import os
import sys
import time
from pathlib import Path

from src.config import check_auth_or_prompt
from src.cli.spinner import Spinner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_input(prompt: str, default: str = "") -> str | None:
    """Prompt for input, returning None on interrupt."""
    try:
        value = input(prompt).strip()
        return value if value else default
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def _abort():
    """Clean exit on cancel."""
    print("\n  Goodbye!")
    sys.exit(0)


def _format_file_size(path: Path) -> str:
    """Human-readable file size."""
    size = path.stat().st_size
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"


def _print_ingest_banner():
    """Print the ingest pipeline banner."""
    print()
    print("\u250c" + "\u2500" * 58 + "\u2510")
    print("\u2502" + " Content Pack Ingest Pipeline ".center(58) + "\u2502")
    print("\u2502" + " PDF-to-Content-Pack Converter ".center(58) + "\u2502")
    print("\u2514" + "\u2500" * 58 + "\u2518")
    print()


def _check_dependencies(use_ocr: bool = False):
    """Check that required ingest dependencies are installed. Exits on failure."""
    missing = []

    try:
        import fitz  # noqa: F401
    except ImportError:
        missing.append("pymupdf")

    if use_ocr:
        try:
            import pytesseract  # noqa: F401
        except ImportError:
            missing.append("pytesseract")

    if missing:
        names = ", ".join(missing)
        print(f"  Missing dependencies: {names}")
        print()
        print("  Install with:")
        print("    pip install 'freeform-rpg[ingest]'")
        print()
        sys.exit(1)


def _confirm(prompt: str, default_yes: bool = True) -> bool | None:
    """Ask a yes/no question. Returns True/False, or None on interrupt."""
    suffix = "[Y/n]" if default_yes else "[y/N]"
    value = _safe_input(f"  {prompt} {suffix} ")
    if value is None:
        return None
    if not value:
        return default_yes
    return value.lower() in ("y", "yes")


# ---------------------------------------------------------------------------
# Prompt functions
# ---------------------------------------------------------------------------

def _prompt_pdf_path() -> Path | None:
    """Prompt for PDF file path with validation."""
    print("  \u2500\u2500 PDF Source \u2500\u2500")
    print()

    while True:
        value = _safe_input("  PDF file path: ")
        if value is None:
            return None
        if not value:
            print("  Please enter a path to a PDF file.")
            continue

        path = Path(value).expanduser().resolve()
        if not path.exists():
            print(f"  File not found: {path}")
            continue
        if path.suffix.lower() != ".pdf":
            print(f"  Not a PDF file: {path.name}")
            continue

        size = _format_file_size(path)
        print(f"  Found: {path.name} ({size})")
        print()
        return path


def _prompt_pack_metadata(pdf_path: Path) -> dict | None:
    """Prompt for pack metadata, auto-suggesting from filename."""
    print("  \u2500\u2500 Pack Metadata \u2500\u2500")
    print()

    stem = pdf_path.stem.replace("_", " ").replace("-", " ")
    # Derive a clean slug for pack ID
    default_id = pdf_path.stem.lower().replace(" ", "_").replace("-", "_")

    pack_id = _safe_input(f"  Pack ID [{default_id}]: ", default_id)
    if pack_id is None:
        return None

    default_name = stem.title()
    pack_name = _safe_input(f"  Pack name [{default_name}]: ", default_name)
    if pack_name is None:
        return None

    pack_version = _safe_input("  Version [1.0]: ", "1.0")
    if pack_version is None:
        return None

    print()
    print("  Pack layer:")
    layers = ["sourcebook", "supplement", "scenario"]
    descriptions = [
        "primary reference",
        "expands a sourcebook",
        "playable content",
    ]
    for i, (layer, desc) in enumerate(zip(layers, descriptions), 1):
        print(f"    {i}. {layer} ({desc})")

    choice = _safe_input("  Choose layer [1]: ", "1")
    if choice is None:
        return None
    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(layers)):
            idx = 0
    except ValueError:
        idx = 0
    pack_layer = layers[idx]

    print()
    pack_author = _safe_input("  Author (optional, Enter to skip): ", "")
    if pack_author is None:
        return None

    pack_description = _safe_input("  Description (optional, Enter to skip): ", "")
    if pack_description is None:
        return None

    print()
    return {
        "pack_id": pack_id,
        "pack_name": pack_name,
        "pack_version": pack_version,
        "pack_layer": pack_layer,
        "pack_author": pack_author,
        "pack_description": pack_description,
    }


def _prompt_pipeline_options() -> dict | None:
    """Prompt for pipeline options (OCR, images, systems)."""
    print("  \u2500\u2500 Pipeline Options \u2500\u2500")
    print()

    use_ocr = _confirm("Use OCR for image-heavy pages?", default_yes=False)
    if use_ocr is None:
        return None

    extract_images = _confirm("Extract embedded images?", default_yes=False)
    if extract_images is None:
        return None

    include_systems = _confirm("Include systems extraction?", default_yes=True)
    if include_systems is None:
        return None

    print()
    return {
        "use_ocr": use_ocr,
        "extract_images": extract_images,
        "skip_systems": not include_systems,
    }


def _prompt_output_dir(pack_id: str) -> str | None:
    """Prompt for output directory."""
    print("  \u2500\u2500 Output \u2500\u2500")
    print()

    default = f"./ingest_output/{pack_id}/"
    value = _safe_input(f"  Output directory [{default}]: ", default)
    if value is None:
        return None

    print()
    return value


def _show_confirmation_summary(config: dict) -> bool | None:
    """Show pre-run summary and ask for confirmation."""
    print("  \u2500\u2500 Summary \u2500\u2500")
    print()
    print(f"    PDF:         {config['pdf_name']}")
    print(f"    Pack ID:     {config['pack_id']}")
    print(f"    Pack Name:   {config['pack_name']}")
    print(f"    Version:     {config['pack_version']}")
    print(f"    Layer:       {config['pack_layer']}")
    print(f"    OCR:         {'Yes' if config['use_ocr'] else 'No'}")
    print(f"    Images:      {'Yes' if config['extract_images'] else 'No'}")
    print(f"    Systems:     {'No' if config['skip_systems'] else 'Yes'}")
    print(f"    Output:      {config['output_dir']}")
    print()

    return _confirm("Start pipeline?", default_yes=True)


# ---------------------------------------------------------------------------
# Pipeline execution with progress
# ---------------------------------------------------------------------------

STAGE_LABELS = {
    "extract": "Extracting PDF text",
    "structure": "Detecting document structure",
    "segment": "Segmenting content",
    "classify": "Classifying segments",
    "enrich": "Enriching lore content",
    "assemble": "Assembling content pack",
    "validate": "Validating content pack",
    "systems": "Extracting game systems",
}


def _stage_summary_line(name: str, elapsed_ms: float, result) -> str:
    """Build a one-line summary for a completed stage."""
    secs = elapsed_ms / 1000
    detail = ""
    if name == "extract" and result is not None:
        detail = f" -- {result.total_pages} pages extracted"
    elif name == "structure" and result is not None:
        detail = f" -- {len(result.sections)} sections detected"
    elif name == "segment" and result is not None:
        detail = f" -- {len(result.segments)} segments created"
    elif name == "classify" and result is not None:
        lore = sum(1 for s in result.segments if s.route and s.route.value == "lore")
        systems = sum(1 for s in result.segments if s.route and s.route.value == "systems")
        detail = f" -- {lore} lore, {systems} systems"
    elif name == "enrich":
        if isinstance(result, tuple) and len(result) == 2:
            files, registry = result
            detail = f" -- {len(files)} files, {len(registry.entities)} entities"
    elif name == "assemble" and result is not None:
        detail = f" -- {result}"
    elif name == "validate" and result is not None:
        status = "PASSED" if result.valid else "FAILED"
        detail = f" -- {status}"
        if result.errors:
            detail += f" ({len(result.errors)} errors)"
    elif name == "systems" and result is not None:
        status = "PASSED" if result.valid else "FAILED"
        detail = f" -- {status}"

    return f"    Done ({secs:.1f}s){detail}"


class InstrumentedPipeline:
    """Wraps IngestPipeline to add per-stage spinner and summary output."""

    def __init__(self, pipeline):
        self._pipeline = pipeline
        self._original_run_stage = pipeline._run_stage
        self._stage_index = 0
        self._total_stages = 7
        if not pipeline.config.skip_systems:
            self._total_stages = 8

    def run(self, resume: bool = True, from_stage: str | None = None) -> dict:
        """Run with instrumented _run_stage."""
        self._pipeline._run_stage = self._instrumented_run_stage
        try:
            return self._pipeline.run(resume=resume, from_stage=from_stage)
        finally:
            self._pipeline._run_stage = self._original_run_stage

    def _instrumented_run_stage(self, name, stage_dir, resume, fn, *args, **kwargs):
        """Wrap each stage with spinner and summary."""
        self._stage_index += 1
        label = STAGE_LABELS.get(name, name.replace("_", " ").title())
        header = f"  Stage {self._stage_index}/{self._total_stages}: {label}..."
        print(header)

        spinner = Spinner(f"  {label}")
        start = time.time()
        with spinner:
            # Give the pipeline a progress callback that updates the spinner
            self._pipeline._progress_fn = spinner.update
            result = self._original_run_stage(name, stage_dir, resume, fn, *args, **kwargs)
            self._pipeline._progress_fn = None
        elapsed_ms = (time.time() - start) * 1000

        summary = _stage_summary_line(name, elapsed_ms, result)
        print(summary)
        print()
        return result


def _run_pipeline_with_progress(config: dict, api_key: str) -> dict:
    """Create gateways, build pipeline, run with progress display."""
    from src.ingest.pipeline import IngestPipeline
    from src.ingest.models import IngestConfig
    from src.llm.gateway import ClaudeGateway
    from src.llm.prompt_registry import PromptRegistry

    ingest_config = IngestConfig(
        pdf_path=config["pdf_path"],
        output_dir=config["output_dir"],
        pack_id=config["pack_id"],
        pack_name=config["pack_name"],
        pack_version=config["pack_version"],
        pack_layer=config["pack_layer"],
        pack_author=config["pack_author"],
        pack_description=config["pack_description"],
        use_ocr=config["use_ocr"],
        extract_images=config["extract_images"],
        skip_systems=config["skip_systems"],
        work_dir=config["output_dir"],
    )

    sonnet = ClaudeGateway(api_key=api_key)
    haiku = ClaudeGateway(api_key=api_key, model="claude-3-5-haiku-20241022")
    prompts_dir = Path(__file__).parent.parent / "prompts"
    registry = PromptRegistry(prompts_dir)

    pipeline = IngestPipeline(
        config=ingest_config,
        sonnet_gateway=sonnet,
        haiku_gateway=haiku,
        prompt_registry=registry,
    )

    instrumented = InstrumentedPipeline(pipeline)
    return instrumented.run(resume=True)


def _show_final_summary(summary: dict):
    """Show pipeline completion summary."""
    print("  \u2500\u2500 Pipeline Complete \u2500\u2500")
    print()
    print(f"    Pack directory: {summary.get('pack_dir', 'N/A')}")

    valid = summary.get("pack_valid", False)
    print(f"    Validation:     {'PASSED' if valid else 'FAILED'}")
    errors = summary.get("validation_errors", [])
    if errors:
        for err in errors[:5]:
            print(f"      - {err}")

    systems = summary.get("systems_valid")
    if systems is not None:
        print(f"    Systems:        {'PASSED' if systems else 'FAILED'}")

    timings = summary.get("timings", {})
    if timings:
        total_ms = sum(timings.values())
        print(f"    Total time:     {total_ms / 1000:.1f}s")

    print()


def _offer_install(pack_dir: str, db_path: str):
    """Offer to install the pack into the game database."""
    result = _confirm("Install this pack into the game database?", default_yes=True)
    if result is None:
        _abort()
    if not result:
        return

    from src.db.state_store import StateStore
    from src.content.pack_loader import PackLoader
    from src.content.chunker import Chunker
    from src.content.indexer import LoreIndexer
    from src.content.vector_store import create_vector_store

    store = StateStore(db_path)
    store.ensure_schema()

    loader = PackLoader()
    chunker = Chunker()
    vector_store = create_vector_store()
    indexer = LoreIndexer(store, vector_store)

    pack_path = Path(pack_dir)
    spinner = Spinner("  Installing pack")
    with spinner:
        manifest, files = loader.load_pack(pack_path)
        chunks = chunker.chunk_files(files, manifest.id)
        stats = indexer.index_pack(manifest, chunks)

    print(f"  Installed: {manifest.name}")
    print(f"    Chunks indexed: {stats.chunks_indexed}")
    print(f"    FTS5 indexed:   {stats.fts_indexed}")
    print(f"    Vector indexed: {stats.vector_indexed}")
    print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def ingest_flow(db_path: str = "game.db"):
    """Interactive ingest flow entry point."""
    _print_ingest_banner()

    # Step 0: Check core dependencies before prompting
    _check_dependencies()

    # Step 1: API key
    api_key = check_auth_or_prompt()
    if not api_key:
        print("  Cannot run ingest without an API key.")
        print("  Run 'freeform-rpg login' or set ANTHROPIC_API_KEY.")
        sys.exit(1)

    # Step 2: PDF path
    pdf_path = _prompt_pdf_path()
    if pdf_path is None:
        _abort()

    # Step 3: Pack metadata
    metadata = _prompt_pack_metadata(pdf_path)
    if metadata is None:
        _abort()

    # Step 4: Pipeline options
    options = _prompt_pipeline_options()
    if options is None:
        _abort()

    # Check OCR dependency if selected
    if options["use_ocr"]:
        _check_dependencies(use_ocr=True)

    # Step 5: Output directory
    output_dir = _prompt_output_dir(metadata["pack_id"])
    if output_dir is None:
        _abort()

    # Build full config
    config = {
        "pdf_path": str(pdf_path),
        "pdf_name": pdf_path.name,
        "output_dir": output_dir,
        **metadata,
        **options,
    }

    # Step 6: Confirmation
    proceed = _show_confirmation_summary(config)
    if proceed is None:
        _abort()
    if not proceed:
        print("  Cancelled.")
        return

    # Step 7: Run pipeline
    print()
    print("  \u2500\u2500 Running Pipeline \u2500\u2500")
    print()

    try:
        summary = _run_pipeline_with_progress(config, api_key)
    except KeyboardInterrupt:
        print("\n\n  Pipeline interrupted. Progress has been saved.")
        print("  Re-run to resume from the last completed stage.")
        sys.exit(1)
    except Exception as e:
        print(f"\n  Pipeline error: {e}")
        sys.exit(1)

    # Step 8: Final summary
    _show_final_summary(summary)

    # Step 9: Offer install
    pack_dir = summary.get("pack_dir")
    if pack_dir and summary.get("pack_valid", False):
        _offer_install(pack_dir, db_path)
