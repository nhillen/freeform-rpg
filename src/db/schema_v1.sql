-- Schema v1: Content packs, sessions, lore retrieval
-- Applied idempotently after schema.sql (v0)

-- Sessions table: groups turns within a game night
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  turn_range_start INTEGER,
  turn_range_end INTEGER,
  recap_text TEXT DEFAULT '',
  lore_cache_json TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_sessions_campaign ON sessions (campaign_id);

-- Content packs: registered world sourcebooks
CREATE TABLE IF NOT EXISTS content_packs (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT DEFAULT '',
  version TEXT DEFAULT '1.0',
  layer TEXT NOT NULL DEFAULT 'adventure',
  path TEXT NOT NULL,
  installed_at TEXT NOT NULL,
  chunk_count INTEGER DEFAULT 0,
  metadata_json TEXT DEFAULT '{}'
);

-- Pack chunks: indexed content segments
CREATE TABLE IF NOT EXISTS pack_chunks (
  id TEXT PRIMARY KEY,
  pack_id TEXT NOT NULL,
  file_path TEXT NOT NULL,
  section_title TEXT NOT NULL,
  content TEXT NOT NULL,
  chunk_type TEXT NOT NULL DEFAULT 'general',
  entity_refs_json TEXT DEFAULT '[]',
  tags_json TEXT DEFAULT '[]',
  metadata_json TEXT DEFAULT '{}',
  token_estimate INTEGER DEFAULT 0,
  FOREIGN KEY (pack_id) REFERENCES content_packs(id)
);

CREATE INDEX IF NOT EXISTS idx_pack_chunks_pack ON pack_chunks (pack_id);
CREATE INDEX IF NOT EXISTS idx_pack_chunks_type ON pack_chunks (chunk_type);

-- FTS5 virtual table for full-text search on pack chunks
CREATE VIRTUAL TABLE IF NOT EXISTS pack_chunks_fts USING fts5(
  chunk_id,
  section_title,
  body,
  chunk_type,
  tags,
  tokenize='porter'
);

-- Scene lore cache: materialized lore for current scene
CREATE TABLE IF NOT EXISTS scene_lore (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  scene_id TEXT NOT NULL DEFAULT 'current',
  session_id TEXT,
  lore_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  chunk_ids_json TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_scene_lore_campaign_scene ON scene_lore (campaign_id, scene_id);
