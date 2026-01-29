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
# Extraction Configuration (System Profiles)
# ---------------------------------------------------------------------------

@dataclass
class MechanicalIndicator:
    """A pattern that indicates mechanical content on a page."""
    pattern: str  # Regex pattern
    meaning: str  # What this pattern indicates (rating_dots, dice_notation, etc.)
    confidence: float = 0.5  # Base confidence when matched


@dataclass
class SectionPattern:
    """Pattern for detecting system-specific sections."""
    header_pattern: str  # Regex for section header
    content_type: str  # ranked_ability, equipment_list, rules, etc.
    rating_type: str = "dots"  # How ratings are expressed
    confidence: float = 0.7


@dataclass
class RatingScale:
    """How to interpret a rating scale."""
    symbol: str = ""
    empty_symbol: str = ""
    max: int = 5
    symbols: list[str] = field(default_factory=list)
    filled: list[str] = field(default_factory=list)
    empty: list[str] = field(default_factory=list)
    typical_max: int = 5
    range: tuple[int, int] = (1, 10)
    default: int = 5
    descriptions: dict[int, str] = field(default_factory=dict)
    applies_to: list[str] = field(default_factory=list)


@dataclass
class StatBlockHints:
    """Hints for parsing stat blocks."""
    npc_format: str = ""  # Template showing expected format
    markers: list[str] = field(default_factory=list)  # Regex patterns for stat block lines


@dataclass
class HealthConfig:
    """Health track configuration."""
    track_type: str = "levels"  # levels, hit_points, stress_boxes
    levels: list[dict] = field(default_factory=list)  # {name, penalty}
    damage_types: list[str] = field(default_factory=list)


@dataclass
class GuidancePattern:
    """Pattern for detecting GM guidance content."""
    pattern: str  # Regex pattern
    meaning: str  # gm_technique, player_experience, pacing_advice, etc.
    confidence: float = 0.5


@dataclass
class GuidanceConfig:
    """Configuration for GM guidance extraction."""
    chapter_indicators: list[str] = field(default_factory=list)
    content_patterns: list[GuidancePattern] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)


@dataclass
class ExtractionHints:
    """Extraction hints portion of system config."""
    mechanical_indicators: list[MechanicalIndicator] = field(default_factory=list)
    section_patterns: dict[str, SectionPattern] = field(default_factory=dict)
    rating_scales: dict[str, RatingScale] = field(default_factory=dict)
    stat_blocks: StatBlockHints = field(default_factory=StatBlockHints)
    health: HealthConfig = field(default_factory=HealthConfig)
    gm_guidance: GuidanceConfig = field(default_factory=GuidanceConfig)


@dataclass
class ExtractionConfig:
    """Complete extraction configuration for a system.

    Built by merging: _base.yaml -> system.yaml -> pack/extraction.yaml
    Used by systems extractors to apply system-specific patterns.
    """
    id: str = "_base"
    name: str = "Base TTRPG Patterns"
    inherits: Optional[str] = None

    # Extraction hints
    extraction: ExtractionHints = field(default_factory=ExtractionHints)

    # Source info (for debugging)
    sources: list[str] = field(default_factory=list)  # Config files that were merged

    def get_mechanical_indicators(self) -> list[MechanicalIndicator]:
        """Get all mechanical indicator patterns."""
        return self.extraction.mechanical_indicators

    def get_section_patterns(self) -> dict[str, SectionPattern]:
        """Get all section patterns."""
        return self.extraction.section_patterns

    def get_rating_scale(self, name: str) -> Optional[RatingScale]:
        """Get a specific rating scale by name."""
        return self.extraction.rating_scales.get(name)

    def get_health_config(self) -> HealthConfig:
        """Get health track configuration."""
        return self.extraction.health

    def get_guidance_config(self) -> GuidanceConfig:
        """Get GM guidance extraction config."""
        return self.extraction.gm_guidance


# ---------------------------------------------------------------------------
# GM Guidance Extraction
# ---------------------------------------------------------------------------

@dataclass
class GuidanceChunk:
    """A chunk of extracted GM guidance content."""
    id: str
    category: str  # pacing, scene_types, tone, player_agency, etc.
    content: str
    source_page: int
    source_section: str
    is_universal: bool = False  # True = candidate for core prompt refinement
    confidence: float = 0.5
    tags: list[str] = field(default_factory=list)


@dataclass
class GuidanceExtractionResult:
    """Output of GM guidance extraction stage."""
    chunks: list[GuidanceChunk] = field(default_factory=list)
    universal_candidates: list[GuidanceChunk] = field(default_factory=list)
    genre_specific: list[GuidanceChunk] = field(default_factory=list)
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
    draft_mode: bool = False  # Output to draft/ with review markers instead of content_packs/

    # System extraction config
    system_hint: str = ""  # System ID for extraction config (e.g., "world_of_darkness")

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
