"""Shared utility functions for the ingest pipeline."""

import json
import re
from pathlib import Path
from typing import Any


def slugify(text: str) -> str:
    """Convert text to a URL/ID-safe slug.

    >>> slugify("The Neon Dragon Bar & Grill")
    'the_neon_dragon_bar_grill'
    """
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s_-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug.strip("_") or "untitled"


def count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def parse_page_range(spec: str, total_pages: int) -> list[int]:
    """Parse a page range specification into a list of page numbers.

    Supports: "1-5", "1,3,5", "1-3,7-9", "all".
    Page numbers are 1-based.

    >>> parse_page_range("1-3,5", 10)
    [1, 2, 3, 5]
    """
    if spec.strip().lower() == "all":
        return list(range(1, total_pages + 1))

    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = max(1, int(start_s.strip()))
            end = min(total_pages, int(end_s.strip()))
            pages.extend(range(start, end + 1))
        else:
            page = int(part)
            if 1 <= page <= total_pages:
                pages.append(page)

    return sorted(set(pages))


def write_stage_meta(stage_dir: Path, meta: dict) -> None:
    """Write stage metadata JSON file."""
    stage_dir.mkdir(parents=True, exist_ok=True)
    meta_path = stage_dir / "stage_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))


def read_stage_meta(stage_dir: Path) -> dict | None:
    """Read stage metadata JSON file, or None if not found."""
    meta_path = stage_dir / "stage_meta.json"
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text())


def write_manifest(path: Path, data: Any) -> None:
    """Write a JSON manifest file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def read_manifest(path: Path) -> Any:
    """Read a JSON manifest file."""
    return json.loads(path.read_text())


def write_markdown(path: Path, content: str, frontmatter: dict | None = None) -> None:
    """Write a markdown file with optional YAML frontmatter."""
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    parts = []
    if frontmatter:
        parts.append("---")
        parts.append(yaml.dump(frontmatter, default_flow_style=False).strip())
        parts.append("---")
        parts.append("")
    parts.append(content)
    path.write_text("\n".join(parts))


def read_markdown_with_frontmatter(path: Path) -> tuple[dict, str]:
    """Read a markdown file, splitting frontmatter from body.

    Returns (frontmatter_dict, body_text).
    """
    import yaml

    raw = path.read_text(encoding="utf-8")
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


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path
