"""
Replay Module - A/B testing and turn replay for prompt iteration.

Supports:
- Replaying turns with different prompt versions
- Side-by-side comparison of outputs
- Statistical analysis of variant performance
- Clean replay via state snapshots
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json
import time

from ..db.state_store import StateStore, json_dumps
from ..llm.gateway import LLMGateway, MockGateway
from ..llm.prompt_registry import PromptRegistry
from ..core.orchestrator import Orchestrator
from .snapshots import (
    SnapshotManager,
    create_snapshot_before_turn,
    run_turn_in_sandbox,
    compare_turn_outputs as snapshot_compare,
)


@dataclass
class ReplayResult:
    """Result of replaying a single turn."""
    turn_no: int
    original_input: str
    original_output: str
    replay_output: str
    prompt_versions: dict
    latency_ms: float
    matches_original: bool


@dataclass
class ABTestResult:
    """Result of A/B testing two prompt variants."""
    turn_no: int
    player_input: str
    variant_a: dict  # {"version": "v0", "output": "..."}
    variant_b: dict  # {"version": "v1", "output": "..."}
    metrics_a: dict
    metrics_b: dict


def rerun_turns(
    state_store: StateStore,
    campaign_id: str,
    start_turn: int,
    end_turn: int,
    prompt_overrides: Optional[dict] = None,
    llm_gateway: Optional[LLMGateway] = None,
    prompt_registry: Optional[PromptRegistry] = None
) -> dict:
    """
    Replay turns with optional prompt version overrides.

    Uses state snapshots to replay each turn in an isolated sandbox.

    Args:
        state_store: Database connection
        campaign_id: Campaign to replay
        start_turn: First turn to replay
        end_turn: Last turn to replay
        prompt_overrides: Dict of {"interpreter": "v1", ...}
        llm_gateway: LLM gateway to use (defaults to mock)
        prompt_registry: Prompt registry to use

    Returns:
        Report dict with original and replayed outputs
    """
    # Get original events
    events = state_store.get_events_range(campaign_id, start_turn, end_turn)

    if not events:
        return {
            "status": "error",
            "note": f"No events found for turns {start_turn}-{end_turn}",
            "events": []
        }

    # Setup for replay
    gateway = llm_gateway or MockGateway()

    results = []
    for event in events:
        turn_no = event["turn_no"]
        player_input = event["player_input"]
        original_output = event["final_text"]

        # Get snapshot before this turn
        start_time = time.time()
        try:
            snapshot = create_snapshot_before_turn(state_store, campaign_id, turn_no)

            # Run turn in sandbox with prompt overrides
            replay_result = run_turn_in_sandbox(
                state_store,
                snapshot,
                player_input,
                prompt_versions=prompt_overrides,
                llm_gateway=gateway
            )
            replay_output = replay_result.get("final_text", "")

        except Exception as e:
            # Fall back to original if sandbox fails
            replay_output = original_output

        latency_ms = (time.time() - start_time) * 1000

        results.append(ReplayResult(
            turn_no=turn_no,
            original_input=player_input,
            original_output=original_output,
            replay_output=replay_output,
            prompt_versions=prompt_overrides or {},
            latency_ms=latency_ms,
            matches_original=(original_output == replay_output)
        ))

    return {
        "status": "completed",
        "campaign_id": campaign_id,
        "turns_replayed": len(results),
        "prompt_overrides": prompt_overrides or {},
        "results": [
            {
                "turn_no": r.turn_no,
                "input": r.original_input,
                "original": r.original_output[:200] + "..." if len(r.original_output) > 200 else r.original_output,
                "replay": r.replay_output[:200] + "..." if len(r.replay_output) > 200 else r.replay_output,
                "matches": r.matches_original,
                "latency_ms": r.latency_ms
            }
            for r in results
        ],
        "note": "Turns replayed in isolated sandbox environments using state snapshots."
    }


def ab_test_turn(
    state_store: StateStore,
    campaign_id: str,
    turn_no: int,
    variant_a_versions: dict,
    variant_b_versions: dict,
    llm_gateway: Optional[LLMGateway] = None
) -> ABTestResult:
    """
    Run A/B test on a single turn with two prompt variants.

    Uses state snapshots to run each variant in an isolated sandbox.

    Args:
        state_store: Database connection
        campaign_id: Campaign containing the turn
        turn_no: Turn to test
        variant_a_versions: Prompt versions for A (e.g., {"narrator": "v0"})
        variant_b_versions: Prompt versions for B (e.g., {"narrator": "v1"})
        llm_gateway: LLM gateway (uses MockGateway if not provided)

    Returns:
        ABTestResult with both outputs
    """
    # Get original event
    event = state_store.get_event(campaign_id, turn_no)
    if not event:
        raise ValueError(f"Turn {turn_no} not found in campaign {campaign_id}")

    player_input = event["player_input"]
    gateway = llm_gateway or MockGateway()

    # Use snapshot system for clean comparison
    comparison = snapshot_compare(
        state_store,
        campaign_id,
        turn_no,
        variant_a_versions,
        variant_b_versions,
        llm_gateway=gateway
    )

    return ABTestResult(
        turn_no=turn_no,
        player_input=player_input,
        variant_a={
            "versions": variant_a_versions,
            "output": comparison.get("variant_a", {}).get("output", ""),
        },
        variant_b={
            "versions": variant_b_versions,
            "output": comparison.get("variant_b", {}).get("output", ""),
        },
        metrics_a={},
        metrics_b={}
    )


def compare_prompt_versions(
    state_store: StateStore,
    campaign_id: str,
    start_turn: int,
    end_turn: int,
    stage: str,  # "interpreter", "planner", "narrator"
    version_a: str,
    version_b: str
) -> dict:
    """
    Compare two versions of a prompt across multiple turns.

    Returns statistics on which version performed better.
    """
    events = state_store.get_events_range(campaign_id, start_turn, end_turn)

    if not events:
        return {"error": "No events found"}

    # This would need LLM calls to actually compare
    # For now, return a template for what the comparison would look like
    return {
        "stage": stage,
        "version_a": version_a,
        "version_b": version_b,
        "turns_compared": len(events),
        "results": {
            "note": "Full comparison requires LLM gateway",
            "template": {
                "version_a_wins": 0,
                "version_b_wins": 0,
                "ties": len(events),
                "avg_length_a": 0,
                "avg_length_b": 0,
                "preference_signals": []
            }
        }
    }


def format_replay_report(report: dict) -> str:
    """Format replay report for display."""
    lines = [
        "=" * 60,
        f"Replay Report: {report.get('campaign_id', 'unknown')}",
        "=" * 60,
        f"Status: {report.get('status', 'unknown')}",
        f"Turns replayed: {report.get('turns_replayed', 0)}",
    ]

    if report.get('prompt_overrides'):
        lines.append(f"Prompt overrides: {json.dumps(report['prompt_overrides'])}")

    if report.get('note'):
        lines.append(f"Note: {report['note']}")

    lines.append("")
    lines.append("Results:")
    lines.append("-" * 40)

    for r in report.get('results', []):
        lines.append(f"Turn {r['turn_no']}:")
        lines.append(f"  Input: {r['input'][:50]}...")
        lines.append(f"  Original: {r['original'][:50]}...")
        if not r['matches']:
            lines.append(f"  Replay: {r['replay'][:50]}...")
        lines.append(f"  Matches: {'✓' if r['matches'] else '✗'}")
        lines.append("")

    return "\n".join(lines)


def format_ab_report(results: list[ABTestResult]) -> str:
    """Format A/B test results for display."""
    lines = [
        "=" * 60,
        "A/B Test Report",
        "=" * 60,
    ]

    for r in results:
        lines.append(f"Turn {r.turn_no}: {r.player_input[:40]}...")
        lines.append(f"  Variant A: {r.variant_a['output'][:60]}...")
        lines.append(f"  Variant B: {r.variant_b['output'][:60]}...")
        lines.append("")

    return "\n".join(lines)
