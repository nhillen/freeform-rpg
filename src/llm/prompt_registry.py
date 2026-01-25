"""
Prompt Registry - Version-controlled prompt template management.

Handles loading, versioning, and pinning of prompt templates.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PromptTemplate:
    """A versioned prompt template."""
    id: str
    version: str
    template: str
    schema_name: str
    metadata: dict


@dataclass
class PromptVersion:
    """Version metadata for a prompt."""
    version: str
    path: str
    created_at: Optional[str] = None


class PromptRegistry:
    """
    Registry for prompt templates with version control.

    Prompts are stored as files: {prompt_id}_v{version}.txt
    Example: interpreter_v0.txt, planner_v1.txt
    """

    def __init__(self, prompts_dir: Optional[Path] = None):
        self.prompts_dir = prompts_dir or Path(__file__).parent.parent / "prompts"
        self._cache: dict[str, PromptTemplate] = {}
        self._pinned_versions: dict[str, dict[str, str]] = {}  # campaign_id -> {prompt_id -> version}

    def get_prompt(
        self,
        prompt_id: str,
        version: Optional[str] = None,
        campaign_id: Optional[str] = None
    ) -> PromptTemplate:
        """
        Get a prompt template by ID and version.

        Args:
            prompt_id: The prompt identifier (e.g., 'interpreter', 'planner')
            version: Specific version (e.g., 'v0'). If None, uses pinned or latest.
            campaign_id: Campaign to check for pinned version

        Returns:
            PromptTemplate with the template content
        """
        # Check for pinned version
        if version is None and campaign_id:
            pinned = self._pinned_versions.get(campaign_id, {})
            version = pinned.get(prompt_id)

        # Use latest if no version specified
        if version is None:
            versions = self.list_prompt_versions(prompt_id)
            if not versions:
                raise FileNotFoundError(f"No versions found for prompt: {prompt_id}")
            version = versions[-1].version

        # Check cache
        cache_key = f"{prompt_id}_{version}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Load from file
        file_path = self.prompts_dir / f"{prompt_id}_{version}.txt"
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt not found: {file_path}")

        with open(file_path) as f:
            template = f.read()

        # Parse metadata from template (optional header comments)
        metadata = self._parse_metadata(template)
        schema_name = metadata.get("schema", f"{prompt_id}_output")

        prompt = PromptTemplate(
            id=prompt_id,
            version=version,
            template=template,
            schema_name=schema_name,
            metadata=metadata
        )

        self._cache[cache_key] = prompt
        return prompt

    def list_prompt_versions(self, prompt_id: str) -> list[PromptVersion]:
        """List all available versions of a prompt."""
        versions = []
        pattern = re.compile(rf"^{prompt_id}_v(\d+)\.txt$")

        for path in self.prompts_dir.glob(f"{prompt_id}_v*.txt"):
            match = pattern.match(path.name)
            if match:
                version = f"v{match.group(1)}"
                versions.append(PromptVersion(
                    version=version,
                    path=str(path)
                ))

        # Sort by version number
        versions.sort(key=lambda v: int(v.version[1:]))
        return versions

    def pin_prompt_version(
        self,
        campaign_id: str,
        prompt_id: str,
        version: str
    ) -> None:
        """
        Pin a specific prompt version for a campaign.

        This allows different campaigns to use different prompt versions
        for A/B testing or gradual rollouts.
        """
        if campaign_id not in self._pinned_versions:
            self._pinned_versions[campaign_id] = {}

        self._pinned_versions[campaign_id][prompt_id] = version

    def get_pinned_versions(self, campaign_id: str) -> dict[str, str]:
        """Get all pinned versions for a campaign."""
        return self._pinned_versions.get(campaign_id, {}).copy()

    def _parse_metadata(self, template: str) -> dict:
        """Parse metadata from template header comments."""
        metadata = {}
        lines = template.split('\n')

        for line in lines:
            if not line.startswith('#'):
                break
            # Parse # key: value format
            match = re.match(r'^#\s*(\w+):\s*(.+)$', line)
            if match:
                metadata[match.group(1).lower()] = match.group(2).strip()

        return metadata

    def clear_cache(self) -> None:
        """Clear the prompt cache."""
        self._cache.clear()
