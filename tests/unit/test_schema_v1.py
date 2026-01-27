"""Tests for v1 schema additions: sessions, content packs, pack chunks, scene lore."""

import pytest
from src.db.state_store import StateStore, new_id


class TestSchemaV1Creation:
    """Test that v1 tables are created correctly."""

    def test_ensure_schema_creates_v1_tables(self, state_store):
        """ensure_schema() should create all v1 tables."""
        with state_store.connect() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        table_names = {row["name"] for row in tables}
        assert "sessions" in table_names
        assert "content_packs" in table_names
        assert "pack_chunks" in table_names
        assert "scene_lore" in table_names

    def test_fts5_virtual_table_created(self, state_store):
        """FTS5 virtual table for pack chunks should exist."""
        with state_store.connect() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        table_names = {row["name"] for row in tables}
        assert "pack_chunks_fts" in table_names

    def test_schema_v1_idempotent(self, state_store):
        """Calling ensure_schema_v1() multiple times should not fail."""
        state_store.ensure_schema_v1()
        state_store.ensure_schema_v1()
        # No exception means success

    def test_provenance_columns_added(self, state_store):
        """Provenance columns should be added to existing tables."""
        with state_store.connect() as conn:
            # Check entities has origin column
            row = conn.execute("PRAGMA table_info(entities)").fetchall()
            col_names = {r["name"] for r in row}
            assert "origin" in col_names
            assert "pack_id" in col_names
            assert "pack_entity_id" in col_names

            # Check facts
            row = conn.execute("PRAGMA table_info(facts)").fetchall()
            col_names = {r["name"] for r in row}
            assert "origin" in col_names
            assert "pack_id" in col_names

            # Check threads
            row = conn.execute("PRAGMA table_info(threads)").fetchall()
            col_names = {r["name"] for r in row}
            assert "origin" in col_names

            # Check clocks
            row = conn.execute("PRAGMA table_info(clocks)").fetchall()
            col_names = {r["name"] for r in row}
            assert "origin" in col_names

            # Check relationships
            row = conn.execute("PRAGMA table_info(relationships)").fetchall()
            col_names = {r["name"] for r in row}
            assert "origin" in col_names

    def test_provenance_alter_idempotent(self, state_store):
        """ALTER TABLE for provenance columns should be idempotent."""
        state_store.ensure_schema_v1()
        state_store.ensure_schema_v1()
        # Verify columns still exist and work
        with state_store.connect() as conn:
            row = conn.execute("PRAGMA table_info(entities)").fetchall()
            col_names = {r["name"] for r in row}
            assert "origin" in col_names


class TestSessionCRUD:
    """Test session lifecycle operations."""

    def test_create_session(self, state_store):
        sid = new_id()
        cid = "test_campaign"
        state_store.create_campaign(cid, "Test")
        session = state_store.create_session(sid, cid)
        assert session["id"] == sid
        assert session["campaign_id"] == cid
        assert session["ended_at"] is None

    def test_get_session(self, state_store):
        sid = new_id()
        cid = "test_campaign"
        state_store.create_campaign(cid, "Test")
        state_store.create_session(sid, cid)
        session = state_store.get_session(sid)
        assert session is not None
        assert session["id"] == sid

    def test_get_session_not_found(self, state_store):
        assert state_store.get_session("nonexistent") is None

    def test_get_active_session(self, state_store):
        cid = "test_campaign"
        state_store.create_campaign(cid, "Test")

        sid1 = new_id()
        state_store.create_session(sid1, cid, started_at="2024-01-01T00:00:00")
        state_store.end_session(sid1)

        sid2 = new_id()
        state_store.create_session(sid2, cid, started_at="2024-01-02T00:00:00")

        active = state_store.get_active_session(cid)
        assert active is not None
        assert active["id"] == sid2

    def test_get_active_session_none(self, state_store):
        cid = "test_campaign"
        state_store.create_campaign(cid, "Test")
        assert state_store.get_active_session(cid) is None

    def test_end_session(self, state_store):
        sid = new_id()
        cid = "test_campaign"
        state_store.create_campaign(cid, "Test")
        state_store.create_session(sid, cid)
        state_store.end_session(sid, recap_text="A good session.")
        session = state_store.get_session(sid)
        assert session["ended_at"] is not None
        assert session["recap_text"] == "A good session."


class TestContentPackCRUD:
    """Test content pack operations."""

    def test_create_content_pack(self, state_store):
        pack = state_store.create_content_pack(
            "test-pack", "Test Pack", "/path/to/pack",
            description="A test pack", version="1.0", layer="adventure"
        )
        assert pack["id"] == "test-pack"
        assert pack["name"] == "Test Pack"
        assert pack["layer"] == "adventure"

    def test_get_content_pack(self, state_store):
        state_store.create_content_pack("tp", "Test", "/path")
        pack = state_store.get_content_pack("tp")
        assert pack is not None
        assert pack["id"] == "tp"

    def test_get_content_pack_not_found(self, state_store):
        assert state_store.get_content_pack("nope") is None

    def test_list_content_packs(self, state_store):
        state_store.create_content_pack("p1", "Pack 1", "/p1")
        state_store.create_content_pack("p2", "Pack 2", "/p2")
        packs = state_store.list_content_packs()
        assert len(packs) == 2

    def test_create_content_pack_idempotent(self, state_store):
        state_store.create_content_pack("tp", "Test", "/path", chunk_count=5)
        state_store.create_content_pack("tp", "Test Updated", "/path2", chunk_count=10)
        pack = state_store.get_content_pack("tp")
        assert pack["name"] == "Test Updated"
        assert pack["chunk_count"] == 10

    def test_content_pack_metadata(self, state_store):
        state_store.create_content_pack(
            "tp", "Test", "/path",
            metadata={"author": "Test", "genre": "cyberpunk"}
        )
        pack = state_store.get_content_pack("tp")
        assert pack["metadata"]["author"] == "Test"


class TestPackChunkCRUD:
    """Test pack chunk operations."""

    def test_insert_and_get_chunks(self, state_store):
        state_store.create_content_pack("tp", "Test", "/path")
        state_store.insert_pack_chunk(
            chunk_id="tp:locations:neon_dragon:overview",
            pack_id="tp",
            file_path="locations/neon_dragon.md",
            section_title="The Neon Dragon",
            content="A seedy bar in the undercity.",
            chunk_type="location",
            entity_refs=["neon_dragon"],
            tags=["location", "undercity"],
            token_estimate=50
        )
        chunks = state_store.get_pack_chunks("tp")
        assert len(chunks) == 1
        assert chunks[0]["section_title"] == "The Neon Dragon"
        assert chunks[0]["chunk_type"] == "location"
        assert "neon_dragon" in chunks[0]["entity_refs"]

    def test_fts5_search(self, state_store):
        state_store.create_content_pack("tp", "Test", "/path")
        state_store.insert_pack_chunk(
            chunk_id="tp:loc:bar",
            pack_id="tp",
            file_path="locations/bar.md",
            section_title="The Bar",
            content="A cyberpunk bar with neon lights and chrome fixtures.",
            chunk_type="location",
            tags=["location"]
        )
        state_store.insert_pack_chunk(
            chunk_id="tp:npc:viktor",
            pack_id="tp",
            file_path="npcs/viktor.md",
            section_title="Viktor",
            content="Viktor is a grizzled fixer who operates from the shadows.",
            chunk_type="npc",
            tags=["npc"]
        )

        # Search for "neon"
        results = state_store.search_chunks_fts("neon")
        assert len(results) >= 1
        assert any(c["id"] == "tp:loc:bar" for c in results)

        # Search for "fixer"
        results = state_store.search_chunks_fts("fixer")
        assert len(results) >= 1
        assert any(c["id"] == "tp:npc:viktor" for c in results)

    def test_fts5_search_with_pack_filter(self, state_store):
        state_store.create_content_pack("p1", "Pack 1", "/p1")
        state_store.create_content_pack("p2", "Pack 2", "/p2")

        state_store.insert_pack_chunk(
            chunk_id="p1:loc:bar", pack_id="p1",
            file_path="bar.md", section_title="Bar",
            content="A neon bar.", chunk_type="location"
        )
        state_store.insert_pack_chunk(
            chunk_id="p2:loc:club", pack_id="p2",
            file_path="club.md", section_title="Club",
            content="A neon club.", chunk_type="location"
        )

        results = state_store.search_chunks_fts("neon", pack_id="p1")
        assert len(results) == 1
        assert results[0]["pack_id"] == "p1"

    def test_fts5_search_with_type_filter(self, state_store):
        state_store.create_content_pack("tp", "Test", "/path")
        state_store.insert_pack_chunk(
            chunk_id="tp:loc:bar", pack_id="tp",
            file_path="bar.md", section_title="Bar",
            content="Dark corner bar.", chunk_type="location"
        )
        state_store.insert_pack_chunk(
            chunk_id="tp:npc:joe", pack_id="tp",
            file_path="joe.md", section_title="Joe",
            content="Dark figure named Joe.", chunk_type="npc"
        )

        results = state_store.search_chunks_fts("dark", chunk_type="npc")
        assert len(results) == 1
        assert results[0]["chunk_type"] == "npc"

    def test_fts5_search_no_results(self, state_store):
        state_store.create_content_pack("tp", "Test", "/path")
        state_store.insert_pack_chunk(
            chunk_id="tp:loc:bar", pack_id="tp",
            file_path="bar.md", section_title="Bar",
            content="A quiet place.", chunk_type="location"
        )
        results = state_store.search_chunks_fts("xyznonexistent")
        assert len(results) == 0


class TestSceneLoreCRUD:
    """Test scene lore cache operations."""

    def test_set_and_get_scene_lore(self, state_store):
        cid = "test_campaign"
        state_store.create_campaign(cid, "Test")
        lore = {
            "atmosphere": "Neon-lit streets, the smell of rain on chrome.",
            "npc_briefings": {"viktor": "A grizzled fixer."}
        }
        state_store.set_scene_lore(
            lore_id=new_id(),
            campaign_id=cid,
            lore=lore,
            scene_id="neon_dragon",
            chunk_ids=["tp:loc:dragon:overview"]
        )
        result = state_store.get_scene_lore(cid, "neon_dragon")
        assert result is not None
        assert result["lore"]["atmosphere"] == lore["atmosphere"]
        assert "tp:loc:dragon:overview" in result["chunk_ids"]

    def test_get_scene_lore_not_found(self, state_store):
        assert state_store.get_scene_lore("nope", "nope") is None

    def test_scene_lore_replaced(self, state_store):
        cid = "test_campaign"
        state_store.create_campaign(cid, "Test")
        lid = new_id()
        state_store.set_scene_lore(lid, cid, {"v": 1}, "s1")
        state_store.set_scene_lore(lid, cid, {"v": 2}, "s1")
        result = state_store.get_scene_lore(cid, "s1")
        assert result["lore"]["v"] == 2
