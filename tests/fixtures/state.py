"""
Functions for setting up test state in the database.

These populate the StateStore with test data for integration tests.
"""

from typing import Optional
from .entities import make_player, make_npc, make_location
from .facts import make_known_fact, make_world_fact


def setup_minimal_game_state(store, campaign_id: str = "test_campaign") -> str:
    """
    Set up minimal game state for testing.

    Creates:
    - 1 campaign with default calibration
    - 1 player entity
    - 1 NPC entity (friendly)
    - 1 location entity
    - Scene with player and NPC present
    - 5 standard clocks
    - 1 known fact, 1 hidden fact
    - 1 active thread

    Returns:
        campaign_id
    """
    # Create campaign
    store.create_campaign(
        campaign_id=campaign_id,
        name="Test Campaign",
        calibration={
            "tone": {"gritty_vs_cinematic": 0.5},
            "themes": {"primary": ["testing"]},
            "risk": {"lethality": "moderate", "failure_mode": "consequential"}
        },
        genre_rules={"setting": "Test setting"}
    )

    # Create entities
    player = make_player()
    store.create_entity(
        entity_id=player["id"],
        entity_type=player["type"],
        name=player["name"],
        attrs=player["attrs"],
        tags=player["tags"]
    )

    npc = make_npc(
        id="test_npc",
        name="Test NPC",
        role="contact",
        description="A helpful contact for testing"
    )
    store.create_entity(
        entity_id=npc["id"],
        entity_type=npc["type"],
        name=npc["name"],
        attrs=npc["attrs"],
        tags=npc["tags"]
    )

    location = make_location(
        id="test_location",
        name="Test Location",
        description="A place for testing"
    )
    store.create_entity(
        entity_id=location["id"],
        entity_type=location["type"],
        name=location["name"],
        attrs=location["attrs"],
        tags=location["tags"]
    )

    # Set up scene
    store.set_scene(
        location_id="test_location",
        present_entity_ids=["player", "test_npc"],
        time={"hour": 12, "period": "day"},
        constraints={}
    )

    # Set up clocks
    setup_clocks(store)

    # Create facts
    store.create_fact(
        fact_id="fact_known",
        subject_id="test_npc",
        predicate="disposition",
        obj="friendly",
        visibility="known",
        discovered_turn=0,
        discovery_method="initial"
    )

    store.create_fact(
        fact_id="fact_hidden",
        subject_id="test_npc",
        predicate="knows",
        obj={"secret": "something important"},
        visibility="world"
    )

    # Create thread
    store.create_thread(
        thread_id="main_thread",
        title="Test the system",
        status="active",
        stakes={"success": "Tests pass", "failure": "Bugs found"}
    )

    # Create relationship
    store.create_relationship(
        a_id="player",
        b_id="test_npc",
        rel_type="trust",
        intensity=1,
        notes={"history": "Just met"}
    )

    return campaign_id


def setup_clocks(store, values: Optional[dict] = None) -> None:
    """
    Set up standard game clocks.

    Args:
        store: StateStore instance
        values: Optional dict of clock_name -> starting_value overrides
    """
    values = values or {}

    clocks = [
        {
            "id": "heat",
            "name": "Heat",
            "value": values.get("heat", 0),
            "max": 8,
            "triggers": {
                "4": "Attention increasing",
                "6": "Active investigation",
                "8": "Full alert"
            }
        },
        {
            "id": "time",
            "name": "Time",
            "value": values.get("time", 8),
            "max": 12,
            "triggers": {
                "4": "Time running short",
                "2": "Almost out of time",
                "0": "Deadline passed"
            }
        },
        {
            "id": "harm",
            "name": "Harm",
            "value": values.get("harm", 0),
            "max": 4,
            "triggers": {
                "2": "Seriously hurt",
                "4": "Critical condition"
            }
        },
        {
            "id": "cred",
            "name": "Cred",
            "value": values.get("cred", 500),
            "max": 9999,
            "triggers": {}
        },
        {
            "id": "rep",
            "name": "Rep",
            "value": values.get("rep", 2),
            "max": 5,
            "triggers": {
                "0": "Nobody",
                "4": "Well known"
            }
        }
    ]

    for clock in clocks:
        store.create_clock(
            clock_id=clock["id"],
            name=clock["name"],
            value=clock["value"],
            max_value=clock["max"],
            triggers=clock["triggers"]
        )


def setup_combat_state(store, campaign_id: str = "combat_campaign") -> str:
    """
    Set up state for combat testing.

    Creates a hostile encounter scenario.
    """
    # Create campaign
    store.create_campaign(
        campaign_id=campaign_id,
        name="Combat Test Campaign",
        calibration={
            "risk": {"lethality": "moderate", "failure_mode": "consequential"}
        }
    )

    # Player
    player = make_player()
    store.create_entity(
        entity_id=player["id"],
        entity_type=player["type"],
        name=player["name"],
        attrs=player["attrs"],
        tags=player["tags"]
    )

    # Hostile NPC
    enemy = make_npc(
        id="enemy",
        name="Hostile Enemy",
        role="enemy",
        description="Someone looking for a fight",
        tags=["hostile"]
    )
    store.create_entity(
        entity_id=enemy["id"],
        entity_type=enemy["type"],
        name=enemy["name"],
        attrs=enemy["attrs"],
        tags=enemy["tags"]
    )

    # Location
    location = make_location(
        id="combat_zone",
        name="Combat Zone",
        description="A dangerous place"
    )
    store.create_entity(
        entity_id=location["id"],
        entity_type=location["type"],
        name=location["name"],
        attrs=location["attrs"],
        tags=location["tags"]
    )

    # Scene
    store.set_scene(
        location_id="combat_zone",
        present_entity_ids=["player", "enemy"],
        visibility_conditions="normal"
    )

    # Clocks
    setup_clocks(store, {"heat": 2})

    # Fact: enemy is hostile
    store.create_fact(
        fact_id="enemy_hostile",
        subject_id="enemy",
        predicate="disposition",
        obj="hostile",
        visibility="known"
    )

    # Give player a weapon
    store.add_inventory("player", "knife", 1, {"equipped": True})

    return campaign_id


def setup_investigation_state(store, campaign_id: str = "investigation_campaign") -> str:
    """
    Set up state for investigation testing.

    Creates a crime scene with clues and witnesses.
    """
    # Create campaign
    store.create_campaign(
        campaign_id=campaign_id,
        name="Investigation Test Campaign",
        calibration={
            "risk": {"lethality": "low", "failure_mode": "consequential"}
        }
    )

    # Player
    player = make_player(background="Investigator")
    store.create_entity(
        entity_id=player["id"],
        entity_type=player["type"],
        name=player["name"],
        attrs=player["attrs"],
        tags=player["tags"]
    )

    # Witness
    witness = make_npc(
        id="witness",
        name="Nervous Witness",
        role="witness",
        description="Saw something, scared to talk"
    )
    store.create_entity(
        entity_id=witness["id"],
        entity_type=witness["type"],
        name=witness["name"],
        attrs=witness["attrs"],
        tags=witness["tags"]
    )

    # Crime scene
    location = make_location(
        id="crime_scene",
        name="Crime Scene",
        description="Where it happened",
        features=["blood", "broken glass", "overturned chair"]
    )
    store.create_entity(
        entity_id=location["id"],
        entity_type=location["type"],
        name=location["name"],
        attrs=location["attrs"],
        tags=location["tags"]
    )

    # Scene
    store.set_scene(
        location_id="crime_scene",
        present_entity_ids=["player", "witness"]
    )

    # Clocks
    setup_clocks(store)

    # Known fact
    store.create_fact(
        fact_id="crime_occurred",
        subject_id="crime_scene",
        predicate="event",
        obj={"type": "murder", "victim": "unknown"},
        visibility="known"
    )

    # Hidden clues (Three Clue Rule - 3 ways to find the truth)
    store.create_fact(
        fact_id="clue_witness",
        subject_id="witness",
        predicate="knows",
        obj={"what": "saw the killer", "will_share": "if reassured"},
        visibility="world",
        tags=["clue"]
    )

    store.create_fact(
        fact_id="clue_physical",
        subject_id="crime_scene",
        predicate="contains",
        obj={"item": "dropped ID", "location": "under chair"},
        visibility="world",
        tags=["clue"]
    )

    store.create_fact(
        fact_id="clue_digital",
        subject_id="crime_scene",
        predicate="contains",
        obj={"item": "security footage", "location": "camera system"},
        visibility="world",
        tags=["clue"]
    )

    # Thread
    store.create_thread(
        thread_id="investigate_murder",
        title="Find out who did it",
        status="active",
        stakes={"success": "Justice", "failure": "Killer escapes"}
    )

    return campaign_id
