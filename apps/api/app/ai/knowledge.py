"""The knowledge library of each console AI agent (slice C3a).

A library holds documents (files, links, notes of the team, an approved summary). The text of a
document is cut into chunks; an agent searches them with the tool `search_library` and gets the
few chunks that match, with the document, its source and the section, so every claim can name a
source. Notes and approved summaries are small and always go into the agent's prompt.

Search is by words (PostgreSQL full text search, which works for Hebrew and English). Search by
meaning is built behind a switch: see embeddings.py. The database functions do the access checks;
see migration 0147."""

import io
import json
import re
import zipfile
from html.parser import HTMLParser
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import embeddings

MAX_CHUNK = 1200  # characters
MAX_CHUNKS = 800
MAX_TEXT = 400_000  # characters of one document
ALWAYS_LIMIT = 6000  # characters of notes and summaries that go into every prompt
HITS = 6
KINDS = ("file", "link", "note", "summary")
COUNTRIES = ("il", "us", "eu", "all")

_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_WORD = re.compile(r"[^\W_]+")
_STOPWORDS = frozenset(
    {"the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "on", "at", "by"}
    | {"it", "be", "as", "what", "how", "do", "does", "can", "i", "we", "you"}
    | {"את", "של", "על", "עם", "זה", "מה", "איך", "האם", "הוא", "היא", "לא", "או", "גם", "כל"}
    | {"אני", "אנחנו", "יש", "אם"}
)
# One-letter Hebrew prefixes (the, in, to, from, and, as, that); the bare word is tried too.
_HEBREW_PREFIXES = "הבלמוכש"


class UnsupportedFile(ValueError):
    pass


def chunks_of(body: str) -> list[dict[str, str | None]]:
    """The text cut at headings and then at paragraphs into chunks of at most MAX_CHUNK
    characters, each with the heading of its section (the section a source is cited by)."""
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in body.splitlines():
        match = _HEADING.match(line)
        if match:
            sections.append((match.group(1), []))
        else:
            sections[-1][1].append(line)
    chunks: list[dict[str, str | None]] = []
    for heading, lines in sections:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", "\n".join(lines)) if p.strip()]
        current = ""
        for paragraph in paragraphs:
            while len(paragraph) > MAX_CHUNK:  # a very long paragraph: cut near a sentence end
                cut = paragraph.rfind(". ", 0, MAX_CHUNK)
                cut = cut + 1 if cut > MAX_CHUNK // 2 else MAX_CHUNK
                if current:
                    chunks.append({"heading": heading, "content": current})
                    current = ""
                chunks.append({"heading": heading, "content": paragraph[:cut].strip()})
                paragraph = paragraph[cut:].strip()
            if current and len(current) + len(paragraph) + 2 > MAX_CHUNK:
                chunks.append({"heading": heading, "content": current})
                current = ""
            current = f"{current}\n\n{paragraph}" if current else paragraph
        if current:
            chunks.append({"heading": heading, "content": current})
    return [c for c in chunks if c["content"]][:MAX_CHUNKS]


def words_query(question: str) -> str | None:
    """A `to_tsquery` text that matches any of the question's meaningful words (and prefixes of
    longer ones), or None when there is nothing to search for."""
    terms: list[str] = []
    for word in _WORD.findall(question.lower()):
        if len(word) < 2 or word in _STOPWORDS:
            continue
        variants = [word]
        if len(word) > 3 and word[0] in _HEBREW_PREFIXES:
            variants.append(word[1:])
        for variant in variants:
            term = f"{variant}:*" if len(variant) >= 3 else variant
            if term not in terms:
                terms.append(term)
    return " | ".join(terms[:24]) or None


def _hit(row: Any) -> dict[str, Any]:
    return {
        "document": row["title"],
        "source_url": row["source_url"],
        "source_org": row["source_org"],
        "country": row["country"],
        "last_reviewed": row["reviewed_on"].isoformat() if row["reviewed_on"] else None,
        "section": row["heading"],
        "text": row["content"],
        "_key": (row["document_id"], row["heading"], row["content"][:80]),
    }


def search(
    db: Session, agent: str | None, question: str, limit: int = HITS
) -> list[dict[str, Any]]:
    """The chunks that best answer the question, from the library of one agent (None: every
    library). By words; by meaning too once the embeddings provider is switched on."""
    hits: list[dict[str, Any]] = []
    query = words_query(question)
    if query:
        rows = db.execute(
            text("SELECT * FROM app.platform_kb_search(:agent, :query, :limit)"),
            {"agent": agent, "query": query, "limit": limit},
        ).mappings()
        hits = [_hit(r) for r in rows]
    provider = embeddings.provider()
    if provider and db.execute(text("SELECT app.platform_kb_vector_ready()")).scalar():
        try:
            [vector] = provider.embed([question], query=True)
        except embeddings.EmbeddingsUnavailable:
            vector = None
        if vector:
            rows = db.execute(
                text("SELECT * FROM app.platform_kb_vector_search(:agent, :vector, :limit)"),
                {"agent": agent, "vector": embeddings.as_sql(vector), "limit": limit},
            ).mappings()
            seen = {h["_key"] for h in hits}
            hits += [h for h in map(_hit, rows) if h["_key"] not in seen]
    for h in hits:
        del h["_key"]
    return hits[:limit]


def always_block(db: Session, agent: str) -> str:
    """The team's notes and approved summaries for this agent, ready for the system prompt."""
    rows = db.execute(
        text("SELECT kind, title, body FROM app.platform_kb_always(:agent)"), {"agent": agent}
    ).mappings()
    parts: list[str] = []
    used = 0
    for r in rows:
        label = "Approved summary" if r["kind"] == "summary" else "Note from the team"
        block = f"[{label}: {r['title']}]\n{r['body'].strip()}"
        if used + len(block) > ALWAYS_LIMIT:
            break
        parts.append(block)
        used += len(block)
    if not parts:
        return ""
    return (
        "The MyBiz team keeps these for you. Follow them; they win over what you remember.\n\n"
        + "\n\n".join(parts)
    )


def save(
    db: Session,
    *,
    doc_id: UUID | None,
    agent: str,
    kind: str,
    title: str,
    url: str | None,
    org: str | None,
    country: str | None,
    reviewed_on: Any,
    enabled: bool,
    body: str | None,
    note: str | None,
) -> UUID:
    """Creates a document or saves a change to it (a changed text is a new version). Returns its
    id. The chunks are embedded when the embeddings provider is on."""
    chunks = chunks_of(body) if body else []
    saved = db.execute(
        text(
            "SELECT app.platform_kb_save(:id, :agent, :kind, :title, :url, :org, :country,"
            " :reviewed, :enabled, :body, :note, CAST(:chunks AS jsonb))"
        ),
        {
            "id": doc_id,
            "agent": agent,
            "kind": kind,
            "title": title,
            "url": url,
            "org": org,
            "country": country,
            "reviewed": reviewed_on,
            "enabled": enabled,
            "body": body,
            "note": note,
            "chunks": json.dumps(chunks, ensure_ascii=False),
        },
    ).scalar_one()
    embed_pending(db)
    return saved


def embed_pending(db: Session, limit: int = 200) -> int:
    """Embeds the chunks that have no embedding yet; 0 and nothing happens while the provider is
    off. A provider error is not fatal: the words search keeps working, and the next save or the
    reindex button tries again."""
    provider = embeddings.provider()
    if provider is None or not db.execute(text("SELECT app.platform_kb_vector_ready()")).scalar():
        return 0
    rows = (
        db.execute(
            text("SELECT * FROM app.platform_kb_pending_embeddings(:limit)"), {"limit": limit}
        )
        .mappings()
        .all()
    )
    if not rows:
        return 0
    try:
        vectors = provider.embed([r["content"] for r in rows], query=False)
    except embeddings.EmbeddingsUnavailable:
        return 0
    by_document: dict[UUID, list[dict[str, Any]]] = {}
    for row, vector in zip(rows, vectors, strict=True):
        by_document.setdefault(row["document_id"], []).append(
            {"ordinal": row["ordinal"], "vector": embeddings.as_sql(vector)}
        )
    for document, items in by_document.items():
        db.execute(
            text("SELECT app.platform_kb_set_embeddings(:doc, CAST(:items AS jsonb))"),
            {"doc": document, "items": json.dumps(items)},
        )
    return len(rows)


# --- Reading an uploaded file -----------------------------------------------------------------


class _Plain(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in ("p", "div", "br", "li", "tr", "section", "article"):
            self.parts.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "windows-1255", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnsupportedFile("unreadable_file")  # pragma: no cover (latin-1 decodes any bytes)


def _docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read("word/document.xml").decode("utf-8")
    except (zipfile.BadZipFile, KeyError) as error:
        raise UnsupportedFile("unreadable_file") from error
    xml = re.sub(r"</w:p>", "\n\n", xml)
    xml = re.sub(r"<w:(tab|br)\s*/>", " ", xml)
    runs = re.sub(r"<(?!/?w:t[ >])[^>]+>", "", xml)  # keep only the text runs and the breaks
    runs = re.sub(r"</?w:t[^>]*>", "", runs)
    return (
        runs.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
    )


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    except (PyPdfError, ValueError, KeyError) as error:
        raise UnsupportedFile("unreadable_file") from error


def extract_text(filename: str, data: bytes) -> str:
    """The text of an uploaded file: plain text, Markdown, HTML, Word (.docx) or PDF."""
    name = filename.lower()
    if name.endswith((".txt", ".md", ".markdown")):
        body = _decode(data)
    elif name.endswith((".html", ".htm")):
        parser = _Plain()
        parser.feed(_decode(data))
        body = "".join(parser.parts)
    elif name.endswith(".docx"):
        body = _docx_text(data)
    elif name.endswith(".pdf"):
        body = _pdf_text(data)
    else:
        raise UnsupportedFile("unsupported_file")
    body = re.sub(r"[ \t]+\n", "\n", body).replace("\r\n", "\n")
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    if not body:
        raise UnsupportedFile("empty_file")
    if len(body) > MAX_TEXT:
        raise UnsupportedFile("file_too_long")
    return body
