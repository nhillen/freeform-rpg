"""Pack Loader - Parses content pack directories into structured data.

A content pack is a directory with:
  pack.yaml           - manifest (name, version, layer, description, etc.)
  locations/*.md      - location lore files
  npcs/*.md           - NPC backstory/profile files
  factions/*.md       - faction/organization files
  culture/*.md        - world culture/flavor files
  items/*.md          - notable items/equipment files
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class PackManifest:
    """Parsed content pack manifest."""
    id: str
    name: str
    version: str = "1.0"
    description: str = ""
    layer: str = "adventure"
    author: str = ""
    dependencies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ContentFile:
    """A parsed markdown content file with frontmatter."""
    path: str
    file_type: str  # location, npc, faction, culture, item, general
    title: str
    body: str
    frontmatter: dict = field(default_factory=dict)
    entity_id: str = ""


@dataclass
class ValidationResult:
    """Result of pack validation."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    file_count: int = 0


# Directories that map to content types
TYPE_DIRS = {
    "locations": "location",
    "npcs": "npc",
    "factions": "faction",
    "culture": "culture",
    "items": "item",
}


class PackLoader:
    """Loads and validates content pack directories."""

    def load_pack(self, path: str | Path) -> tuple[PackManifest, list[ContentFile]]:
        """Load a content pack from a directory.

        Returns (manifest, list of content files).
        Raises ValueError if the pack is invalid.
        """
        pack_dir = Path(path)
        validation = self.validate_pack(pack_dir)
        if not validation.valid:
            raise ValueError(
                f"Invalid content pack at {pack_dir}: {'; '.join(validation.errors)}"
            )

        manifest = self._parse_manifest(pack_dir / "pack.yaml")
        content_files = self._scan_content_files(pack_dir, manifest.id)
        return manifest, content_files

    def validate_pack(self, path: str | Path) -> ValidationResult:
        """Validate a content pack directory structure."""
        pack_dir = Path(path)
        errors = []
        warnings = []
        file_count = 0

        if not pack_dir.is_dir():
            return ValidationResult(False, [f"Not a directory: {pack_dir}"])

        manifest_path = pack_dir / "pack.yaml"
        if not manifest_path.exists():
            return ValidationResult(False, [f"Missing pack.yaml in {pack_dir}"])

        # Validate manifest
        try:
            manifest = self._parse_manifest(manifest_path)
        except Exception as e:
            return ValidationResult(False, [f"Invalid pack.yaml: {e}"])

        if not manifest.id:
            errors.append("pack.yaml missing 'id' field")
        if not manifest.name:
            errors.append("pack.yaml missing 'name' field")

        # Scan for content files
        for subdir_name, file_type in TYPE_DIRS.items():
            subdir = pack_dir / subdir_name
            if subdir.is_dir():
                md_files = list(subdir.glob("*.md"))
                file_count += len(md_files)
                for md_file in md_files:
                    try:
                        self.parse_content_file(md_file, file_type)
                    except Exception as e:
                        warnings.append(f"Problem parsing {md_file.name}: {e}")

        # Also check for loose .md files in the root
        root_md = [f for f in pack_dir.glob("*.md") if f.name != "README.md"]
        file_count += len(root_md)

        if file_count == 0:
            warnings.append("No content files found")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            file_count=file_count
        )

    def list_packs(self, directory: str | Path) -> list[PackManifest]:
        """List all valid content packs in a directory."""
        packs_dir = Path(directory)
        manifests = []
        if not packs_dir.is_dir():
            return manifests

        for sub in sorted(packs_dir.iterdir()):
            if sub.is_dir() and (sub / "pack.yaml").exists():
                try:
                    manifest = self._parse_manifest(sub / "pack.yaml")
                    manifests.append(manifest)
                except Exception:
                    pass  # Skip invalid packs
        return manifests

    def parse_content_file(
        self,
        path: str | Path,
        file_type: str = "general"
    ) -> ContentFile:
        """Parse a single markdown content file with optional YAML frontmatter."""
        path = Path(path)
        raw = path.read_text(encoding="utf-8")

        frontmatter, body = _split_frontmatter(raw)

        # Derive title: frontmatter > first H1 > filename
        title = frontmatter.get("title", "")
        if not title:
            h1_match = re.match(r"^#\s+(.+)$", body, re.MULTILINE)
            if h1_match:
                title = h1_match.group(1).strip()
            else:
                title = path.stem.replace("_", " ").replace("-", " ").title()

        # Override file_type from frontmatter if present
        if "type" in frontmatter:
            file_type = frontmatter["type"]

        # Entity ID from frontmatter or filename
        entity_id = frontmatter.get("entity_id", path.stem.replace(" ", "_"))

        return ContentFile(
            path=str(path),
            file_type=file_type,
            title=title,
            body=body,
            frontmatter=frontmatter,
            entity_id=entity_id
        )

    def _parse_manifest(self, manifest_path: Path) -> PackManifest:
        """Parse a pack.yaml manifest file."""
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("pack.yaml must be a YAML mapping")

        return PackManifest(
            id=data.get("id", ""),
            name=data.get("name", ""),
            version=str(data.get("version", "1.0")),
            description=data.get("description", ""),
            layer=data.get("layer", "adventure"),
            author=data.get("author", ""),
            dependencies=data.get("dependencies", []),
            tags=data.get("tags", []),
            metadata={
                k: v for k, v in data.items()
                if k not in ("id", "name", "version", "description", "layer",
                             "author", "dependencies", "tags")
            }
        )

    def _scan_content_files(
        self,
        pack_dir: Path,
        pack_id: str
    ) -> list[ContentFile]:
        """Scan all content files in a pack directory."""
        files = []

        for subdir_name, file_type in TYPE_DIRS.items():
            subdir = pack_dir / subdir_name
            if subdir.is_dir():
                for md_file in sorted(subdir.glob("*.md")):
                    cf = self.parse_content_file(md_file, file_type)
                    files.append(cf)

        # Root-level .md files (general type)
        for md_file in sorted(pack_dir.glob("*.md")):
            if md_file.name in ("README.md",):
                continue
            cf = self.parse_content_file(md_file, "general")
            files.append(cf)

        return files


def _split_frontmatter(raw: str) -> tuple[dict, str]:
    """Split YAML frontmatter from markdown body.

    Returns (frontmatter_dict, body_text).
    """
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
                return fm, body
            except yaml.YAMLError:
                pass
    return {}, raw.strip()
