"""LLM Refinement Layer for Systems Extraction.

Takes raw heuristic extraction results and uses LLM to:
1. Filter noise (remove obviously wrong items)
2. Fill gaps (add descriptions, complete partial data)
3. Structure properly (format to schema)
4. Extract detailed power boxes/ranked abilities
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# Prompts for refinement tasks
REFINE_MAGIC_PROMPT = """You are refining extracted magic system data from an RPG sourcebook.

## Raw Heuristic Extraction (may contain noise):
{raw_extraction}

## Source Text Excerpt:
{source_excerpt}

## Your Task:
Clean up and structure this magic system data. You should:

1. **Filter Noise**: Remove items that are clearly not magic schools/spheres (like "Various", "Additional", "Mental" - common English words that got picked up by pattern matching).

2. **Identify Real Schools/Spheres**: Keep only actual named magic categories from this game system. Look for capitalized terms that appear as section headers with ranked abilities.

3. **Extract Ranked Abilities**: For each school/sphere, find the ranked power levels (usually marked with bullets • or numbers 1-5). Each rank should have:
   - A name (the power/ability name)
   - Capabilities (what you CAN do at this rank)
   - Description (explanation of how it works)

4. **Sample Rotes/Effects**: Extract any named example spells or effects mentioned.

5. **Preserve Valid Data**: Keep casting_stat, casting_mechanic, difficulty_modifiers, resource_pools, backlash_system, and foci if they look correct.

Return a cleaned JSON object matching this structure:
{{
  "magic_system": {{
    "system_name": "Name of the magic system",
    "casting_stat": "Primary stat used for casting",
    "casting_mechanic": "How casting rolls work",
    "difficulty_modifiers": [
      {{"condition": "...", "modifier": "..."}}
    ],
    "spell_schools": [
      {{
        "name": "School Name",
        "description": "What this school governs",
        "specialties": ["specialty1", "specialty2"],
        "ranks": [
          {{
            "rank": 1,
            "name": "Ability Name",
            "description": "What you can do at this rank",
            "capabilities": ["specific thing 1", "specific thing 2"]
          }}
        ],
        "sample_rotes": [
          {{"name": "Rote Name", "rank_required": 3, "description": "What it does"}}
        ]
      }}
    ],
    "resource_pools": [...],
    "backlash_system": {{...}},
    "foci": {{...}}
  }}
}}

Only include schools that are clearly actual game mechanics, not common words.
Extract as much detail about ranked abilities as you can find in the source text.
"""

REFINE_STAT_SCHEMA_PROMPT = """You are refining extracted stat/attribute data from an RPG sourcebook.

## Raw Heuristic Extraction (may contain noise):
{raw_extraction}

## Source Text Excerpt:
{source_excerpt}

## Your Task:
Clean up and structure this character stat data. You should:

1. **Filter Noise**: Remove attribute categories that are clearly wrong (like "costs", "resonance", "health" - these are section headers, not attribute categories).

2. **Identify Real Attributes**: Keep only actual character attributes organized by category (Physical, Mental, Social or equivalent).

3. **Identify Real Abilities/Skills**: Keep only actual skills/abilities, organized by category if applicable.

4. **Special Traits**: Keep traits that are clearly game-specific pools or ratings (like Willpower, Arete, Quintessence) but remove noise (like "dice", "difficulty", "temporary").

5. **Backgrounds/Advantages**: Keep only valid background/advantage names.

Return a cleaned JSON object matching this structure:
{{
  "attributes": {{
    "physical": ["strength", "dexterity", "stamina"],
    "mental": ["intelligence", "wits", "perception"],
    "social": ["charisma", "manipulation", "appearance"]
  }},
  "abilities": {{
    "talents": ["alertness", "athletics", ...],
    "skills": ["drive", "firearms", ...],
    "knowledges": ["academics", "computer", ...]
  }},
  "special_traits": {{
    "willpower": {{"min": 1, "max": 10, "description": "..."}},
    ...
  }},
  "backgrounds": [
    {{"name": "Allies", "description": "..."}},
    ...
  ],
  "point_allocation": {{...}},
  "advancement_costs": {{...}}
}}

Only include items that are clearly actual game mechanics.
"""


class SystemsRefiner:
    """Refines raw heuristic extractions using LLM."""

    def __init__(self, llm_gateway):
        self.gateway = llm_gateway

    def refine_extraction(
        self,
        extractor_key: str,
        raw_extraction: dict,
        source_text: str,
        max_source_chars: int = 20000,
    ) -> Optional[dict]:
        """Refine a single extraction using LLM.

        Args:
            extractor_key: Which extractor produced this (e.g., "magic", "stat_schema")
            raw_extraction: Raw heuristic extraction result
            source_text: Original source text for context
            max_source_chars: Maximum characters of source text to include

        Returns:
            Refined extraction dict, or None on failure
        """
        prompt_map = {
            "magic": REFINE_MAGIC_PROMPT,
            "stat_schema": REFINE_STAT_SCHEMA_PROMPT,
        }

        prompt_template = prompt_map.get(extractor_key)
        if not prompt_template:
            logger.debug("No refinement prompt for extractor: %s", extractor_key)
            return raw_extraction  # Return as-is

        # Truncate source text
        source_excerpt = source_text[:max_source_chars]
        if len(source_text) > max_source_chars:
            source_excerpt += "\n\n[...truncated...]"

        # Format prompt
        prompt = prompt_template.format(
            raw_extraction=json.dumps(raw_extraction, indent=2),
            source_excerpt=source_excerpt,
        )

        # Minimal schema that accepts any object structure
        # This allows LLM to return flexible JSON while still using structured output
        permissive_schema = {
            "type": "object",
            "additionalProperties": True
        }

        try:
            response = self.gateway.run_structured(
                prompt=prompt,
                input_data={},
                schema=permissive_schema,
                options={"temperature": 0.2, "max_tokens": 8000},
            )

            # Response.content should already be parsed
            if isinstance(response.content, dict):
                logger.info("Successfully refined %s extraction", extractor_key)
                return response.content
            else:
                # Try to parse if it's a string
                result = self._parse_json_response(response.content)
                if result:
                    logger.info("Successfully refined %s extraction", extractor_key)
                    return result
                else:
                    logger.warning("Failed to parse LLM response for %s", extractor_key)
                    return raw_extraction

        except Exception as e:
            logger.warning("LLM refinement failed for %s: %s", extractor_key, e)
            return raw_extraction

    def refine_all(
        self,
        extractions: dict[str, dict],
        source_text: str,
    ) -> dict[str, dict]:
        """Refine all extractions.

        Args:
            extractions: Dict mapping extractor key to raw extraction
            source_text: Original source text

        Returns:
            Dict mapping extractor key to refined extraction
        """
        refined = {}
        for key, raw in extractions.items():
            refined[key] = self.refine_extraction(key, raw, source_text)
        return refined

    def _parse_json_response(self, response: str) -> Optional[dict]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        if not response:
            return None

        # Handle string responses
        if isinstance(response, str):
            text = response.strip()

            # Try to extract JSON from markdown code block
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                if end > start:
                    text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                if end > start:
                    text = text[start:end].strip()

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # Try to find JSON object in response
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    try:
                        return json.loads(text[start:end])
                    except json.JSONDecodeError:
                        pass
                return None

        # Already a dict
        if isinstance(response, dict):
            return response

        return None


def refine_systems_extraction(
    raw_extractions: dict[str, dict],
    source_text: str,
    llm_gateway,
) -> dict[str, dict]:
    """Convenience function to refine systems extractions.

    Args:
        raw_extractions: Dict from SystemsExtractor.extract()
        source_text: Original source text used for extraction
        llm_gateway: LLM gateway instance

    Returns:
        Refined extractions dict
    """
    refiner = SystemsRefiner(llm_gateway)
    return refiner.refine_all(raw_extractions, source_text)
