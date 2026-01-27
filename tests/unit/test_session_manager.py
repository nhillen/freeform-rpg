"""
Tests for the Session Manager.

Tests session lifecycle: create, resume, end, recap generation.
"""

import pytest
from src.content.session_manager import SessionManager
from tests.fixtures.state import setup_minimal_game_state


class TestSessionLifecycle:
    """Tests for session start/end lifecycle."""

    def test_start_session_creates_new(self, state_store):
        """Starting a session creates a new session record."""
        setup_minimal_game_state(state_store)
        mgr = SessionManager(state_store)

        session = mgr.start_session("test_campaign")

        assert session is not None
        assert session["campaign_id"] == "test_campaign"
        assert session["ended_at"] is None

    def test_start_session_resumes_active(self, state_store):
        """Starting a session when one is active returns the active one."""
        setup_minimal_game_state(state_store)
        mgr = SessionManager(state_store)

        first = mgr.start_session("test_campaign")
        second = mgr.start_session("test_campaign")

        assert first["id"] == second["id"]

    def test_end_session(self, state_store):
        """Ending a session marks it as ended."""
        setup_minimal_game_state(state_store)
        mgr = SessionManager(state_store)

        session = mgr.start_session("test_campaign")
        mgr.end_session(session["id"], recap_text="Test recap.")

        ended = state_store.get_session(session["id"])
        assert ended["ended_at"] is not None
        assert ended["recap_text"] == "Test recap."

    def test_no_active_after_end(self, state_store):
        """No active session after ending it."""
        setup_minimal_game_state(state_store)
        mgr = SessionManager(state_store)

        session = mgr.start_session("test_campaign")
        mgr.end_session(session["id"])

        active = mgr.get_active_session("test_campaign")
        assert active is None

    def test_get_active_session_none_initially(self, state_store):
        """No active session before one is started."""
        setup_minimal_game_state(state_store)
        mgr = SessionManager(state_store)

        active = mgr.get_active_session("test_campaign")
        assert active is None

    def test_start_new_session_after_end(self, state_store):
        """Can start a new session after ending the previous one."""
        setup_minimal_game_state(state_store)
        mgr = SessionManager(state_store)

        first = mgr.start_session("test_campaign")
        mgr.end_session(first["id"])
        second = mgr.start_session("test_campaign")

        assert second["id"] != first["id"]


class TestSessionRecap:
    """Tests for session recap generation."""

    def test_recap_no_events(self, state_store):
        """Recap with no events returns placeholder text."""
        setup_minimal_game_state(state_store)
        mgr = SessionManager(state_store)

        session = mgr.start_session("test_campaign")
        recap = mgr.generate_recap("test_campaign", session["id"])

        # No events logged yet, should return the no-events message
        assert recap in ("No events recorded in this session.", "Session completed.", "")

    def test_recap_nonexistent_session(self, state_store):
        """Recap for nonexistent session returns empty string."""
        setup_minimal_game_state(state_store)
        mgr = SessionManager(state_store)

        recap = mgr.generate_recap("test_campaign", "nonexistent")
        assert recap == ""

    def test_recap_with_events(self, state_store):
        """Recap includes text from logged events."""
        setup_minimal_game_state(state_store)
        mgr = SessionManager(state_store)

        # Set campaign turn counter
        state_store.update_campaign("test_campaign", current_turn=2)

        # Log some events
        from src.db.state_store import json_dumps, new_event_id
        for turn_no in [1, 2]:
            state_store.append_event({
                "id": new_event_id(),
                "campaign_id": "test_campaign",
                "turn_no": turn_no,
                "player_input": f"action {turn_no}",
                "context_packet_json": json_dumps({}),
                "pass_outputs_json": json_dumps({}),
                "engine_events_json": json_dumps([]),
                "state_diff_json": json_dumps({}),
                "final_text": f"Turn {turn_no} happened. Something occurred.",
                "prompt_versions_json": json_dumps({}),
            })

        session = mgr.start_session("test_campaign")
        recap = mgr.generate_recap("test_campaign", session["id"])

        assert len(recap) > 0
        assert "Turn 1 happened" in recap or "Turn 2 happened" in recap
