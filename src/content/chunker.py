"""Chunker - Splits markdown content files into indexed chunks.

Chunking strategy:
  - H1 (#) becomes the overview chunk for the file
  - H2 (##) become individual chunks (primary split boundary)
  - H3+ (###, ####) merge into their parent H2 chunk
  - Each chunk inherits the file's frontmatter metadata
  - Chunk IDs are namespaced: {pack_id}:{file_id}:{section_slug}
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from .pack_loader import ContentFile


@dataclass
class ContentChunk:
    """A single indexed chunk of content."""
    id: str  # {pack_id}:{file_id}:{section_slug}
    pack_id: str
    file_path: str
    section_title: str
    content: str
    chunk_type: str  # location, npc, faction, culture, item, general
    entity_refs: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    token_estimate: int = 0


class Chunker:
    """Splits ContentFile objects into ContentChunk objects."""

    def chunk_file(
        self,
        content_file: ContentFile,
        pack_id: str
    ) -> list[ContentChunk]:
        """Split a content file into chunks.

        Returns a list of ContentChunk objects, one per major section.
        """
        file_id = _slugify(content_file.entity_id or content_file.title)
        body = content_file.body
        sections = _split_by_headers(body)

        chunks = []
        base_tags = list(content_file.frontmatter.get("tags", []))
        base_tags.append(content_file.file_type)
        entity_refs = list(content_file.frontmatter.get("entity_refs", []))
        if content_file.entity_id:
            entity_refs.append(content_file.entity_id)
        # Deduplicate
        entity_refs = list(dict.fromkeys(entity_refs))
        base_tags = list(dict.fromkeys(base_tags))

        for section in sections:
            section_slug = _slugify(section["title"]) if section["title"] else "overview"
            chunk_id = f"{pack_id}:{file_id}:{section_slug}"

            # Merge frontmatter metadata with section-level info
            metadata = dict(content_file.frontmatter)
            metadata.pop("tags", None)
            metadata.pop("entity_refs", None)
            metadata["file_type"] = content_file.file_type
            metadata["source_file"] = content_file.path

            content = section["content"].strip()
            if not content:
                continue

            chunk = ContentChunk(
                id=chunk_id,
                pack_id=pack_id,
                file_path=content_file.path,
                section_title=section["title"] or content_file.title,
                content=content,
                chunk_type=content_file.file_type,
                entity_refs=entity_refs.copy(),
                tags=base_tags.copy(),
                metadata=metadata,
                token_estimate=estimate_tokens(content)
            )
            chunks.append(chunk)

        return chunks

    def chunk_files(
        self,
        content_files: list[ContentFile],
        pack_id: str
    ) -> list[ContentChunk]:
        """Chunk multiple content files."""
        all_chunks = []
        for cf in content_files:
            all_chunks.extend(self.chunk_file(cf, pack_id))
        return all_chunks


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~0.75 tokens per word for English text."""
    word_count = len(text.split())
    return int(word_count * 1.33)


def _slugify(text: str) -> str:
    """Convert text to a slug suitable for chunk IDs."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s_-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug.strip("_") or "untitled"


def _split_by_headers(body: str) -> list[dict]:
    """Split markdown body into sections by H1/H2 headers.

    H3+ headers are merged into their parent H2 section.

    Returns list of {"title": str, "content": str, "level": int}.
    """
    lines = body.split("\n")
    sections = []
    current_title = ""
    current_level = 0
    current_lines = []

    for line in lines:
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)

        if header_match:
            level = len(header_match.group(1))
            title = header_match.group(2).strip()

            if level <= 2:
                # H1 or H2: start a new section
                if current_lines or current_title:
                    sections.append({
                        "title": current_title,
                        "content": "\n".join(current_lines),
                        "level": current_level
                    })
                current_title = title
                current_level = level
                current_lines = []
            else:
                # H3+: merge into current section (include the header line)
                current_lines.append(line)
        else:
            current_lines.append(line)

    # Flush remaining content
    if current_lines or current_title:
        sections.append({
            "title": current_title,
            "content": "\n".join(current_lines),
            "level": current_level
        })

    # If no headers were found, return the whole body as one chunk
    if not sections:
        sections.append({
            "title": "",
            "content": body,
            "level": 0
        })

    return sections
