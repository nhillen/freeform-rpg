"""Data models for the PDF ingest pipeline.

All intermediate representations passed between pipeline stages.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Stage 1: Extraction
# ---------------------------------------------------------------------------

@dataclass
class PageEntry:
    """A single extracted page."""
    page_num: int
    text: str
    has_images: bool = False
    image_paths: list[str] = field(default_factory=list)
    char_count: int = 0
    ocr_used: bool = False


@dataclass
class ExtractionResult:
    """Output of Stage 1 (PDF extraction)."""
    pdf_path: str
    total_pages: int
    pages: list[PageEntry] = field(default_factory=list)
    output_dir: str = ""
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage 2: Structure
# ---------------------------------------------------------------------------

class ChapterIntent(Enum):
    """Intent classification for top-level document sections."""
    SETTING = "setting"        # World, geography, atmosphere, history
    FACTIONS = "factions"      # Organizations, traditions, clans
    MECHANICS = "mechanics"    # Rules, magic systems, character creation
    CHARACTERS = "characters"  # NPCs, archetypes, stat blocks
    NARRATIVE = "narrative"    # Fiction, in-character prose
    REFERENCE = "reference"    # Appendices, glossaries, tables
    META = "meta"              # Copyright, credits, ToC
    EQUIPMENT = "equipment"    # Gear, items, weapons
    BESTIARY = "bestiary"      # Monsters, antagonists, spirits
    UNKNOWN = "unknown"        # No match — behaves as pre-change default


@dataclass
class SectionNode:
    """A node in the document hierarchy tree."""
    title: str
    level: int  # 1 = chapter, 2 = section, 3 = subsection
    page_start: int
    page_end: int
    children: list["SectionNode"] = field(default_factory=list)
    content: str = ""
    intent: Optional[ChapterIntent] = None


@dataclass
class DocumentStructure:
    """Output of Stage 2 (structure detection)."""
    title: str
    sections: list[SectionNode] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage 3: Segmentation
# ---------------------------------------------------------------------------

class ContentType(Enum):
    """Content type for a segment."""
    LOCATION = "location"
    NPC = "npc"
    FACTION = "faction"
    CULTURE = "culture"
    ITEM = "item"
    EVENT = "event"
    HISTORY = "history"
    RULES = "rules"
    TABLE = "table"
    GENERAL = "general"


class Route(Enum):
    """Processing route for a segment."""
    LORE = "lore"
    SYSTEMS = "systems"
    BOTH = "both"


@dataclass
class SegmentEntry:
    """A content segment ready for classification."""
    id: str
    title: str
    content: str
    source_section: str  # parent section title
    page_start: int
    page_end: int
    word_count: int = 0
    content_type: Optional[ContentType] = None
    route: Optional[Route] = None
    classification_confidence: float = 0.0
    tags: list[str] = field(default_factory=list)
    chapter_intent: Optional[ChapterIntent] = None


@dataclass
class SegmentManifest:
    """Output of Stage 3 (segmentation)."""
    segments: list[SegmentEntry] = field(default_factory=list)
    total_words: int = 0
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage 5: Entity Extraction / Enrichment
# ---------------------------------------------------------------------------

@dataclass
class EntityEntry:
    """An entity extracted from the source material."""
    id: str
    name: str
    entity_type: str  # npc, location, faction, item, etc.
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    related_entities: list[str] = field(default_factory=list)
    source_segments: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class EntityRegistry:
    """Global entity registry built during enrichment."""
    entities: list[EntityEntry] = field(default_factory=list)
    entity_index: dict[str, EntityEntry] = field(default_factory=dict)

    def add(self, entity: EntityEntry) -> None:
        self.entities.append(entity)
        self.entity_index[entity.id] = entity

    def get(self, entity_id: str) -> Optional[EntityEntry]:
        return self.entity_index.get(entity_id)

    def list_by_type(self, entity_type: str) -> list[EntityEntry]:
        return [e for e in self.entities if e.entity_type == entity_type]


# ---------------------------------------------------------------------------
# Systems Extraction
# ---------------------------------------------------------------------------

@dataclass
class SystemsExtractionManifest:
    """Output of systems extraction stages."""
    extractions: dict[str, dict] = field(default_factory=dict)
    # keys: resolution, clocks, entity_stats, conditions,
    #        calibration, action_types, escalation
    source_segments: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pipeline Configuration
# ---------------------------------------------------------------------------

@dataclass
class IngestConfig:
    """Configuration for the full ingest pipeline."""
    pdf_path: str = ""
    output_dir: str = ""
    pack_id: str = ""
    pack_name: str = ""
    pack_version: str = "1.0"
    pack_layer: str = "sourcebook"
    pack_author: str = ""
    pack_description: str = ""

    # Stage toggles
    use_ocr: bool = False
    extract_images: bool = False
    skip_systems: bool = False

    # LLM settings
    sonnet_model: str = "claude-sonnet-4-20250514"
    haiku_model: str = "claude-3-5-haiku-20241022"

    # Size constraints
    min_segment_words: int = 100
    max_segment_words: int = 1500
    target_segment_words: int = 400

    # Work directory structure
    work_dir: str = ""

    def get_work_dir(self) -> Path:
        if self.work_dir:
            return Path(self.work_dir)
        pdf_stem = Path(self.pdf_path).stem if self.pdf_path else "unknown"
        return Path(self.output_dir) / f"work_{pdf_stem}"
