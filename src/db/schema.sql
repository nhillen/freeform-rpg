PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS entities (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  name TEXT NOT NULL,
  attrs_json TEXT NOT NULL,
  tags TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS facts (
  id TEXT PRIMARY KEY,
  subject_id TEXT NOT NULL,
  predicate TEXT NOT NULL,
  object_json TEXT NOT NULL,
  visibility TEXT NOT NULL,
  confidence REAL NOT NULL,
  tags TEXT NOT NULL,
  -- Perception tracking (when/how player learned this)
  discovered_turn INTEGER,
  discovery_method TEXT
);

CREATE TABLE IF NOT EXISTS scene (
  id TEXT PRIMARY KEY,
  location_id TEXT NOT NULL,
  present_entity_ids_json TEXT NOT NULL,
  time_json TEXT NOT NULL,
  constraints_json TEXT NOT NULL,
  -- Perception conditions
  visibility_conditions TEXT DEFAULT 'normal',
  noise_level TEXT DEFAULT 'normal',
  obscured_entities_json TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS threads (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  stakes_json TEXT NOT NULL,
  related_entity_ids_json TEXT NOT NULL,
  tags TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clocks (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  value INTEGER NOT NULL,
  max INTEGER NOT NULL,
  triggers_json TEXT NOT NULL,
  tags TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory (
  owner_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  qty INTEGER NOT NULL,
  flags_json TEXT NOT NULL,
  PRIMARY KEY (owner_id, item_id)
);

CREATE TABLE IF NOT EXISTS relationships (
  a_id TEXT NOT NULL,
  b_id TEXT NOT NULL,
  rel_type TEXT NOT NULL,
  intensity INTEGER NOT NULL,
  notes_json TEXT NOT NULL,
  PRIMARY KEY (a_id, b_id, rel_type)
);

CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  turn_no INTEGER NOT NULL,
  player_input TEXT NOT NULL,
  context_packet_json TEXT NOT NULL,
  pass_outputs_json TEXT NOT NULL,
  engine_events_json TEXT NOT NULL,
  state_diff_json TEXT NOT NULL,
  final_text TEXT NOT NULL,
  prompt_versions_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS summaries (
  id TEXT PRIMARY KEY,
  scope TEXT NOT NULL,
  scope_id TEXT NOT NULL,
  text TEXT NOT NULL,
  turn_no_range TEXT NOT NULL
);

-- Campaign configuration (calibration, game system, metadata)
CREATE TABLE IF NOT EXISTS campaigns (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  -- Calibration settings (tone, themes, risk, boundaries, agency)
  calibration_json TEXT NOT NULL DEFAULT '{}',
  -- Game system configuration (clocks, rolls, consequences)
  system_json TEXT NOT NULL DEFAULT '{}',
  -- Genre rules for context injection
  genre_rules_json TEXT NOT NULL DEFAULT '{}',
  -- Current turn number
  current_turn INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_events_campaign_turn ON events (campaign_id, turn_no);
CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts (subject_id);
CREATE INDEX IF NOT EXISTS idx_facts_visibility ON facts (visibility);
CREATE INDEX IF NOT EXISTS idx_relationships_a ON relationships (a_id);
CREATE INDEX IF NOT EXISTS idx_relationships_b ON relationships (b_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities (type);
