"""Tests for the pipeline orchestrator."""

import json
import pytest
from pathlib import Path

from src.ingest.models import IngestConfig
from src.ingest.pipeline import IngestPipeline, STAGE_ORDER, STAGE_DIRS


class TestIngestConfig:
    def test_work_dir_derived_from_pdf(self):
        config = IngestConfig(
            pdf_path="/data/sourcebook.pdf",
            output_dir="/data/output",
        )
        wd = config.get_work_dir()
        assert "sourcebook" in str(wd)

    def test_explicit_work_dir(self):
        config = IngestConfig(work_dir="/custom/path")
        assert str(config.get_work_dir()) == "/custom/path"

    def test_default_config(self):
        config = IngestConfig()
        assert config.min_segment_words == 100
        assert config.max_segment_words == 1500
        assert config.skip_systems is False
        assert config.use_ocr is False


class TestPipelineInit:
    def test_creates_with_config(self):
        config = IngestConfig(pdf_path="test.pdf")
        pipeline = IngestPipeline(config=config)
        assert pipeline.config.pdf_path == "test.pdf"
        assert pipeline.sonnet is None
        assert pipeline.haiku is None

    def test_haiku_falls_back_to_sonnet(self):
        from src.llm.gateway import MockGateway
        config = IngestConfig()
        gateway = MockGateway()
        pipeline = IngestPipeline(config=config, sonnet_gateway=gateway)
        # haiku should fall back to sonnet when not provided
        assert pipeline.haiku is gateway


class TestStageConstants:
    def test_stage_order_has_all_stages(self):
        assert len(STAGE_ORDER) == 8
        assert "extract" in STAGE_ORDER
        assert "systems" in STAGE_ORDER

    def test_stage_dirs_matches_order(self):
        for stage in STAGE_ORDER:
            assert stage in STAGE_DIRS

    def test_stage_order_is_sequential(self):
        assert STAGE_ORDER.index("extract") < STAGE_ORDER.index("structure")
        assert STAGE_ORDER.index("structure") < STAGE_ORDER.index("segment")
        assert STAGE_ORDER.index("classify") < STAGE_ORDER.index("enrich")


class TestClearFromStage:
    def test_clears_target_and_downstream(self, tmp_path):
        config = IngestConfig(work_dir=str(tmp_path))
        pipeline = IngestPipeline(config=config)

        # Create all stage dirs
        for stage_dir_name in STAGE_DIRS.values():
            (tmp_path / stage_dir_name).mkdir()

        pipeline._clear_from_stage("classify", tmp_path)

        # Upstream stages should still exist
        assert (tmp_path / "01_extract").exists()
        assert (tmp_path / "02_structure").exists()
        assert (tmp_path / "03_segment").exists()
        # Target and downstream should be cleared
        assert not (tmp_path / "04_classify").exists()
        assert not (tmp_path / "05_lore").exists()
        assert not (tmp_path / "06_assemble").exists()
        assert not (tmp_path / "07_validate").exists()
        assert not (tmp_path / "08_systems").exists()

    def test_clears_from_extract(self, tmp_path):
        config = IngestConfig(work_dir=str(tmp_path))
        pipeline = IngestPipeline(config=config)

        for stage_dir_name in STAGE_DIRS.values():
            (tmp_path / stage_dir_name).mkdir()

        pipeline._clear_from_stage("extract", tmp_path)

        # Everything should be cleared
        for stage_dir_name in STAGE_DIRS.values():
            assert not (tmp_path / stage_dir_name).exists()

    def test_invalid_stage_raises(self, tmp_path):
        config = IngestConfig(work_dir=str(tmp_path))
        pipeline = IngestPipeline(config=config)

        with pytest.raises(ValueError, match="Unknown stage"):
            pipeline._clear_from_stage("bogus", tmp_path)

    def test_missing_dirs_no_error(self, tmp_path):
        config = IngestConfig(work_dir=str(tmp_path))
        pipeline = IngestPipeline(config=config)

        # No dirs exist — should not raise
        pipeline._clear_from_stage("structure", tmp_path)


class TestRunStageResume:
    def test_skips_completed_stage_with_loader(self, tmp_path):
        config = IngestConfig(work_dir=str(tmp_path))
        pipeline = IngestPipeline(config=config)

        stage_dir = tmp_path / "test_stage"
        stage_dir.mkdir()

        # Write a completed stage_meta.json
        (stage_dir / "stage_meta.json").write_text(
            json.dumps({"status": "complete"})
        )

        run_count = 0
        def fake_fn():
            nonlocal run_count
            run_count += 1
            return "ran"

        def fake_loader(d):
            return "loaded"

        result = pipeline._run_stage(
            "test", stage_dir, True, fake_fn, loader=fake_loader
        )

        assert result == "loaded"
        assert run_count == 0  # fn should NOT have been called

    def test_runs_when_no_checkpoint(self, tmp_path):
        config = IngestConfig(work_dir=str(tmp_path))
        pipeline = IngestPipeline(config=config)

        stage_dir = tmp_path / "test_stage"

        def fake_fn():
            return "ran"

        def fake_loader(d):
            return "loaded"

        result = pipeline._run_stage(
            "test", stage_dir, True, fake_fn, loader=fake_loader
        )

        assert result == "ran"

    def test_runs_when_resume_false(self, tmp_path):
        config = IngestConfig(work_dir=str(tmp_path))
        pipeline = IngestPipeline(config=config)

        stage_dir = tmp_path / "test_stage"
        stage_dir.mkdir()
        (stage_dir / "stage_meta.json").write_text(
            json.dumps({"status": "complete"})
        )

        def fake_fn():
            return "ran"

        def fake_loader(d):
            return "loaded"

        result = pipeline._run_stage(
            "test", stage_dir, False, fake_fn, loader=fake_loader
        )

        assert result == "ran"  # Should run, not load

    def test_runs_when_no_loader(self, tmp_path):
        config = IngestConfig(work_dir=str(tmp_path))
        pipeline = IngestPipeline(config=config)

        stage_dir = tmp_path / "test_stage"
        stage_dir.mkdir()
        (stage_dir / "stage_meta.json").write_text(
            json.dumps({"status": "complete"})
        )

        def fake_fn():
            return "ran"

        # No loader — must run even with checkpoint
        result = pipeline._run_stage(
            "test", stage_dir, True, fake_fn
        )

        assert result == "ran"
