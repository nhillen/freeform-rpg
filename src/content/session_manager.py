"""Session Manager - Manages session lifecycle within campaigns.

A session represents one game night of play. Sessions:
  - Group turns for recap generation
  - Cache materialized lore
  - Track start/end times
"""

import logging
from typing import Optional

from ..db.state_store import StateStore, new_id

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session lifecycle."""

    def __init__(self, state_store: StateStore):
        self.store = state_store

    def start_session(self, campaign_id: str) -> dict:
        """Start a new session for a campaign.

        If an active session already exists, returns it instead of
        creating a new one.
        """
        active = self.store.get_active_session(campaign_id)
        if active:
            logger.info("Resuming active session %s", active["id"])
            return active

        session_id = new_id()
        session = self.store.create_session(session_id, campaign_id)
        logger.info("Started new session %s for campaign %s", session_id, campaign_id)
        return session

    def end_session(
        self,
        session_id: str,
        recap_text: str = ""
    ) -> None:
        """End an active session."""
        self.store.end_session(session_id, recap_text=recap_text)
        logger.info("Ended session %s", session_id)

    def get_active_session(self, campaign_id: str) -> Optional[dict]:
        """Get the active session for a campaign, if any."""
        return self.store.get_active_session(campaign_id)

    def generate_recap(self, campaign_id: str, session_id: str) -> str:
        """Generate a simple recap of the session's turns.

        Returns a text summary of what happened during the session.
        """
        session = self.store.get_session(session_id)
        if not session:
            return ""

        # Get turn range for this session
        start = session.get("turn_range_start")
        end = session.get("turn_range_end")
        if not start or not end:
            # Use all turns since session start
            campaign = self.store.get_campaign(campaign_id)
            if not campaign:
                return ""
            end = campaign.get("current_turn", 0)
            start = max(1, end - 20)  # Last 20 turns max

        events = self.store.get_events_range(campaign_id, start, end)
        if not events:
            return "No events recorded in this session."

        # Build simple recap from event texts
        parts = []
        for event in events:
            text = event.get("final_text", "")
            if text:
                # Take first sentence or first 100 chars
                first_sentence = text.split(".")[0] + "."
                if len(first_sentence) > 120:
                    first_sentence = text[:100] + "..."
                parts.append(first_sentence)

        if not parts:
            return "Session completed."

        return " ".join(parts[:10])  # Cap at 10 turn summaries
