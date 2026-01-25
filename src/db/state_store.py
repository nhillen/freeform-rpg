import json
import sqlite3
import uuid
from pathlib import Path


class StateStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self):
        schema_path = Path(__file__).with_name("schema.sql")
        sql = schema_path.read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(sql)
            conn.commit()

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


def new_event_id():
    return str(uuid.uuid4())


def json_dumps(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))
