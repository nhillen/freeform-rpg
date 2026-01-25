"""
Evaluation Module - Quality metrics, feedback capture, and A/B testing.

Supports:
- Automatic quality metric logging per turn
- Player feedback capture (ratings, flags, comments)
- Self-evaluation prompts for LLM critique
- A/B testing replay with prompt variants
- Evaluation report generation
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import json

from ..db.state_store import StateStore, new_id, json_dumps


class FeedbackType(Enum):
    """Types of player feedback."""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    FLAG_ISSUE = "flag_issue"
    COMMENT = "comment"
    RATING = "rating"  # 1-5 scale


@dataclass
class QualityMetrics:
    """Automatic quality metrics captured per turn."""
    # Timing
    total_latency_ms: float = 0
    interpreter_latency_ms: float = 0
    validator_latency_ms: float = 0
    planner_latency_ms: float = 0
    resolver_latency_ms: float = 0
    narrator_latency_ms: float = 0

    # Action recognition
    actions_proposed: int = 0
    actions_allowed: int = 0
    actions_blocked: int = 0
    clarification_needed: bool = False

    # State coherence
    entities_in_context: int = 0
    facts_in_context: int = 0
    clock_triggers_fired: list = field(default_factory=list)

    # Output quality signals
    narrative_length: int = 0
    has_dialogue: bool = False
    has_description: bool = False
    has_consequence: bool = False

    # Roll outcomes (if any)
    roll_count: int = 0
    roll_outcomes: list = field(default_factory=list)  # ["success", "failure", etc.]

    def to_dict(self) -> dict:
        return {
            "timing": {
                "total_ms": self.total_latency_ms,
                "interpreter_ms": self.interpreter_latency_ms,
                "validator_ms": self.validator_latency_ms,
                "planner_ms": self.planner_latency_ms,
                "resolver_ms": self.resolver_latency_ms,
                "narrator_ms": self.narrator_latency_ms,
            },
            "actions": {
                "proposed": self.actions_proposed,
                "allowed": self.actions_allowed,
                "blocked": self.actions_blocked,
                "clarification_needed": self.clarification_needed,
            },
            "context": {
                "entities": self.entities_in_context,
                "facts": self.facts_in_context,
                "triggers_fired": self.clock_triggers_fired,
            },
            "output": {
                "narrative_length": self.narrative_length,
                "has_dialogue": self.has_dialogue,
                "has_description": self.has_description,
                "has_consequence": self.has_consequence,
            },
            "rolls": {
                "count": self.roll_count,
                "outcomes": self.roll_outcomes,
            }
        }


@dataclass
class PlayerFeedback:
    """Player feedback on a turn."""
    turn_no: int
    feedback_type: FeedbackType
    value: Optional[str] = None  # Rating value, comment text, or flag type
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "turn_no": self.turn_no,
            "type": self.feedback_type.value,
            "value": self.value,
            "timestamp": self.timestamp,
        }


@dataclass
class SelfEvaluation:
    """LLM self-evaluation of a turn."""
    turn_no: int
    evaluations: dict = field(default_factory=dict)
    # Example evaluations:
    # - tone_match: 0-10 how well output matched calibration tone
    # - intent_capture: 0-10 how well we understood player intent
    # - narrative_quality: 0-10 prose quality
    # - state_accuracy: 0-10 consistency with game state
    # - pacing: 0-10 appropriate beat/tension handling

    def to_dict(self) -> dict:
        return {
            "turn_no": self.turn_no,
            "evaluations": self.evaluations,
        }


# Self-evaluation prompt templates
SELF_EVAL_PROMPTS = {
    "tone_match": """
Given the calibration settings and the narrative output, rate how well the tone matches (0-10):

Calibration tone settings:
{{calibration_tone}}

Narrative output:
{{narrative}}

Respond with just a number 0-10 and a brief reason.
""",

    "intent_capture": """
Rate how well we understood and responded to the player's intent (0-10):

Player input: {{player_input}}
Interpreted intent: {{interpreted_intent}}
Actions taken: {{actions}}
Final narrative: {{narrative}}

Respond with just a number 0-10 and a brief reason.
""",

    "narrative_quality": """
Rate the narrative quality (0-10) considering:
- Prose style and readability
- Sensory details and atmosphere
- Character voice consistency
- Appropriate length

Narrative:
{{narrative}}

Genre: {{genre}}

Respond with just a number 0-10 and a brief reason.
""",

    "state_accuracy": """
Check if the narrative accurately reflects the game state (0-10):

Game state summary:
- Location: {{location}}
- Present entities: {{present_entities}}
- Recent facts: {{recent_facts}}
- Clock values: {{clocks}}

Narrative claims:
{{narrative}}

Flag any inconsistencies. Respond with 0-10 and explanation.
""",
}


class EvaluationTracker:
    """Tracks evaluation data for a campaign."""

    def __init__(self, state_store: StateStore):
        self.store = state_store
        self._ensure_eval_tables()

    def _ensure_eval_tables(self):
        """Ensure evaluation tables exist."""
        conn = self.store.connect()
        cursor = conn.cursor()

        # Metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eval_metrics (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                turn_no INTEGER NOT NULL,
                metrics_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Feedback table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eval_feedback (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                turn_no INTEGER NOT NULL,
                feedback_type TEXT NOT NULL,
                value TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Self-evaluation table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eval_self (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                turn_no INTEGER NOT NULL,
                eval_type TEXT NOT NULL,
                score REAL,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # A/B test results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eval_ab_tests (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                turn_no INTEGER NOT NULL,
                variant_a TEXT NOT NULL,
                variant_b TEXT NOT NULL,
                output_a TEXT,
                output_b TEXT,
                winner TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def log_metrics(
        self,
        campaign_id: str,
        turn_no: int,
        metrics: QualityMetrics
    ) -> None:
        """Log automatic quality metrics for a turn."""
        conn = self.store.connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO eval_metrics (id, campaign_id, turn_no, metrics_json)
            VALUES (?, ?, ?, ?)
        """, (new_id(), campaign_id, turn_no, json_dumps(metrics.to_dict())))

        conn.commit()
        conn.close()

    def log_feedback(
        self,
        campaign_id: str,
        feedback: PlayerFeedback
    ) -> None:
        """Log player feedback."""
        conn = self.store.connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO eval_feedback (id, campaign_id, turn_no, feedback_type, value)
            VALUES (?, ?, ?, ?, ?)
        """, (
            new_id(),
            campaign_id,
            feedback.turn_no,
            feedback.feedback_type.value,
            feedback.value
        ))

        conn.commit()
        conn.close()

    def log_self_eval(
        self,
        campaign_id: str,
        turn_no: int,
        eval_type: str,
        score: float,
        reason: str
    ) -> None:
        """Log LLM self-evaluation."""
        conn = self.store.connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO eval_self (id, campaign_id, turn_no, eval_type, score, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (new_id(), campaign_id, turn_no, eval_type, score, reason))

        conn.commit()
        conn.close()

    def log_ab_test(
        self,
        campaign_id: str,
        turn_no: int,
        variant_a: str,
        variant_b: str,
        output_a: str,
        output_b: str,
        winner: Optional[str] = None,
        notes: Optional[str] = None
    ) -> None:
        """Log A/B test result."""
        conn = self.store.connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO eval_ab_tests
            (id, campaign_id, turn_no, variant_a, variant_b, output_a, output_b, winner, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            new_id(), campaign_id, turn_no,
            variant_a, variant_b, output_a, output_b, winner, notes
        ))

        conn.commit()
        conn.close()

    def get_metrics_summary(self, campaign_id: str) -> dict:
        """Get summary of metrics for a campaign."""
        conn = self.store.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT metrics_json FROM eval_metrics
            WHERE campaign_id = ?
            ORDER BY turn_no
        """, (campaign_id,))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return {"turns": 0, "summary": {}}

        metrics_list = [json.loads(row[0]) for row in rows]

        # Aggregate metrics
        total_turns = len(metrics_list)
        avg_latency = sum(m["timing"]["total_ms"] for m in metrics_list) / total_turns
        total_clarifications = sum(1 for m in metrics_list if m["actions"]["clarification_needed"])
        avg_narrative_length = sum(m["output"]["narrative_length"] for m in metrics_list) / total_turns

        roll_outcomes = []
        for m in metrics_list:
            roll_outcomes.extend(m["rolls"]["outcomes"])

        return {
            "turns": total_turns,
            "summary": {
                "avg_latency_ms": round(avg_latency, 2),
                "clarification_rate": round(total_clarifications / total_turns, 2),
                "avg_narrative_length": round(avg_narrative_length, 0),
                "roll_distribution": _count_outcomes(roll_outcomes),
            }
        }

    def get_feedback_summary(self, campaign_id: str) -> dict:
        """Get summary of player feedback for a campaign."""
        conn = self.store.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT feedback_type, value, turn_no FROM eval_feedback
            WHERE campaign_id = ?
        """, (campaign_id,))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return {"total": 0, "by_type": {}}

        by_type = {}
        for feedback_type, value, turn_no in rows:
            if feedback_type not in by_type:
                by_type[feedback_type] = []
            by_type[feedback_type].append({"turn": turn_no, "value": value})

        # Calculate sentiment
        thumbs_up = len(by_type.get("thumbs_up", []))
        thumbs_down = len(by_type.get("thumbs_down", []))
        total_votes = thumbs_up + thumbs_down

        return {
            "total": len(rows),
            "by_type": by_type,
            "sentiment": {
                "positive": thumbs_up,
                "negative": thumbs_down,
                "ratio": round(thumbs_up / total_votes, 2) if total_votes > 0 else None
            }
        }

    def get_problematic_turns(self, campaign_id: str) -> list:
        """Get turns that had issues (flags, low ratings, clarifications)."""
        conn = self.store.connect()
        cursor = conn.cursor()

        # Get flagged turns
        cursor.execute("""
            SELECT turn_no, value FROM eval_feedback
            WHERE campaign_id = ? AND feedback_type = 'flag_issue'
        """, (campaign_id,))
        flagged = [(row[0], row[1]) for row in cursor.fetchall()]

        # Get thumbs down turns
        cursor.execute("""
            SELECT turn_no FROM eval_feedback
            WHERE campaign_id = ? AND feedback_type = 'thumbs_down'
        """, (campaign_id,))
        thumbs_down = [row[0] for row in cursor.fetchall()]

        # Get clarification turns
        cursor.execute("""
            SELECT turn_no, metrics_json FROM eval_metrics
            WHERE campaign_id = ?
        """, (campaign_id,))

        clarification_turns = []
        for turn_no, metrics_json in cursor.fetchall():
            metrics = json.loads(metrics_json)
            if metrics["actions"]["clarification_needed"]:
                clarification_turns.append(turn_no)

        conn.close()

        # Compile problem turns
        problems = []
        all_problem_turns = set(
            [t for t, _ in flagged] +
            thumbs_down +
            clarification_turns
        )

        for turn_no in sorted(all_problem_turns):
            issue = {
                "turn_no": turn_no,
                "issues": []
            }
            for t, flag in flagged:
                if t == turn_no:
                    issue["issues"].append(f"flagged: {flag}")
            if turn_no in thumbs_down:
                issue["issues"].append("thumbs_down")
            if turn_no in clarification_turns:
                issue["issues"].append("needed_clarification")
            problems.append(issue)

        return problems


def _count_outcomes(outcomes: list) -> dict:
    """Count roll outcome frequencies."""
    counts = {}
    for o in outcomes:
        counts[o] = counts.get(o, 0) + 1
    return counts


def extract_metrics_from_turn(
    context_packet: dict,
    interpreter_output: dict,
    validator_output: dict,
    resolver_output: dict,
    narrator_output: dict,
    timings: Optional[dict] = None
) -> QualityMetrics:
    """Extract quality metrics from turn data."""
    timings = timings or {}

    metrics = QualityMetrics(
        # Timing
        total_latency_ms=timings.get("total", 0),
        interpreter_latency_ms=timings.get("interpreter", 0),
        validator_latency_ms=timings.get("validator", 0),
        planner_latency_ms=timings.get("planner", 0),
        resolver_latency_ms=timings.get("resolver", 0),
        narrator_latency_ms=timings.get("narrator", 0),

        # Actions
        actions_proposed=len(interpreter_output.get("proposed_actions", [])),
        actions_allowed=len(validator_output.get("allowed_actions", [])),
        actions_blocked=len(validator_output.get("blocked_actions", [])),
        clarification_needed=validator_output.get("clarification_needed", False),

        # Context
        entities_in_context=len(context_packet.get("entities", [])),
        facts_in_context=len(context_packet.get("facts", [])),

        # Rolls
        roll_count=len(resolver_output.get("rolls", [])),
        roll_outcomes=[r.get("outcome") for r in resolver_output.get("rolls", [])],
    )

    # Analyze narrative
    narrative = narrator_output.get("final_text", "")
    metrics.narrative_length = len(narrative)
    metrics.has_dialogue = '"' in narrative or "'" in narrative
    metrics.has_description = any(word in narrative.lower() for word in
        ["see", "hear", "smell", "feel", "notice", "appear"])
    metrics.has_consequence = any(word in narrative.lower() for word in
        ["but", "however", "unfortunately", "consequence", "result"])

    return metrics
