"""Stage S1: Mechanical Systems Extraction.

Extracts game-mechanical data from systems-routed segments using
sub-extractors that target specific mechanical patterns:
  1. Resolution mechanics (dice pools, sum-based, target numbers)
  2. Stat schema (attributes, abilities, special traits, backgrounds)
  3. Health system (health levels, damage types, healing)
  4. Equipment (weapons, armor, gear)
  5. Conditions (status effects, states)
  6. Clocks (progress trackers, thresholds, triggers)
  7. Calibration (difficulty tuning, preset values)
  8. Action types (available actions, costs, risks)
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from .models import Route, SegmentEntry, SegmentManifest, SystemsExtractionManifest
from .utils import ensure_dir, write_stage_meta

logger = logging.getLogger(__name__)

# Common English stopwords to filter from extracted terms
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "as", "is", "was", "are", "were", "been", "be",
    "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "must", "shall", "can", "need", "dare", "ought", "used",
    "this", "that", "these", "those", "it", "its", "he", "she", "they", "them",
    "his", "her", "their", "my", "your", "our", "who", "whom", "whose", "which",
    "what", "where", "when", "why", "how", "all", "each", "every", "both",
    "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only",
    "own", "same", "so", "than", "too", "very", "just", "also", "now", "here",
    "there", "then", "once", "any", "many", "much", "new", "old", "first", "last",
    "long", "great", "little", "own", "other", "old", "right", "big", "high",
    "different", "small", "large", "next", "early", "young", "important", "few",
    "public", "bad", "same", "able", "into", "after", "before", "between",
    "under", "again", "further", "once", "during", "about", "against", "above",
    "below", "up", "down", "out", "off", "over", "through", "while", "because",
    "until", "unless", "although", "though", "however", "therefore", "thus",
    "hence", "otherwise", "still", "already", "yet", "even", "ever", "never",
    "always", "often", "sometimes", "usually", "really", "quite", "rather",
    "almost", "enough", "especially", "particularly", "generally", "specifically",
    # Game-context false positives
    "using", "based", "following", "given", "certain", "within", "without",
    "whether", "either", "neither", "nothing", "something", "anything", "everything",
    "someone", "anyone", "everyone", "nobody", "anybody", "everybody",
    "chapter", "section", "page", "table", "example", "note", "see", "below",
}


def _is_valid_term(term: str, min_len: int = 3) -> bool:
    """Check if a term is valid (not a stopword, has sufficient length)."""
    term_lower = term.lower()
    return (
        len(term) >= min_len
        and term_lower not in STOPWORDS
        and not term.isdigit()
        and term_lower.isalpha()
    )


# Sub-extractor keys - ordered by importance for system definition
EXTRACTOR_KEYS = [
    "resolution",      # Core dice mechanics
    "stat_schema",     # Attributes, abilities, special traits
    "health",          # Health levels, damage types
    "equipment",       # Weapons, armor
    "magic",           # Spellcasting, spheres, paradox
    "conditions",      # Status effects
    "clocks",          # Progress trackers
    "calibration",     # Difficulty settings
    "action_types",    # Action definitions
]


class SystemsExtractor:
    """Extracts mechanical data from systems-routed segments."""

    def __init__(self, llm_gateway=None, prompt_registry=None):
        self.gateway = llm_gateway
        self.registry = prompt_registry

    def extract(
        self,
        manifest: SegmentManifest,
        output_dir: str | Path,
        raw_pages_dir: str | Path | None = None,
    ) -> SystemsExtractionManifest:
        """Run all sub-extractors on systems-routed segments.

        Args:
            manifest: Classified segment manifest.
            output_dir: Directory to write extraction results.
            raw_pages_dir: Optional path to raw extracted pages (01_extract/pages).
                          If provided, uses raw pages for extraction instead of
                          summarized segments (recommended for mechanical data).

        Returns:
            SystemsExtractionManifest with extracted data.
        """
        output_dir = Path(output_dir)
        ensure_dir(output_dir)

        systems_segments = [
            s for s in manifest.segments
            if s.route in (Route.SYSTEMS, Route.BOTH)
        ]

        if not systems_segments:
            logger.warning("No systems segments to extract")
            return SystemsExtractionManifest()

        # Determine source text for extraction
        if raw_pages_dir:
            # Use raw pages from the relevant page ranges (better for mechanical data)
            systems_text = self._load_raw_pages_for_segments(
                Path(raw_pages_dir), systems_segments
            )
            logger.info("Using raw pages for systems extraction (%d chars)", len(systems_text))
        else:
            # Fall back to summarized segment content
            systems_text = "\n\n---\n\n".join(
                f"## {s.title}\n\n{s.content}" for s in systems_segments
            )
            logger.info("Using summarized segments for systems extraction (%d chars)", len(systems_text))

        result = SystemsExtractionManifest(
            source_segments=[s.id for s in systems_segments],
        )

        # Run each sub-extractor
        for key in EXTRACTOR_KEYS:
            extraction = self._run_sub_extractor(key, systems_text, systems_segments)
            if extraction:
                result.extractions[key] = extraction
                # Write individual extraction file
                (output_dir / f"{key}.yaml").write_text(
                    self._to_yaml(extraction),
                    encoding="utf-8",
                )

        # Write manifest
        manifest_data = {
            "extractors_run": list(result.extractions.keys()),
            "source_segments": result.source_segments,
            "metadata": result.metadata,
        }
        (output_dir / "extraction_manifest.json").write_text(
            json.dumps(manifest_data, indent=2, ensure_ascii=False)
        )

        # Optionally run LLM refinement
        if self.gateway:
            try:
                from .systems_refine import SystemsRefiner
                refiner = SystemsRefiner(self.gateway)
                for key in list(result.extractions.keys()):
                    raw = result.extractions[key]
                    refined = refiner.refine_extraction(key, raw, systems_text)
                    if refined and refined != raw:
                        result.extractions[key] = refined
                        # Write refined version
                        (output_dir / f"{key}.yaml").write_text(
                            self._to_yaml(refined),
                            encoding="utf-8",
                        )
                        logger.info("Refined %s extraction with LLM", key)
            except Exception as e:
                logger.warning("LLM refinement skipped: %s", e)

        write_stage_meta(output_dir, {
            "stage": "systems_extract",
            "status": "complete",
            "extractors_run": list(result.extractions.keys()),
            "source_segments": len(systems_segments),
            "llm_refined": self.gateway is not None,
        })

        logger.info(
            "Ran %d sub-extractors on %d systems segments",
            len(result.extractions), len(systems_segments)
        )
        return result

    def _run_sub_extractor(
        self,
        key: str,
        systems_text: str,
        segments: list[SegmentEntry],
    ) -> Optional[dict]:
        """Run a single sub-extractor."""
        # First try heuristic extraction
        heuristic_result = self._heuristic_extract(key, systems_text)

        # Then use LLM for deeper extraction
        if self.gateway and self.registry:
            llm_result = self._llm_extract(key, systems_text)
            if llm_result:
                # Merge heuristic and LLM results
                return self._merge_extractions(heuristic_result, llm_result)

        return heuristic_result if heuristic_result else None

    def _heuristic_extract(self, key: str, text: str) -> Optional[dict]:
        """Pattern-based mechanical data extraction."""
        extractors = {
            "resolution": self._extract_resolution,
            "stat_schema": self._extract_stat_schema,
            "health": self._extract_health,
            "equipment": self._extract_equipment,
            "magic": self._extract_magic,
            "conditions": self._extract_conditions,
            "clocks": self._extract_clocks,
            "calibration": self._extract_calibration,
            "action_types": self._extract_action_types,
        }
        fn = extractors.get(key)
        if fn:
            return fn(text)
        return None

    def _extract_resolution(self, text: str) -> Optional[dict]:
        """Extract dice resolution mechanics - supports multiple system types."""
        result = {}
        text_lower = text.lower()

        # Detect resolution method
        if re.search(r"dice\s*pool|roll\s+\d+\s+dice|attribute\s*\+\s*ability", text_lower):
            result["method"] = "dice_pool"
        elif re.search(r"roll\s+2d6|moves?\s+trigger|pbta|powered\s+by", text_lower):
            result["method"] = "sum_bands"
        elif re.search(r"d20|difficulty\s+class|dc\s+\d+", text_lower):
            result["method"] = "target_number"

        # Die type detection
        die_matches = re.findall(r"\b(\d*)d(\d+)\b", text, re.IGNORECASE)
        if die_matches:
            # Find most common die type
            die_types = [int(m[1]) for m in die_matches if m[1]]
            if die_types:
                result["die_type"] = max(set(die_types), key=die_types.count)

        # Pool composition patterns (WoD style)
        pool_patterns = [
            r"(attribute)\s*\+\s*(ability)",
            r"(stat)\s*\+\s*(skill)",
            r"(\w+)\s*\+\s*(\w+)\s*(?:dice|pool)",
        ]
        for pattern in pool_patterns:
            m = re.search(pattern, text_lower)
            if m:
                result["pool_composition"] = f"{m.group(1).title()} + {m.group(2).title()}"
                break

        # Difficulty detection
        diff_match = re.search(
            r"(?:default\s+)?difficulty\s*(?:of|is|:)?\s*(\d+)",
            text_lower
        )
        if diff_match:
            result["default_difficulty"] = int(diff_match.group(1))

        # Difficulty scale (named levels)
        diff_scale = []
        diff_scale_pattern = re.compile(
            r"(?:difficulty\s+)?(\d+)\s*[-–:]\s*(easy|routine|standard|challenging|difficult|hard|very\s+hard|nearly\s+impossible|trivial)",
            re.IGNORECASE
        )
        for m in diff_scale_pattern.finditer(text):
            diff_scale.append({"value": int(m.group(1)), "label": m.group(2).strip()})
        # Also check reverse format: "Easy (3)"
        diff_scale_pattern2 = re.compile(
            r"(easy|routine|standard|challenging|difficult|hard|trivial)\s*[:\(]\s*(\d+)",
            re.IGNORECASE
        )
        for m in diff_scale_pattern2.finditer(text):
            diff_scale.append({"value": int(m.group(2)), "label": m.group(1).strip()})
        if diff_scale:
            result["difficulty_scale"] = diff_scale

        # 1s cancel successes (WoD)
        if re.search(r"1s?\s+cancel|ones?\s+cancel|subtract.*ones?|each\s+1\s+cancels?", text_lower):
            result["ones_cancel_successes"] = True

        # Botch detection
        if re.search(r"botch|critical\s+failure|catastrophic", text_lower):
            result["botch_on_ones"] = True

        # Outcome thresholds for dice pools
        outcome_patterns = [
            (r"(\d+)\s*(?:or\s+more\s+)?success(?:es)?.*exceptional", "exceptional"),
            (r"(\d+)[-–](\d+)\s*success(?:es)?.*(?:standard|complete|full)", "success"),
            (r"(\d+)\s*success.*(?:marginal|partial|mixed)", "marginal"),
        ]
        thresholds = {}
        for pattern, label in outcome_patterns:
            m = re.search(pattern, text_lower)
            if m:
                thresholds[label] = int(m.group(1))
        # Check for failure pattern separately (no capture group)
        if re.search(r"(?:no|zero|0)\s*success(?:es)?.*fail", text_lower):
            thresholds["failure"] = 0
        if thresholds:
            result["outcome_thresholds"] = thresholds

        # Outcome bands for sum-based (PbtA style)
        bands = []
        band_pattern = re.compile(
            r"(\d+)\s*[-–]\s*(\d+)\s*[:=]\s*(.+?)(?:\n|$)|(\d+)\s*\+\s*[:=]\s*(.+?)(?:\n|$)",
            re.IGNORECASE
        )
        for m in band_pattern.finditer(text):
            if m.group(1) and m.group(2):
                bands.append({"range": f"{m.group(1)}-{m.group(2)}", "label": m.group(3).strip()})
            elif m.group(4):
                bands.append({"range": f"{m.group(4)}+", "label": m.group(5).strip()})
        if bands:
            result["outcome_bands"] = bands

        # Willpower spending
        wp_match = re.search(
            r"(?:spend|use)\s+(?:a\s+)?(?:point\s+of\s+)?(willpower|wp|will)\s*(?:for|to\s+(?:gain|get|add))?\s*(\d+)?\s*(?:automatic\s+)?success",
            text_lower
        )
        if wp_match:
            result["willpower"] = {
                "enabled": True,
                "resource_name": "willpower",
                "effect": "automatic success",
                "max_per_turn": 1
            }

        # Specialties
        if re.search(r"specialty|specialization|specialities", text_lower):
            spec_match = re.search(
                r"specialty.*(?:roll|reroll|extra|additional|bonus).*(\d+|10)",
                text_lower
            )
            result["specialties"] = {
                "enabled": True,
                "trigger": "4+ dots in trait" if not spec_match else spec_match.group(0)[:100]
            }

        # Automatic success rule
        auto_match = re.search(
            r"(?:automatic(?:ally)?|auto)\s+(?:success|succeed).*(?:if|when).*(?:pool|dice)\s*(?:>=?|equals?|exceeds?)\s*(?:difficulty|target)",
            text_lower
        )
        if auto_match:
            result["automatic_success_rule"] = "pool >= difficulty"

        return result if result else None

    def _extract_stat_schema(self, text: str) -> Optional[dict]:
        """Extract attribute/ability structure - GENERIC extraction.

        Detects stat categories and groupings without assuming specific system names.
        The LLM refinement layer will contextualize results.
        """
        result = {}
        text_lower = text.lower()

        # === DETECT ATTRIBUTE CATEGORIES ===
        # Look for category headers followed by stat lists
        # Pattern: "Physical Attributes: Strength, Dexterity, Stamina"
        # Or: "Physical\nStrength\nDexterity\nStamina"

        attr_categories = {}

        # Common category names across systems
        category_keywords = [
            "physical", "mental", "social",  # WoD
            "body", "mind", "soul",  # Various
            "strength", "agility", "intellect",  # Generic
            "power", "finesse", "resistance",  # Chronicles of Darkness
        ]

        # Look for "X Attributes" or "X Traits" sections
        category_pattern = re.compile(
            r"(\w+)\s+(?:attributes?|traits?|stats?)\s*[:\n]",
            re.IGNORECASE
        )
        for m in category_pattern.finditer(text):
            cat_name = m.group(1).lower()
            if not _is_valid_term(cat_name, min_len=4):
                continue
            # Get following content to find attribute names
            following = text[m.end():m.end()+500]
            # Look for capitalized words that could be attributes
            attrs = re.findall(r"\b([A-Z][a-z]+)\b", following)
            # Filter to valid terms
            attrs = [a.lower() for a in attrs if _is_valid_term(a, min_len=4)][:5]
            if attrs:
                attr_categories[cat_name] = attrs

        # Fallback: detect common attribute names directly
        common_attrs = {
            "physical": ["strength", "dexterity", "stamina", "constitution", "agility", "body"],
            "mental": ["intelligence", "wits", "perception", "wisdom", "reason", "mind"],
            "social": ["charisma", "manipulation", "appearance", "presence", "composure"],
        }
        for cat, attrs in common_attrs.items():
            if cat not in attr_categories:
                found = [a for a in attrs if re.search(rf"\b{a}\b", text_lower)]
                if len(found) >= 2:  # Need at least 2 to be a category
                    attr_categories[cat] = found

        if attr_categories:
            result["attributes"] = attr_categories

        # === DETECT ABILITY/SKILL CATEGORIES ===
        ability_categories = {}

        # Look for skill category headers
        skill_cat_pattern = re.compile(
            r"(talents?|skills?|knowledges?|proficiencies?|abilities?)\s*[:\n]",
            re.IGNORECASE
        )
        for m in skill_cat_pattern.finditer(text):
            cat_name = m.group(1).lower().rstrip('s')  # Normalize plural
            following = text[m.end():m.end()+1000]
            # Look for bullet points or capitalized skill names
            skills = re.findall(r"(?:^|\n)\s*(?:•|[-*])?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", following)
            skills = [s.lower() for s in skills if _is_valid_term(s, min_len=4)][:15]
            if skills:
                ability_categories[cat_name] = skills

        if ability_categories:
            result["abilities"] = ability_categories

        # === DETECT SPECIAL/DERIVED TRAITS ===
        # These are system-specific pools like Willpower, Arete, Mana, etc.
        special_traits = {}

        # Look for traits with explicit ratings/ranges
        trait_range_pattern = re.compile(
            r"(\w+)\s+(?:rating|score|pool)?\s*(?:ranges?\s+from|is\s+rated)?\s*(\d+)\s*(?:to|-|–)\s*(\d+)",
            re.IGNORECASE
        )
        for m in trait_range_pattern.finditer(text):
            trait_name = m.group(1).lower()
            if _is_valid_term(trait_name, min_len=4):
                special_traits[trait_name] = {
                    "min": int(m.group(2)),
                    "max": int(m.group(3))
                }

        # Also detect traits that appear frequently with "points" or "pool"
        pool_traits = re.findall(
            r"(\w+)\s+(?:points?|pool)",
            text_lower
        )
        for trait in set(pool_traits):
            if _is_valid_term(trait, min_len=4) and trait not in special_traits:
                count = pool_traits.count(trait)
                if count >= 3:  # Require more mentions
                    special_traits[trait] = {"type": "pool"}

        if special_traits:
            result["special_traits"] = special_traits

        # === DETECT BACKGROUNDS/ADVANTAGES ===
        backgrounds = []

        # Look for "Backgrounds" or "Advantages" or "Merits" sections
        bg_section = re.search(
            r"(?:backgrounds?|advantages?|merits?)\s*[:\n](.+?)(?:\n\n|\n[A-Z]|\Z)",
            text_lower,
            re.DOTALL
        )
        if bg_section:
            # Extract capitalized items
            bg_items = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", text[bg_section.start():bg_section.end()])
            for bg in bg_items[:20]:
                if _is_valid_term(bg, min_len=4):
                    backgrounds.append({"name": bg})

        if backgrounds:
            result["backgrounds"] = backgrounds

        # === DETECT POINT ALLOCATION ===
        # Pattern: "7/5/3" or "prioritize (7/5/3)"
        alloc_match = re.search(
            r"(?:prioritize|distribute|allocate)?.*?(\d+)\s*/\s*(\d+)\s*/\s*(\d+)",
            text_lower
        )
        if alloc_match:
            nums = sorted([int(alloc_match.group(i)) for i in (1, 2, 3)], reverse=True)
            result["point_allocation"] = {
                "primary": nums[0],
                "secondary": nums[1],
                "tertiary": nums[2]
            }

        # === DETECT ADVANCEMENT COSTS ===
        # Pattern: "Attribute 5 per dot" or "Skill: 2 points"
        cost_pattern = re.compile(
            r"(\w+)\s*[:=]?\s*(\d+)\s*(?:per\s+dot|points?|xp|experience)",
            re.IGNORECASE
        )
        costs = {}
        for m in cost_pattern.finditer(text):
            trait_type = m.group(1).lower()
            if trait_type in ("attribute", "ability", "skill", "sphere", "discipline",
                             "background", "merit", "willpower", "virtue"):
                costs[trait_type] = int(m.group(2))
        if costs:
            result["advancement_costs"] = costs

        return result if result else None

    def _extract_health(self, text: str) -> Optional[dict]:
        """Extract health and damage system."""
        result = {}
        text_lower = text.lower()

        # Detect health track type
        if re.search(r"health\s*level|bruised|hurt|injured|wounded|mauled|crippled|incapacitated", text_lower):
            result["health_track_type"] = "levels"
        elif re.search(r"hit\s*points?|hp\b|damage\s*points?", text_lower):
            result["health_track_type"] = "hit_points"
        elif re.search(r"stress\s*(?:box|track)", text_lower):
            result["health_track_type"] = "stress_boxes"

        # Health levels (WoD style)
        health_levels = []
        level_patterns = [
            (r"bruised", 0, "No penalty"),
            (r"hurt", -1, "Minor injury"),
            (r"injured", -1, "Movement halved"),
            (r"wounded", -2, "Cannot run"),
            (r"mauled", -2, "Hobble only"),
            (r"crippled", -5, "Crawl only"),
            (r"incapacitated", None, "No actions possible"),
        ]
        for name, penalty, default_desc in level_patterns:
            if re.search(rf"\b{name}\b", text_lower):
                level = {"name": name.title()}
                if penalty is not None:
                    level["dice_penalty"] = penalty
                # Try to find actual penalty
                pen_match = re.search(rf"{name}[^.]*?(-\d+)", text_lower)
                if pen_match:
                    level["dice_penalty"] = int(pen_match.group(1))
                health_levels.append(level)

        if health_levels:
            result["health_levels"] = health_levels

        # Damage types
        damage_types = []
        if re.search(r"\bbashing\b", text_lower):
            damage_types.append({
                "name": "bashing",
                "description": "Non-lethal damage from blunt impacts"
            })
        if re.search(r"\blethal\b", text_lower):
            damage_types.append({
                "name": "lethal",
                "description": "Deadly damage from weapons"
            })
        if re.search(r"\baggravated\b", text_lower):
            damage_types.append({
                "name": "aggravated",
                "description": "Supernatural damage, difficult to heal"
            })
        if damage_types:
            result["damage_types"] = damage_types

        # Soak
        if re.search(r"\bsoak\b", text_lower):
            soak_stat = "stamina"
            stat_match = re.search(r"soak.*?(stamina|constitution|toughness)", text_lower)
            if stat_match:
                soak_stat = stat_match.group(1)
            result["soak"] = {
                "enabled": True,
                "stat_used": soak_stat
            }

        return result if result else None

    def _extract_equipment(self, text: str) -> Optional[dict]:
        """Extract weapon and armor tables."""
        result = {}
        lines = text.split('\n')

        # === RANGED WEAPONS ===
        # Format: Weapon Name\nDamage\nRange\nRate\nClip\nConceal
        ranged = []

        # Match weapon names that appear at start of line
        # Format in PDF: "Revolver, Lt. ( .38 Special)" or "Pistol, Hvy. (Colt .45)" etc.
        ranged_weapon_patterns = [
            r"^Revolver[,\s].*$",
            r"^Pistol[,\s].*$",
            r"^Rifle\s*\(.*$",
            r"^Shotgun\s*\(.*$",
            r"^SMG[,\s].*$",
            r"^Assault Rifle.*$",
            r"^Crossbow\s*$",
            r"^Compound Bow.*$",
            r"^Shuriken\s*$",
            r"^Taser\s*$",
            r"^X-5 Protector.*$",
        ]
        ranged_pattern = re.compile(
            r"(" + "|".join(ranged_weapon_patterns) + r")",
            re.IGNORECASE | re.MULTILINE
        )

        for m in ranged_pattern.finditer(text):
            name = m.group(1).strip()
            # Skip if this is a header row
            if name.lower() in ['type', 'damage', 'range', 'rate', 'clip', 'conceal']:
                continue
            pos = m.end()
            # Get next 5 non-empty lines for stats
            remaining = text[pos:pos+200].strip().split('\n')
            stats = [l.strip() for l in remaining if l.strip()][:5]
            if len(stats) >= 4:
                try:
                    # First stat is damage (number or "X (or special)")
                    damage = stats[0].split()[0] if stats[0] else "?"
                    range_val = stats[1].split()[0] if stats[1] else "?"
                    rate = stats[2].split()[0] if stats[2] else "?"
                    clip = stats[3] if stats[3] else "?"
                    # Validate that damage looks like a number
                    if damage.isdigit() or damage.startswith(('1','2','3','4','5','6','7','8','9')):
                        ranged.append({
                            "name": name,
                            "damage": damage,
                            "range": range_val,
                            "rate": rate,
                            "clip": clip,
                            "damage_type": "bashing" if "taser" in name.lower() else "lethal"
                        })
                except (IndexError, ValueError):
                    pass

        if ranged:
            result["ranged_weapons"] = ranged

        # === MELEE WEAPONS ===
        # Format: Weapon Name\nStrength + X [?|L]\nDifficulty\nConceal
        melee = []
        melee_pattern = re.compile(
            r"^(Sap|Club|Knife|Saber|Katana|Axe|Butterfly Knife|Nunchaku|Tonfa|Sai|Fighting Chain|Stake|Staff|Sword)\s*$",
            re.IGNORECASE | re.MULTILINE
        )

        for m in melee_pattern.finditer(text):
            name = m.group(1).strip()
            pos = m.end()
            # Get next line for damage
            remaining = text[pos:pos+100].strip().split('\n')
            if remaining:
                damage_line = remaining[0].strip()
                # Look for "Strength + X" pattern
                dmg_match = re.search(r"Strength\s*\+\s*(\d+)", damage_line, re.IGNORECASE)
                if dmg_match:
                    damage = f"Strength + {dmg_match.group(1)}"
                    damage_type = "bashing" if "?" in damage_line else "lethal" if "L" in damage_line else "varies"
                    melee.append({
                        "name": name.title(),
                        "damage": damage,
                        "damage_type": damage_type
                    })

        if melee:
            result["melee_weapons"] = melee

        # === ARMOR ===
        # Format: Class X (description)\nRating\nPenalty
        armor = []
        armor_pattern = re.compile(
            r"^Class\s+(One|Two|Three|Four|Five)\s*\(([^)]+)\)\s*$",
            re.IGNORECASE | re.MULTILINE
        )

        class_to_num = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}

        for m in armor_pattern.finditer(text):
            class_word = m.group(1).lower()
            description = m.group(2).strip()
            pos = m.end()
            # Get next 2 lines for rating and penalty
            remaining = text[pos:pos+50].strip().split('\n')
            stats = [l.strip() for l in remaining if l.strip()][:2]
            if len(stats) >= 2:
                try:
                    rating = int(stats[0])
                    penalty = int(stats[1])
                    armor.append({
                        "name": description,
                        "class": class_to_num.get(class_word, 0),
                        "rating": rating,
                        "penalty": penalty
                    })
                except (ValueError, IndexError):
                    pass

        if armor:
            result["armor"] = armor

        return result if result else None

    def _extract_magic(self, text: str) -> Optional[dict]:
        """Extract magic/spellcasting system mechanics - GENERIC extraction.

        This extractor uses system-agnostic patterns to detect:
        - Casting stats and mechanics
        - Spell schools/disciplines/spheres (any named groupings)
        - Resource pools (mana, points, etc.)
        - Backlash/failure systems
        - Difficulty modifiers

        The LLM refinement layer will contextualize and clean up results.
        """
        result = {"magic_system": {}}
        text_lower = text.lower()
        ms = result["magic_system"]

        # === DETECT CASTING STAT ===
        # Look for patterns like "roll X", "X dice pool", "use X to cast"
        casting_patterns = [
            (r"roll\s+(?:your\s+)?(\w+)\s+(?:as\s+)?(?:a\s+)?dice\s*pool", 1),
            (r"(\w+)\s+(?:rating|score)\s+(?:determines?|is\s+used\s+for)\s+(?:magic|casting|spells?)", 1),
            (r"cast(?:ing)?\s+(?:uses?|requires?)\s+(\w+)", 1),
            (r"(\w+)\s+roll\s+(?:for|to\s+cast)", 1),
        ]
        for pattern, group in casting_patterns:
            m = re.search(pattern, text_lower)
            if m:
                stat = m.group(group).strip()
                # Filter out common non-stat words
                if stat not in ("a", "the", "your", "their", "dice", "d10", "d20"):
                    ms["casting_stat"] = stat.title()
                    break

        # === DETECT CASTING MECHANIC ===
        if re.search(r"dice\s*pool|pool\s+of\s+dice", text_lower):
            ms["casting_mechanic"] = "dice pool"
        elif re.search(r"d20\s*\+|roll\s+d20", text_lower):
            ms["casting_mechanic"] = "d20 + modifier vs DC"
        elif re.search(r"2d6|pbta|powered\s+by\s+the\s+apocalypse", text_lower):
            ms["casting_mechanic"] = "2d6 + stat"
        elif re.search(r"spell\s*slots?|prepared\s+spells?", text_lower):
            ms["casting_mechanic"] = "spell slots"

        # === DETECT DIFFICULTY MODIFIERS ===
        # Generic pattern: "X magic/spells have difficulty Y" or "difficulty is X + Y"
        difficulty_mods = []
        diff_patterns = [
            # "coincidental magic's base difficulty is the highest Sphere used +3"
            (r"(\w+(?:\s+\w+)?)\s+magic(?:'s)?\s+(?:base\s+)?difficulty\s+(?:is|=)\s+(.+?)(?:\.|$)", True),
            # "+2 difficulty for casting in combat"
            (r"([+-]\d+)\s+difficulty\s+(?:for|when|if)\s+(.+?)(?:\.|$)", False),
            # "difficulty modifier of +2 when..."
            (r"difficulty\s+modifier\s+(?:of\s+)?([+-]?\d+)\s+(?:for|when|if)\s+(.+?)(?:\.|$)", False),
        ]
        for pattern, is_formula in diff_patterns:
            for m in re.finditer(pattern, text_lower):
                if is_formula:
                    difficulty_mods.append({
                        "condition": m.group(1).strip(),
                        "modifier": m.group(2).strip()[:100]
                    })
                else:
                    difficulty_mods.append({
                        "condition": m.group(2).strip()[:100],
                        "modifier": m.group(1).strip()
                    })
        if difficulty_mods:
            ms["difficulty_modifiers"] = difficulty_mods[:10]  # Limit

        # === DETECT SPELL SCHOOLS/DISCIPLINES ===
        # Look for capitalized terms that appear with ranked abilities
        # Pattern: "School/Sphere/Discipline Name" followed by ranked effects
        schools = []

        # Generic school detection - look for sections with bullet-pointed ranks
        # This finds headers followed by • ranked lists
        school_pattern = re.compile(
            r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*$\s*"  # Capitalized name on its own line
            r"(?:Specialties?:.*?\n)?"  # Optional specialties
            r".*?"  # Some content
            r"(•\s+[A-Z].*?)(?=\n[A-Z][a-z]+\s*$|\Z)",  # Ranked abilities
            re.MULTILINE | re.DOTALL
        )

        # Also detect via keyword patterns
        school_keywords = [
            r"sphere\s+of\s+(\w+)",
            r"(\w+)\s+sphere",
            r"school\s+of\s+(\w+)",
            r"(\w+)\s+school",
            r"discipline\s+of\s+(\w+)",
            r"(\w+)\s+discipline",
            r"domain\s+of\s+(\w+)",
            r"(\w+)\s+domain",
        ]
        found_schools = set()
        for pattern in school_keywords:
            for m in re.finditer(pattern, text_lower):
                name = m.group(1).strip()
                if len(name) > 2 and name not in ("the", "a", "an", "magic"):
                    found_schools.add(name.title())

        for school_name in found_schools:
            # Filter invalid terms
            if not _is_valid_term(school_name, min_len=4):
                continue
            # Count mentions to filter noise
            mentions = len(re.findall(rf"\b{school_name.lower()}\b", text_lower))
            if mentions >= 3:
                schools.append({"name": school_name, "mentions": mentions})

        if schools:
            # Sort by mentions, take top entries
            schools = sorted(schools, key=lambda x: -x["mentions"])[:15]
            for s in schools:
                del s["mentions"]  # Remove count from output
            ms["spell_schools"] = schools

        # === DETECT RESOURCE POOLS ===
        resource_pools = []

        # Generic resource patterns
        resource_patterns = [
            (r"\b(mana|quintessence|essence|power\s*points?|spell\s*points?|arcane\s*points?)\b", None),
            (r"(\w+)\s+pool\s+(?:of|for)\s+(?:magic|casting|spells?)", 1),
            (r"spend\s+(\w+)\s+(?:to|for)\s+(?:cast|magic|spell)", 1),
        ]
        found_resources = set()
        for pattern, group in resource_patterns:
            for m in re.finditer(pattern, text_lower):
                name = m.group(group) if group else m.group(1)
                name = name.strip()
                if _is_valid_term(name, min_len=4):
                    found_resources.add(name.title())

        for res_name in found_resources:
            res_entry = {"name": res_name}

            # Try to find max/recovery info
            max_match = re.search(
                rf"{res_name.lower()}.*?(?:max(?:imum)?|equal\s+to|up\s+to)\s+(?:your\s+)?(\w+)",
                text_lower
            )
            if max_match:
                res_entry["max_formula"] = max_match.group(1).title()

            # Try to find use effects
            use_match = re.search(
                rf"(?:spend|use)\s+{res_name.lower()}.*?(?:to|for)\s+(.+?)(?:\.|$)",
                text_lower
            )
            if use_match:
                res_entry["use_effects"] = [use_match.group(1).strip()[:100]]

            resource_pools.append(res_entry)

        # Willpower as a common spendable resource
        if re.search(r"spend\s+(?:a\s+)?(?:point\s+of\s+)?willpower", text_lower):
            wp_use = None
            wp_match = re.search(
                r"spend.*willpower.*?(?:to|for)\s+(.+?)(?:\.|$)",
                text_lower
            )
            if wp_match:
                wp_use = wp_match.group(1).strip()[:100]
            resource_pools.append({
                "name": "Willpower",
                "use_effects": [wp_use] if wp_use else ["spend for bonus"]
            })

        if resource_pools:
            ms["resource_pools"] = resource_pools

        # === DETECT BACKLASH/FAILURE SYSTEM ===
        # Look for named consequences of magical failure
        backlash_keywords = [
            "paradox", "backlash", "miscast", "wild magic", "surge",
            "corruption", "taint", "feedback", "blowback"
        ]
        for keyword in backlash_keywords:
            if re.search(rf"\b{keyword}\b", text_lower):
                backlash = {"name": keyword.title()}

                # Try to find trigger
                trigger_match = re.search(
                    rf"{keyword}.*?(?:occurs?|happens?|triggers?|when|if)\s+(.+?)(?:\.|$)",
                    text_lower
                )
                if trigger_match:
                    backlash["trigger"] = trigger_match.group(1).strip()[:100]

                # Try to find effects
                effect_match = re.search(
                    rf"{keyword}.*?(?:causes?|results?\s+in|leads?\s+to)\s+(.+?)(?:\.|$)",
                    text_lower
                )
                if effect_match:
                    backlash["effects"] = [{"effect": effect_match.group(1).strip()[:100]}]

                ms["backlash_system"] = backlash
                break

        # === DETECT FOCI/COMPONENTS ===
        if re.search(r"\bfoci\b|\bfocus\b|\bcomponent|material\s+component|verbal|somatic", text_lower):
            foci = {}

            if re.search(r"require[ds]?\s+(?:a\s+)?(?:focus|foci|component)", text_lower):
                foci["required"] = True

            exempt_match = re.search(
                r"(?:without|no\s+longer\s+need)\s+(?:a\s+)?(?:focus|foci|component).*?(?:at|when|if)\s+(.+?)(?:\.|$)",
                text_lower
            )
            if exempt_match:
                foci["exemption"] = exempt_match.group(1).strip()[:100]

            if foci:
                ms["foci"] = foci

        # === DETECT RITUAL/EXTENDED CASTING ===
        if re.search(r"ritual|extended\s+cast|longer\s+cast|casting\s+time", text_lower):
            ms["supports_rituals"] = True

        # Clean up empty magic_system
        if not ms:
            return None

        return result

    def _extract_clocks(self, text: str) -> Optional[dict]:
        """Extract clock definitions."""
        result = {"clocks": []}

        # Pattern: "Clock Name: X/Y" or "clock_id (0-10)"
        clock_pattern = re.compile(
            r"(?:^|\n)\s*(\w[\w\s]*?)\s*(?:clock)?\s*[:=]\s*(\d+)\s*/\s*(\d+)",
            re.IGNORECASE
        )
        for m in clock_pattern.finditer(text):
            result["clocks"].append({
                "name": m.group(1).strip(),
                "value": int(m.group(2)),
                "max": int(m.group(3)),
            })

        # Threshold triggers: "at 5: something happens"
        trigger_pattern = re.compile(
            r"(?:at|when|if)\s+(\d+)\s*[:=]\s*(.+?)(?:\n|$)",
            re.IGNORECASE
        )
        triggers = []
        for m in trigger_pattern.finditer(text):
            triggers.append({
                "threshold": int(m.group(1)),
                "effect": m.group(2).strip(),
            })
        if triggers:
            result["triggers"] = triggers

        return result if result["clocks"] else None

    def _extract_conditions(self, text: str) -> Optional[dict]:
        """Extract status conditions and effects."""
        result = {"conditions": []}

        # Generic and WoD-specific condition keywords
        condition_keywords = [
            # WoD conditions
            "bruised", "hurt", "injured", "wounded", "mauled", "crippled", "incapacitated",
            # Common RPG conditions
            "exposed", "hidden", "pursued", "cornered", "stunned", "prone",
            "grappled", "blinded", "deafened", "frightened", "poisoned",
            "detected", "alert", "suspicious", "hostile", "friendly",
            # Mage-specific
            "paradox", "quiet", "marauder", "nephandi",
        ]
        for keyword in condition_keywords:
            pattern = re.compile(
                rf"\b{keyword}\b\s*[:—–-]\s*(.+?)(?:\n|$)",
                re.IGNORECASE
            )
            for m in pattern.finditer(text):
                result["conditions"].append({
                    "name": keyword,
                    "effect": m.group(1).strip()[:200],
                })

        return result if result["conditions"] else None

    def _extract_calibration(self, text: str) -> Optional[dict]:
        """Extract difficulty calibration data."""
        result = {"presets": [], "difficulty_modifiers": []}

        # Standard format: "Easy: 3" or "Easy (3)"
        diff_pattern = re.compile(
            r"(easy|routine|standard|straightforward|challenging|difficult|hard|very\s*hard|nearly\s*impossible|trivial)\s*[:\(]?\s*(\d+)",
            re.IGNORECASE
        )
        for m in diff_pattern.finditer(text):
            result["presets"].append({
                "name": m.group(1).strip(),
                "value": int(m.group(2))
            })

        # WoD multi-line format: "Three\nEasy (description)"
        # Number words mapped to integers
        num_words = {
            "three": 3, "four": 4, "five": 5, "six": 6,
            "seven": 7, "eight": 8, "nine": 9, "ten": 10
        }
        diff_labels = ["easy", "routine", "standard", "straightforward", "challenging", "difficult", "hard"]

        # Look for pattern: number word on one line, difficulty label on next
        multiline_pattern = re.compile(
            r"^(Three|Four|Five|Six|Seven|Eight|Nine|Ten)\s*$\s*^(Easy|Routine|Standard|Straightforward|Challenging|Difficult|Hard)",
            re.IGNORECASE | re.MULTILINE
        )
        for m in multiline_pattern.finditer(text):
            num_word = m.group(1).lower()
            label = m.group(2).strip()
            if num_word in num_words:
                result["presets"].append({
                    "name": label,
                    "value": num_words[num_word]
                })

        # Degrees of success (also multi-line)
        success_pattern = re.compile(
            r"^(One|Two|Three|Four|Five)\s*$\s*^(Marginal|Moderate|Complete|Exceptional|Phenomenal)",
            re.IGNORECASE | re.MULTILINE
        )
        success_thresholds = []
        for m in success_pattern.finditer(text):
            num_word = m.group(1).lower()
            label = m.group(2).strip()
            word_to_num = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
            if num_word in word_to_num:
                success_thresholds.append({
                    "successes": word_to_num[num_word],
                    "label": label
                })
        if success_thresholds:
            result["success_thresholds"] = success_thresholds

        # General difficulty modifiers
        mod_pattern = re.compile(
            r"([+-]\d+)\s+(?:difficulty|modifier|penalty|bonus).*?(?:for|when|if)\s+(.+?)(?:\n|$)",
            re.IGNORECASE
        )
        for m in mod_pattern.finditer(text):
            result["difficulty_modifiers"].append({
                "modifier": m.group(1),
                "condition": m.group(2).strip()[:100]
            })

        return result if any(result.values()) else None

    def _extract_action_types(self, text: str) -> Optional[dict]:
        """Extract action type definitions."""
        result = {"action_types": []}

        # Common action patterns - expanded list
        action_keywords = [
            # Combat
            "attack", "defend", "dodge", "parry", "block", "grapple",
            # Movement
            "move", "run", "climb", "jump", "swim", "fly",
            # Social
            "persuade", "intimidate", "deceive", "negotiate", "seduce",
            # Investigation
            "examine", "search", "investigate", "research", "analyze",
            # Stealth
            "sneak", "hide", "steal", "pickpocket", "disguise",
            # Technical
            "hack", "repair", "craft", "drive", "pilot",
            # Magic
            "cast", "ritual", "effect", "rote",
        ]
        for keyword in action_keywords:
            pattern = re.compile(
                rf"\b{keyword}\b\s*[:—–-]\s*(.+?)(?:\n|$)",
                re.IGNORECASE
            )
            for m in pattern.finditer(text):
                result["action_types"].append({
                    "name": keyword,
                    "description": m.group(1).strip()[:200],
                })

        return result if result["action_types"] else None

    def _llm_extract(self, key: str, text: str) -> Optional[dict]:
        """Use LLM for deeper mechanical extraction."""
        from ..llm.gateway import load_schema

        prompt_name = f"systems_{key}"
        try:
            prompt_tmpl = self.registry.get_prompt(prompt_name)
            schema = load_schema(prompt_tmpl.schema_name)
        except (FileNotFoundError, KeyError, AttributeError) as e:
            logger.debug("No prompt/schema for %s: %s", key, e)
            return None

        # Truncate text to fit context
        if len(text) > 15000:
            text = text[:15000]

        try:
            response = self.gateway.run_structured(
                prompt=prompt_tmpl.template,
                input_data={"systems_text": text},
                schema=schema,
                options={"temperature": 0.2, "max_tokens": 4096},
            )
            return response.content
        except Exception as e:
            logger.warning("LLM extraction failed for %s: %s", key, e)
            return None

    def _merge_extractions(
        self,
        heuristic: Optional[dict],
        llm: Optional[dict]
    ) -> dict:
        """Merge heuristic and LLM extraction results."""
        if not heuristic:
            return llm or {}
        if not llm:
            return heuristic

        # LLM results take precedence, but merge lists
        merged = dict(llm)
        for key, value in heuristic.items():
            if key not in merged:
                merged[key] = value
            elif isinstance(value, list) and isinstance(merged[key], list):
                # Deduplicate merged lists
                existing = {json.dumps(x, sort_keys=True) for x in merged[key]}
                for item in value:
                    if json.dumps(item, sort_keys=True) not in existing:
                        merged[key].append(item)
            elif isinstance(value, dict) and isinstance(merged[key], dict):
                # Merge nested dicts
                for k, v in value.items():
                    if k not in merged[key]:
                        merged[key][k] = v
        return merged

    def _to_yaml(self, data: dict) -> str:
        """Convert dict to YAML string."""
        import yaml
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)

    def _load_raw_pages_for_segments(
        self,
        pages_dir: Path,
        segments: list[SegmentEntry],
    ) -> str:
        """Load raw page content for the page ranges covered by segments.

        This is preferred over summarized segment content because mechanical
        data (dice notations, tables, stat blocks) is often lost in summarization.
        """
        # Collect all page ranges from segments
        page_nums = set()
        for seg in segments:
            for p in range(seg.page_start, seg.page_end + 1):
                page_nums.add(p)

        # Load pages in order
        pages_content = []
        for page_num in sorted(page_nums):
            page_path = pages_dir / f"page_{page_num:04d}.md"
            if page_path.exists():
                pages_content.append(page_path.read_text())
            else:
                logger.debug("Page file not found: %s", page_path)

        if not pages_content:
            logger.warning("No raw pages found in %s", pages_dir)
            return ""

        return "\n\n---\n\n".join(pages_content)
