"""Guideline processing utilities.

This module is responsible for extracting text from the local Uganda HIV guidelines PDF
and chunking it into retrievable segments with page metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import html
import re

from pypdf import PdfReader


@dataclass(frozen=True)
class GuidelineChunk:
    """A chunk of guideline text with traceability metadata."""

    chunk_id: str
    text: str
    source_path: str
    page_number: int


def _normalize_whitespace(text: str) -> str:
    # Rationale: PDF text extraction often contains irregular spacing/newlines. Normalizing
    # reduces noise for both embeddings and LLM explanations.
    return " ".join(text.replace("\u00a0", " ").split())


def _split_into_paragraphs(text: str) -> List[str]:
    # Rationale: paragraph-like splits produce more coherent retrieval units than fixed
    # character windows, while keeping implementation lightweight.
    raw_parts = [p.strip() for p in text.split("\n")]
    return [p for p in raw_parts if p]


def chunk_page_text(
    page_text: str,
    *,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> List[str]:
    """Chunk a single page of extracted PDF text.

    Notes:
    - This intentionally uses a simple heuristic chunker for demo reliability.
    - Chunking is performed within a page to preserve page-level traceability.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be < chunk_size")

    normalized = _normalize_whitespace(page_text)
    if not normalized:
        return []

    paragraphs = _split_into_paragraphs(page_text)
    if not paragraphs:
        return []

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for para in paragraphs:
        para_norm = _normalize_whitespace(para)
        if not para_norm:
            continue

        # If a single paragraph is very long, fall back to fixed windows.
        if len(para_norm) > chunk_size:
            if current:
                chunks.append(" ".join(current).strip())
                current = []
                current_len = 0

            start = 0
            while start < len(para_norm):
                end = min(start + chunk_size, len(para_norm))
                chunks.append(para_norm[start:end].strip())
                if end == len(para_norm):
                    break
                start = max(end - overlap, 0)
            continue

        if current_len + len(para_norm) + 1 > chunk_size and current:
            chunks.append(" ".join(current).strip())

            # Overlap: re-seed next chunk with the tail of the previous chunk.
            if overlap > 0:
                prev = chunks[-1]
                tail = prev[-overlap:]
                current = [tail]
                current_len = len(tail)
            else:
                current = []
                current_len = 0

        current.append(para_norm)
        current_len += len(para_norm) + 1

    if current:
        chunks.append(" ".join(current).strip())

    # Final cleanup pass.
    return [_normalize_whitespace(c) for c in chunks if _normalize_whitespace(c)]


def extract_page_texts(
    pdf_path: Path,
    *,
    max_pages: Optional[int] = None,
) -> List[str]:
    """Extract text from each page of a PDF.

    max_pages:
        Optional cap used to speed up smoke tests and local iteration.
    """

    reader = PdfReader(str(pdf_path))
    page_texts: List[str] = []

    total_pages = len(reader.pages)
    limit = total_pages if max_pages is None else min(max_pages, total_pages)

    for i in range(limit):
        page = reader.pages[i]
        text = page.extract_text() or ""
        page_texts.append(text)

    return page_texts


def process_guidelines(
    pdf_path: Path,
    *,
    chunk_size: int = 1200,
    overlap: int = 200,
    max_pages: Optional[int] = None,
) -> List[GuidelineChunk]:
    """Process a guideline PDF into chunks with metadata."""

    if not pdf_path.exists():
        raise FileNotFoundError(f"Guideline PDF not found: {pdf_path}")

    page_texts = extract_page_texts(pdf_path, max_pages=max_pages)

    chunks: List[GuidelineChunk] = []
    for idx, page_text in enumerate(page_texts, start=1):
        for j, chunk_text in enumerate(
            chunk_page_text(page_text, chunk_size=chunk_size, overlap=overlap), start=1
        ):
            chunks.append(
                GuidelineChunk(
                    chunk_id=f"p{idx}_c{j}",
                    text=chunk_text,
                    source_path=str(pdf_path),
                    page_number=idx,
                )
            )

    return chunks


def iter_chunk_texts(chunks: Iterable[GuidelineChunk]) -> Iterable[str]:
    """Convenience iterator for embedding generation."""

    for c in chunks:
        yield c.text


# ---------------------------------------------------------------------------
# Markdown guideline processing
# ---------------------------------------------------------------------------

_ANCHOR_RE = re.compile(r"<a\s+id=['\"][^'\"]*['\"]\s*/?>", re.IGNORECASE)
_ANCHOR_CLOSE_RE = re.compile(r"</a>", re.IGNORECASE)
_SPECIAL_BLOCK_RE = re.compile(r"<::(.*?)::>", re.DOTALL)
_HTML_TABLE_TAG_RE = re.compile(r"</?(table|tr|td)\b[^>]*>", re.IGNORECASE)
# Only real HTML tags. "<[^>]+>" also matched "< 50 copies/mL and CD4 >" and deleted
# guideline thresholds (fix 10, G29).
_HTML_TAG_RE = re.compile(
    r"</?(?:a|b|i|u|em|strong|small|sup|sub|span|div|p|br|hr|img|font|center|h[1-6]|ul|ol|li|"
    r"table|thead|tbody|tfoot|tr|td|th|caption|col|colgroup|figure|figcaption)\b[^<>]*>",
    re.IGNORECASE,
)


def _strip_markdown_noise(text: str) -> str:
    """Remove anchor tags and image/logo placeholders that add no retrieval value."""
    text = _ANCHOR_RE.sub("", text)
    text = _ANCHOR_CLOSE_RE.sub("", text)

    def _special_block_repl(m: re.Match[str]) -> str:
        inner = (m.group(1) or "").strip()
        # Rationale: keep flowchart/text blocks (they contain clinical decision logic),
        # but drop pure image/logo placeholders that don't add retrieval value.
        # Note: some guideline conversions represent section headers as 'logo:' blocks
        # (e.g. '<::logo: [Unknown] MODULE 9 ...::>'). These are decorative and add
        # no retrieval value.
        # Some variants omit the bracketed description (e.g. 'logo: Module 21 ...').
        if re.match(r"^logo\s*:", inner, flags=re.IGNORECASE) or re.search(r":\s*logo\b", inner, re.IGNORECASE):
            return ""
        # Figure, photo and image blocks can hold guideline text (a WHO recommendation sits in
        # one), so keep their text and drop only the label (fix 10, G29).
        return re.sub(r"\s*:\s*(figure|photo|image|chemical structure)\b", "", inner, flags=re.IGNORECASE)

    text = _SPECIAL_BLOCK_RE.sub(_special_block_repl, text)

    # Rationale: some converted files contain malformed/orphan special-block markers
    # (e.g. a line with only '<::' and no matching '::>'). Drop any remaining
    # marker tokens after the structured substitution above.
    text = re.sub(r"<::\s*", "", text)
    text = re.sub(r"::>\s*", "", text)

    # Rationale: navigation/boilerplate tokens add no retrieval value and can
    # dominate similarity search for common queries.
    text = re.sub(
        r"(?im)^\s*(?:↑\s*)?Back to Table of Contents\s*$",
        "",
        text,
    )

    # Rationale: tables are real clinical content; keep cell text but drop HTML tags.
    text = re.sub(r"</tr\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<tr\s*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</td\s*>", "\t", text, flags=re.IGNORECASE)
    text = re.sub(r"<td\b[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</table\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<table\b[^>]*>", "", text, flags=re.IGNORECASE)

    # Drop any remaining HTML tags.
    text = _HTML_TAG_RE.sub("", text)

    # Decode entity encodings (e.g., &lt; and &gt;) into their unicode characters.
    text = html.unescape(text)
    return text


def extract_markdown_page_texts(
    md_path: Path,
    *,
    max_pages: Optional[int] = None,
) -> List[str]:
    """Split a Markdown file into page-equivalent segments using ``<!-- PAGE BREAK -->``."""

    raw = md_path.read_text(encoding="utf-8")
    # Rationale: the converted Markdown files use <!-- PAGE BREAK --> as the page delimiter,
    # mirroring the original PDF page boundaries.
    segments = re.split(r"<!--\s*PAGE\s+BREAK\s*-->", raw)

    # The content before the first PAGE BREAK is page 1.
    page_texts: List[str] = []
    limit = len(segments) if max_pages is None else min(max_pages, len(segments))
    for seg in segments[:limit]:
        cleaned = _strip_markdown_noise(seg).strip()
        page_texts.append(cleaned)

    return page_texts


SECTION_LIMIT = 900  # characters: about what the search model reads (256 word pieces), label included
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_SENTENCE_RE = re.compile(r"(?<=[.!?;])\s+")


def _fit(text: str, room: int) -> List[str]:
    """Sentences packed into parts of at most `room` characters; a longer sentence is cut by words."""
    parts: List[str] = []
    current = ""
    for sentence in _SENTENCE_RE.split(text):
        words = sentence.split()
        while words:
            piece = words.pop(0)
            while words and len(piece) + 1 + len(words[0]) <= room:
                piece += " " + words.pop(0)
            if current and len(current) + 1 + len(piece) <= room:
                current += " " + piece
            else:
                if current:
                    parts.append(current)
                current = piece
    if current:
        parts.append(current)
    return parts


def _section_pieces(label: str, lines: List[Tuple[int, str]], limit: int) -> List[Tuple[int, str]]:
    """One section's text as (page, text) pieces: paragraphs packed, tables by whole rows with
    the header row repeated, every piece starting with the section label."""
    head = f"{label}\n" if label else ""
    room = max(limit - len(head), 100)
    blocks: List[Tuple[str, List[Tuple[int, str]]]] = []
    for page, line in lines:
        if "\t" in line:  # a table row, as the cleaner leaves it (cells separated by tabs)
            row = " | ".join(c.strip() for c in line.split("\t") if c.strip())
            if row:
                if not blocks or blocks[-1][0] != "table":
                    blocks.append(("table", []))
                blocks[-1][1].append((page, row))
        elif line.strip():
            if not blocks or blocks[-1][0] != "para":
                blocks.append(("para", []))
            blocks[-1][1].append((page, line.strip()))
        elif blocks and blocks[-1][0] == "para":
            blocks.append(("break", []))

    pieces: List[Tuple[int, str]] = []
    text, first_page = "", 0
    for kind, items in blocks:
        if not items:
            continue
        if kind == "table" and len(items) > 1:
            if text:
                pieces.append((first_page, head + text))
                text = ""
            header = items[0][1]
            block, block_page = header, items[0][0]
            for page, row in items[1:]:
                if block != header and len(block) + 1 + len(row) > room:
                    pieces.append((block_page, head + block))
                    block, block_page = header, page
                block += "\n" + row
            pieces.append((block_page, head + block))
            continue
        for part in _fit(_normalize_whitespace(" ".join(t for _, t in items)), room):
            if text and len(text) + 1 + len(part) > room:
                pieces.append((first_page, head + text))
                text = ""
            if not text:
                text, first_page = part, items[0][0]
            else:
                text += " " + part
    if text:
        pieces.append((first_page, head + text))
    return pieces


def process_markdown_sections(
    md_path: Path,
    *,
    limit: int = SECTION_LIMIT,
    max_pages: Optional[int] = None,
) -> List[GuidelineChunk]:
    """Cut a guideline Markdown file along its own sections (Phase 2B fix 5b).

    A piece never crosses a heading and starts with its section path ("6.12 MONITORING > 6.12.3
    Frequency of VL"); paragraphs are packed up to `limit` characters, so the search model reads
    every word, and tables are split by whole rows with the header row repeated. It replaced
    1,200-character windows that cut sections and tables apart, 42% of them longer than the search
    model reads (G34). The page is the page the piece starts on.
    """
    if not md_path.exists():
        raise FileNotFoundError(f"Guideline Markdown file not found: {md_path}")
    segments = re.split(r"<!--\s*PAGE\s+BREAK\s*-->", md_path.read_text(encoding="utf-8"))
    segments = segments if max_pages is None else segments[:max_pages]
    file_prefix = md_path.stem.strip().lower().replace(" ", "-")

    sections: List[Tuple[str, List[Tuple[int, str]]]] = []
    path: List[Tuple[int, str]] = []
    lines: List[Tuple[int, str]] = []
    for page, segment in enumerate(segments, start=1):
        for line in _strip_markdown_noise(segment).split("\n"):
            m = _HEADING_RE.match(line.strip())
            if m:
                sections.append((" > ".join(t for _, t in path), lines))
                level, title = len(m.group(1)), _normalize_whitespace(m.group(2).replace("*", ""))
                path = [(lv, t) for lv, t in path if lv < level] + [(level, title)]
                lines = []
            else:
                lines.append((page, line))
    sections.append((" > ".join(t for _, t in path), lines))

    chunks: List[GuidelineChunk] = []
    for s, (label, section_lines) in enumerate(sections, start=1):
        for j, (page, text) in enumerate(_section_pieces(label, section_lines, limit), start=1):
            chunks.append(GuidelineChunk(chunk_id=f"{file_prefix}__s{s}_c{j}", text=text,
                                         source_path=str(md_path), page_number=page))
    return chunks


def process_markdown_guidelines(
    md_path: Path,
    *,
    chunk_size: int = 1200,
    overlap: int = 200,
    max_pages: Optional[int] = None,
) -> List[GuidelineChunk]:
    """Process a Markdown guideline file into chunks with metadata.

    Mirrors ``process_guidelines`` but reads ``.md`` files and splits on
    ``<!-- PAGE BREAK -->`` instead of using pypdf.
    """

    if not md_path.exists():
        raise FileNotFoundError(f"Guideline Markdown file not found: {md_path}")

    page_texts = extract_markdown_page_texts(md_path, max_pages=max_pages)

    # Rationale: derive a stable file-level prefix from the stem so chunk IDs
    # are unique across multiple Markdown source files.
    file_prefix = md_path.stem.strip().lower().replace(" ", "-")

    chunks: List[GuidelineChunk] = []
    for idx, page_text in enumerate(page_texts, start=1):
        for j, chunk_text in enumerate(
            chunk_page_text(page_text, chunk_size=chunk_size, overlap=overlap), start=1
        ):
            chunks.append(
                GuidelineChunk(
                    chunk_id=f"{file_prefix}__p{idx}_c{j}",
                    text=chunk_text,
                    source_path=str(md_path),
                    page_number=idx,
                )
            )

    return chunks
