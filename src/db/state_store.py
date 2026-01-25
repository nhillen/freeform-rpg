"""
State Store - SQLite-backed game state management.

Provides CRUD operations for all game state tables with JSON serialization.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class StateStore:
    """
    SQLite-backed state store for game data.

    All JSON fields are automatically serialized/deserialized.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        """Create a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def ensure_schema(self) -> None:
        """Initialize database schema from schema.sql."""
        schema_path = Path(__file__).with_name("schema.sql")
        sql = schema_path.read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(sql)
            conn.commit()

    # =========================================================================
    # Campaign Operations
    # =========================================================================

    def create_campaign(
        self,
        campaign_id: str,
        name: str,
        calibration: Optional[dict] = None,
        system: Optional[dict] = None,
        genre_rules: Optional[dict] = None
    ) -> dict:
        """Create a new campaign."""
        now = datetime.utcnow().isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO campaigns (id, name, created_at, updated_at,
                    calibration_json, system_json, genre_rules_json, current_turn)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    campaign_id,
                    name,
                    now,
                    now,
                    json_dumps(calibration or {}),
                    json_dumps(system or {}),
                    json_dumps(genre_rules or {})
                )
            )
            conn.commit()
        return self.get_campaign(campaign_id)

    def get_campaign(self, campaign_id: str) -> Optional[dict]:
        """Get campaign by ID."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM campaigns WHERE id = ?",
                (campaign_id,)
            ).fetchone()
        if not row:
            return None
        return _parse_campaign_row(row)

    def update_campaign(
        self,
        campaign_id: str,
        calibration: Optional[dict] = None,
        system: Optional[dict] = None,
        genre_rules: Optional[dict] = None,
        current_turn: Optional[int] = None
    ) -> None:
        """Update campaign settings."""
        updates = []
        params = []

        if calibration is not None:
            updates.append("calibration_json = ?")
            params.append(json_dumps(calibration))
        if system is not None:
            updates.append("system_json = ?")
            params.append(json_dumps(system))
        if genre_rules is not None:
            updates.append("genre_rules_json = ?")
            params.append(json_dumps(genre_rules))
        if current_turn is not None:
            updates.append("current_turn = ?")
            params.append(current_turn)

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.utcnow().isoformat())
            params.append(campaign_id)

            with self.connect() as conn:
                conn.execute(
                    f"UPDATE campaigns SET {', '.join(updates)} WHERE id = ?",
                    params
                )
                conn.commit()

    # =========================================================================
    # Entity Operations
    # =========================================================================

    def create_entity(
        self,
        entity_id: str,
        entity_type: str,
        name: str,
        attrs: Optional[dict] = None,
        tags: Optional[list] = None
    ) -> dict:
        """Create a new entity."""
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO entities (id, type, name, attrs_json, tags)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    entity_id,
                    entity_type,
                    name,
                    json_dumps(attrs or {}),
                    json_dumps(tags or [])
                )
            )
            conn.commit()
        return self.get_entity(entity_id)

    def get_entity(self, entity_id: str) -> Optional[dict]:
        """Get entity by ID."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM entities WHERE id = ?",
                (entity_id,)
            ).fetchone()
        if not row:
            return None
        return _parse_entity_row(row)

    def get_entities_by_type(self, entity_type: str) -> list[dict]:
        """Get all entities of a given type."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM entities WHERE type = ?",
                (entity_type,)
            ).fetchall()
        return [_parse_entity_row(row) for row in rows]

    def get_entities_by_ids(self, entity_ids: list[str]) -> list[dict]:
        """Get multiple entities by IDs."""
        if not entity_ids:
            return []
        placeholders = ",".join("?" * len(entity_ids))
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM entities WHERE id IN ({placeholders})",
                entity_ids
            ).fetchall()
        return [_parse_entity_row(row) for row in rows]

    def update_entity(
        self,
        entity_id: str,
        name: Optional[str] = None,
        attrs: Optional[dict] = None,
        tags: Optional[list] = None
    ) -> None:
        """Update an entity."""
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if attrs is not None:
            updates.append("attrs_json = ?")
            params.append(json_dumps(attrs))
        if tags is not None:
            updates.append("tags = ?")
            params.append(json_dumps(tags))

        if updates:
            params.append(entity_id)
            with self.connect() as conn:
                conn.execute(
                    f"UPDATE entities SET {', '.join(updates)} WHERE id = ?",
                    params
                )
                conn.commit()

    def delete_entity(self, entity_id: str) -> None:
        """Delete an entity."""
        with self.connect() as conn:
            conn.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
            conn.commit()

    # =========================================================================
    # Fact Operations
    # =========================================================================

    def create_fact(
        self,
        fact_id: str,
        subject_id: str,
        predicate: str,
        obj: Any,
        visibility: str = "world",
        confidence: float = 1.0,
        tags: Optional[list] = None,
        discovered_turn: Optional[int] = None,
        discovery_method: Optional[str] = None
    ) -> dict:
        """Create a new fact."""
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO facts (id, subject_id, predicate, object_json,
                    visibility, confidence, tags, discovered_turn, discovery_method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact_id,
                    subject_id,
                    predicate,
                    json_dumps(obj),
                    visibility,
                    confidence,
                    json_dumps(tags or []),
                    discovered_turn,
                    discovery_method
                )
            )
            conn.commit()
        return self.get_fact(fact_id)

    def get_fact(self, fact_id: str) -> Optional[dict]:
        """Get fact by ID."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM facts WHERE id = ?",
                (fact_id,)
            ).fetchone()
        if not row:
            return None
        return _parse_fact_row(row)

    def get_facts_for_subject(self, subject_id: str) -> list[dict]:
        """Get all facts about a subject."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM facts WHERE subject_id = ?",
                (subject_id,)
            ).fetchall()
        return [_parse_fact_row(row) for row in rows]

    def get_facts_by_visibility(self, visibility: str) -> list[dict]:
        """Get all facts with a given visibility."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM facts WHERE visibility = ?",
                (visibility,)
            ).fetchall()
        return [_parse_fact_row(row) for row in rows]

    def get_known_facts(self) -> list[dict]:
        """Get all facts known to the player."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM facts WHERE visibility = 'known'"
            ).fetchall()
        return [_parse_fact_row(row) for row in rows]

    def update_fact(
        self,
        fact_id: str,
        obj: Optional[Any] = None,
        visibility: Optional[str] = None,
        confidence: Optional[float] = None,
        discovered_turn: Optional[int] = None,
        discovery_method: Optional[str] = None
    ) -> None:
        """Update a fact."""
        updates = []
        params = []

        if obj is not None:
            updates.append("object_json = ?")
            params.append(json_dumps(obj))
        if visibility is not None:
            updates.append("visibility = ?")
            params.append(visibility)
        if confidence is not None:
            updates.append("confidence = ?")
            params.append(confidence)
        if discovered_turn is not None:
            updates.append("discovered_turn = ?")
            params.append(discovered_turn)
        if discovery_method is not None:
            updates.append("discovery_method = ?")
            params.append(discovery_method)

        if updates:
            params.append(fact_id)
            with self.connect() as conn:
                conn.execute(
                    f"UPDATE facts SET {', '.join(updates)} WHERE id = ?",
                    params
                )
                conn.commit()

    def mark_fact_discovered(
        self,
        fact_id: str,
        turn_no: int,
        method: str
    ) -> None:
        """Mark a fact as discovered by the player."""
        self.update_fact(
            fact_id,
            visibility="known",
            discovered_turn=turn_no,
            discovery_method=method
        )

    # =========================================================================
    # Clock Operations
    # =========================================================================

    def create_clock(
        self,
        clock_id: str,
        name: str,
        value: int,
        max_value: int,
        triggers: Optional[dict] = None,
        tags: Optional[list] = None
    ) -> dict:
        """Create a new clock."""
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO clocks (id, name, value, max, triggers_json, tags)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    clock_id,
                    name,
                    value,
                    max_value,
                    json_dumps(triggers or {}),
                    json_dumps(tags or [])
                )
            )
            conn.commit()
        return self.get_clock(clock_id)

    def get_clock(self, clock_id: str) -> Optional[dict]:
        """Get clock by ID."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM clocks WHERE id = ?",
                (clock_id,)
            ).fetchone()
        if not row:
            return None
        return _parse_clock_row(row)

    def get_clock_by_name(self, name: str) -> Optional[dict]:
        """Get clock by name (case-insensitive)."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM clocks WHERE LOWER(name) = LOWER(?)",
                (name,)
            ).fetchone()
        if not row:
            return None
        return _parse_clock_row(row)

    def get_all_clocks(self) -> list[dict]:
        """Get all clocks."""
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM clocks").fetchall()
        return [_parse_clock_row(row) for row in rows]

    def update_clock(
        self,
        clock_id: str,
        value: Optional[int] = None,
        max_value: Optional[int] = None,
        triggers: Optional[dict] = None
    ) -> list[str]:
        """
        Update a clock and return any triggered events.

        Returns list of trigger messages that fired.
        """
        clock = self.get_clock(clock_id)
        # Fall back to name lookup if ID not found
        if not clock:
            clock = self.get_clock_by_name(clock_id)
            if clock:
                clock_id = clock["id"]
        if not clock:
            raise ValueError(f"Clock not found: {clock_id}")

        old_value = clock["value"]
        new_value = value if value is not None else old_value

        updates = []
        params = []

        if value is not None:
            # Clamp to valid range
            new_value = max(0, min(value, clock["max"]))
            updates.append("value = ?")
            params.append(new_value)
        if max_value is not None:
            updates.append("max = ?")
            params.append(max_value)
        if triggers is not None:
            updates.append("triggers_json = ?")
            params.append(json_dumps(triggers))

        if updates:
            params.append(clock_id)
            with self.connect() as conn:
                conn.execute(
                    f"UPDATE clocks SET {', '.join(updates)} WHERE id = ?",
                    params
                )
                conn.commit()

        # Check for triggered events
        triggered = []
        clock_triggers = triggers if triggers is not None else clock["triggers"]
        for threshold_str, message in clock_triggers.items():
            threshold = int(threshold_str)
            # Trigger if we crossed this threshold
            if old_value < threshold <= new_value:
                triggered.append(message)

        return triggered

    def adjust_clock(self, clock_id: str, delta: int) -> list[str]:
        """Adjust clock value by delta. Returns triggered events."""
        clock = self.get_clock(clock_id)
        # Fall back to name lookup if ID not found
        if not clock:
            clock = self.get_clock_by_name(clock_id)
            if clock:
                clock_id = clock["id"]
        if not clock:
            raise ValueError(f"Clock not found: {clock_id}")
        return self.update_clock(clock_id, value=clock["value"] + delta)

    # =========================================================================
    # Scene Operations
    # =========================================================================

    def get_scene(self, scene_id: str = "current") -> Optional[dict]:
        """Get scene by ID (default: 'current')."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM scene WHERE id = ?",
                (scene_id,)
            ).fetchone()
        if not row:
            return None
        return _parse_scene_row(row)

    def set_scene(
        self,
        location_id: str,
        present_entity_ids: list[str],
        time: Optional[dict] = None,
        constraints: Optional[dict] = None,
        visibility_conditions: str = "normal",
        noise_level: str = "normal",
        obscured_entities: Optional[list[str]] = None,
        scene_id: str = "current"
    ) -> dict:
        """Set or update the current scene."""
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO scene (id, location_id, present_entity_ids_json,
                    time_json, constraints_json, visibility_conditions, noise_level,
                    obscured_entities_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scene_id,
                    location_id,
                    json_dumps(present_entity_ids),
                    json_dumps(time or {}),
                    json_dumps(constraints or {}),
                    visibility_conditions,
                    noise_level,
                    json_dumps(obscured_entities or [])
                )
            )
            conn.commit()
        return self.get_scene(scene_id)

    def update_scene_entities(
        self,
        present_entity_ids: list[str],
        scene_id: str = "current"
    ) -> None:
        """Update which entities are present in the scene."""
        with self.connect() as conn:
            conn.execute(
                "UPDATE scene SET present_entity_ids_json = ? WHERE id = ?",
                (json_dumps(present_entity_ids), scene_id)
            )
            conn.commit()

    # =========================================================================
    # Thread Operations
    # =========================================================================

    def create_thread(
        self,
        thread_id: str,
        title: str,
        status: str = "active",
        stakes: Optional[dict] = None,
        related_entity_ids: Optional[list[str]] = None,
        tags: Optional[list] = None
    ) -> dict:
        """Create a new thread."""
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO threads (id, title, status, stakes_json,
                    related_entity_ids_json, tags)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    thread_id,
                    title,
                    status,
                    json_dumps(stakes or {}),
                    json_dumps(related_entity_ids or []),
                    json_dumps(tags or [])
                )
            )
            conn.commit()
        return self.get_thread(thread_id)

    def get_thread(self, thread_id: str) -> Optional[dict]:
        """Get thread by ID."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM threads WHERE id = ?",
                (thread_id,)
            ).fetchone()
        if not row:
            return None
        return _parse_thread_row(row)

    def get_active_threads(self) -> list[dict]:
        """Get all active threads."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM threads WHERE status = 'active'"
            ).fetchall()
        return [_parse_thread_row(row) for row in rows]

    def update_thread(
        self,
        thread_id: str,
        title: Optional[str] = None,
        status: Optional[str] = None,
        stakes: Optional[dict] = None
    ) -> None:
        """Update a thread."""
        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if stakes is not None:
            updates.append("stakes_json = ?")
            params.append(json_dumps(stakes))

        if updates:
            params.append(thread_id)
            with self.connect() as conn:
                conn.execute(
                    f"UPDATE threads SET {', '.join(updates)} WHERE id = ?",
                    params
                )
                conn.commit()

    # =========================================================================
    # Inventory Operations
    # =========================================================================

    def add_inventory(
        self,
        owner_id: str,
        item_id: str,
        qty: int = 1,
        flags: Optional[dict] = None
    ) -> dict:
        """Add or update inventory item."""
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO inventory (owner_id, item_id, qty, flags_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(owner_id, item_id) DO UPDATE SET
                    qty = qty + excluded.qty,
                    flags_json = excluded.flags_json
                """,
                (owner_id, item_id, qty, json_dumps(flags or {}))
            )
            conn.commit()
        return self.get_inventory_item(owner_id, item_id)

    def get_inventory_item(self, owner_id: str, item_id: str) -> Optional[dict]:
        """Get a specific inventory item."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM inventory WHERE owner_id = ? AND item_id = ?",
                (owner_id, item_id)
            ).fetchone()
        if not row:
            return None
        return _parse_inventory_row(row)

    def get_inventory(self, owner_id: str) -> list[dict]:
        """Get all inventory for an owner."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM inventory WHERE owner_id = ?",
                (owner_id,)
            ).fetchall()
        return [_parse_inventory_row(row) for row in rows]

    def remove_inventory(self, owner_id: str, item_id: str, qty: int = 1) -> bool:
        """Remove quantity from inventory. Returns True if item remains."""
        item = self.get_inventory_item(owner_id, item_id)
        if not item:
            return False

        new_qty = item["qty"] - qty
        if new_qty <= 0:
            with self.connect() as conn:
                conn.execute(
                    "DELETE FROM inventory WHERE owner_id = ? AND item_id = ?",
                    (owner_id, item_id)
                )
                conn.commit()
            return False
        else:
            with self.connect() as conn:
                conn.execute(
                    "UPDATE inventory SET qty = ? WHERE owner_id = ? AND item_id = ?",
                    (new_qty, owner_id, item_id)
                )
                conn.commit()
            return True

    # =========================================================================
    # Relationship Operations
    # =========================================================================

    def create_relationship(
        self,
        a_id: str,
        b_id: str,
        rel_type: str,
        intensity: int = 0,
        notes: Optional[dict] = None
    ) -> dict:
        """Create or update a relationship."""
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO relationships (a_id, b_id, rel_type, intensity, notes_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(a_id, b_id, rel_type) DO UPDATE SET
                    intensity = excluded.intensity,
                    notes_json = excluded.notes_json
                """,
                (a_id, b_id, rel_type, intensity, json_dumps(notes or {}))
            )
            conn.commit()
        return self.get_relationship(a_id, b_id, rel_type)

    def get_relationship(
        self,
        a_id: str,
        b_id: str,
        rel_type: str
    ) -> Optional[dict]:
        """Get a specific relationship."""
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM relationships
                WHERE a_id = ? AND b_id = ? AND rel_type = ?
                """,
                (a_id, b_id, rel_type)
            ).fetchone()
        if not row:
            return None
        return _parse_relationship_row(row)

    def get_relationships_for_entity(self, entity_id: str) -> list[dict]:
        """Get all relationships involving an entity."""
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM relationships
                WHERE a_id = ? OR b_id = ?
                """,
                (entity_id, entity_id)
            ).fetchall()
        return [_parse_relationship_row(row) for row in rows]

    def update_relationship_intensity(
        self,
        a_id: str,
        b_id: str,
        rel_type: str,
        delta: int
    ) -> Optional[dict]:
        """Adjust relationship intensity by delta."""
        rel = self.get_relationship(a_id, b_id, rel_type)
        if not rel:
            return None

        new_intensity = rel["intensity"] + delta
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE relationships SET intensity = ?
                WHERE a_id = ? AND b_id = ? AND rel_type = ?
                """,
                (new_intensity, a_id, b_id, rel_type)
            )
            conn.commit()
        return self.get_relationship(a_id, b_id, rel_type)

    # =========================================================================
    # State Diff Application
    # =========================================================================

    def apply_state_diff(self, diff: dict, turn_no: int) -> list[str]:
        """
        Apply a state diff to the database.

        Returns list of triggered events/messages.
        """
        triggered = []

        # Apply clock changes
        for clock_change in diff.get("clocks", []):
            clock_id = clock_change.get("id")
            if clock_change.get("delta"):
                triggers = self.adjust_clock(clock_id, clock_change["delta"])
                triggered.extend(triggers)
            elif "value" in clock_change:
                triggers = self.update_clock(clock_id, value=clock_change["value"])
                triggered.extend(triggers)

        # Add new facts
        for fact in diff.get("facts_add", []):
            self.create_fact(
                fact_id=fact.get("id", new_id()),
                subject_id=fact["subject_id"],
                predicate=fact["predicate"],
                obj=fact.get("object", {}),
                visibility=fact.get("visibility", "world"),
                tags=fact.get("tags", []),
                discovered_turn=turn_no if fact.get("visibility") == "known" else None,
                discovery_method=fact.get("discovery_method")
            )

        # Update existing facts
        for fact in diff.get("facts_update", []):
            self.update_fact(
                fact["id"],
                obj=fact.get("object"),
                visibility=fact.get("visibility"),
                discovered_turn=turn_no if fact.get("visibility") == "known" else None,
                discovery_method=fact.get("discovery_method")
            )

        # Apply inventory changes
        for inv_change in diff.get("inventory_changes", []):
            delta = inv_change.get("delta", 0)
            if delta > 0:
                self.add_inventory(
                    inv_change["owner_id"],
                    inv_change["item_id"],
                    delta
                )
            elif delta < 0:
                self.remove_inventory(
                    inv_change["owner_id"],
                    inv_change["item_id"],
                    abs(delta)
                )

        # Update scene
        scene_update = diff.get("scene_update", {})
        if scene_update:
            current_scene = self.get_scene()
            self.set_scene(
                location_id=scene_update.get("location_id", current_scene["location_id"] if current_scene else "unknown"),
                present_entity_ids=scene_update.get("present_entity_ids", current_scene["present_entity_ids"] if current_scene else [])
            )

        # Update threads
        for thread in diff.get("threads_update", []):
            self.update_thread(
                thread["id"],
                status=thread.get("status"),
                stakes=thread.get("stakes")
            )

        return triggered

    def get_next_turn_no(self, campaign_id):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(turn_no), 0) AS max_turn FROM events WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
        return int(row["max_turn"]) + 1

    def append_event(self, event_record):
        required = [
            "id",
            "campaign_id",
            "turn_no",
            "player_input",
            "context_packet_json",
            "pass_outputs_json",
            "engine_events_json",
            "state_diff_json",
            "final_text",
            "prompt_versions_json",
        ]
        missing = [key for key in required if key not in event_record]
        if missing:
            raise ValueError(f"Missing event fields: {', '.join(missing)}")

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO events (
                  id, campaign_id, turn_no, player_input,
                  context_packet_json, pass_outputs_json, engine_events_json,
                  state_diff_json, final_text, prompt_versions_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_record["id"],
                    event_record["campaign_id"],
                    event_record["turn_no"],
                    event_record["player_input"],
                    event_record["context_packet_json"],
                    event_record["pass_outputs_json"],
                    event_record["engine_events_json"],
                    event_record["state_diff_json"],
                    event_record["final_text"],
                    event_record["prompt_versions_json"],
                ),
            )
            conn.commit()

    def get_event(self, campaign_id, turn_no):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM events WHERE campaign_id = ? AND turn_no = ?",
                (campaign_id, turn_no),
            ).fetchone()
        return dict(row) if row else None

    def get_events_range(self, campaign_id, start_turn, end_turn):
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM events
                WHERE campaign_id = ? AND turn_no BETWEEN ? AND ?
                ORDER BY turn_no ASC
                """,
                (campaign_id, start_turn, end_turn),
            ).fetchall()
        return [dict(row) for row in rows]


# =============================================================================
# Helper Functions
# =============================================================================

def new_id() -> str:
    """Generate a new UUID."""
    return str(uuid.uuid4())


def new_event_id() -> str:
    """Generate a new event UUID (alias for new_id)."""
    return new_id()


def json_dumps(value: Any) -> str:
    """Serialize value to JSON string."""
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def json_loads(value: str) -> Any:
    """Deserialize JSON string to value."""
    return json.loads(value) if value else None


def _parse_campaign_row(row: sqlite3.Row) -> dict:
    """Parse a campaign row to dict."""
    return {
        "id": row["id"],
        "name": row["name"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "calibration": json_loads(row["calibration_json"]),
        "system": json_loads(row["system_json"]),
        "genre_rules": json_loads(row["genre_rules_json"]),
        "current_turn": row["current_turn"]
    }


def _parse_entity_row(row: sqlite3.Row) -> dict:
    """Parse an entity row to dict."""
    return {
        "id": row["id"],
        "type": row["type"],
        "name": row["name"],
        "attrs": json_loads(row["attrs_json"]),
        "tags": json_loads(row["tags"])
    }


def _parse_fact_row(row: sqlite3.Row) -> dict:
    """Parse a fact row to dict."""
    return {
        "id": row["id"],
        "subject_id": row["subject_id"],
        "predicate": row["predicate"],
        "object": json_loads(row["object_json"]),
        "visibility": row["visibility"],
        "confidence": row["confidence"],
        "tags": json_loads(row["tags"]),
        "discovered_turn": row["discovered_turn"],
        "discovery_method": row["discovery_method"]
    }


def _parse_clock_row(row: sqlite3.Row) -> dict:
    """Parse a clock row to dict."""
    return {
        "id": row["id"],
        "name": row["name"],
        "value": row["value"],
        "max": row["max"],
        "triggers": json_loads(row["triggers_json"]),
        "tags": json_loads(row["tags"])
    }


def _parse_scene_row(row: sqlite3.Row) -> dict:
    """Parse a scene row to dict."""
    return {
        "id": row["id"],
        "location_id": row["location_id"],
        "present_entity_ids": json_loads(row["present_entity_ids_json"]),
        "time": json_loads(row["time_json"]),
        "constraints": json_loads(row["constraints_json"]),
        "visibility_conditions": row["visibility_conditions"],
        "noise_level": row["noise_level"],
        "obscured_entities": json_loads(row["obscured_entities_json"])
    }


def _parse_thread_row(row: sqlite3.Row) -> dict:
    """Parse a thread row to dict."""
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "stakes": json_loads(row["stakes_json"]),
        "related_entity_ids": json_loads(row["related_entity_ids_json"]),
        "tags": json_loads(row["tags"])
    }


def _parse_inventory_row(row: sqlite3.Row) -> dict:
    """Parse an inventory row to dict."""
    return {
        "owner_id": row["owner_id"],
        "item_id": row["item_id"],
        "qty": row["qty"],
        "flags": json_loads(row["flags_json"])
    }


def _parse_relationship_row(row: sqlite3.Row) -> dict:
    """Parse a relationship row to dict."""
    return {
        "a_id": row["a_id"],
        "b_id": row["b_id"],
        "rel_type": row["rel_type"],
        "intensity": row["intensity"],
        "notes": json_loads(row["notes_json"])
    }
