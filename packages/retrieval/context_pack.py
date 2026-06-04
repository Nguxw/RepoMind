from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from packages.code_intelligence.models import CodeSymbol
from packages.repo_ingestion.models import RepoProfile
from packages.retrieval.vector_search import InMemoryVectorStore
from packages.wiki_engine.models import Citation, WikiPage


class SourceSnippet(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    content: str


class ContextPack(BaseModel):
    wiki_pages: list[WikiPage] = Field(default_factory=list)
    symbols: list[CodeSymbol] = Field(default_factory=list)
    snippets: list[SourceSnippet] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


def retrieve_context(profile: RepoProfile, wiki_pages: list[WikiPage], symbols: list[CodeSymbol], question: str, limit: int = 6) -> ContextPack:
    terms = _terms(question)
    vector_store = InMemoryVectorStore()
    vector_store.upsert_texts(
        [
            (f"wiki:{page.slug}", f"{page.title}\n{page.summary}\n" + "\n".join(section.content for section in page.sections), {"kind": "wiki", "slug": page.slug})
            for page in wiki_pages
        ]
        + [
            (f"symbol:{symbol.id}", f"{symbol.name} {symbol.type} {symbol.file_path} {symbol.signature}", {"kind": "symbol", "symbol_id": symbol.id})
            for symbol in symbols
        ]
    )
    vector_hits = vector_store.search(question, limit=limit)
    vector_page_slugs = [hit.metadata["slug"] for hit in vector_hits if hit.metadata.get("kind") == "wiki"]
    vector_symbol_ids = [hit.metadata["symbol_id"] for hit in vector_hits if hit.metadata.get("kind") == "symbol"]
    matched_pages = sorted(wiki_pages, key=lambda page: _score(page.title + " " + page.summary, terms), reverse=True)[:3]
    matched_pages = _merge_pages(matched_pages, [page for page in wiki_pages if page.slug in vector_page_slugs])[:3]
    matched_symbols = sorted(
        symbols,
        key=lambda symbol: _score(f"{symbol.name} {symbol.file_path} {symbol.signature}", terms),
        reverse=True,
    )[:limit]
    matched_symbols = _merge_symbols(matched_symbols, [symbol for symbol in symbols if symbol.id in vector_symbol_ids])[:limit]

    citations: list[Citation] = []
    for page in matched_pages:
        for section in page.sections:
            citations.extend(section.citations)
    citations.extend(Citation(file_path=symbol.file_path, start_line=symbol.start_line, end_line=symbol.end_line) for symbol in matched_symbols)
    citations = _dedupe_citations(citations)[:limit]
    snippets = [_read_snippet(profile.local_path, citation) for citation in citations]
    snippets = [snippet for snippet in snippets if snippet.content]
    return ContextPack(wiki_pages=matched_pages, symbols=matched_symbols, snippets=snippets, citations=citations)


def _merge_pages(primary: list[WikiPage], secondary: list[WikiPage]) -> list[WikiPage]:
    seen: set[str] = set()
    merged: list[WikiPage] = []
    for page in [*secondary, *primary]:
        if page.slug in seen:
            continue
        seen.add(page.slug)
        merged.append(page)
    return merged


def _merge_symbols(primary: list[CodeSymbol], secondary: list[CodeSymbol]) -> list[CodeSymbol]:
    seen: set[str] = set()
    merged: list[CodeSymbol] = []
    for symbol in [*secondary, *primary]:
        if symbol.id in seen:
            continue
        seen.add(symbol.id)
        merged.append(symbol)
    return merged


def _terms(question: str) -> list[str]:
    return [part for part in question.lower().replace("_", " ").split() if len(part) >= 2]


def _score(text: str, terms: list[str]) -> int:
    lowered = text.lower()
    return sum(lowered.count(term) for term in terms)


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[tuple[str, int, int]] = set()
    result: list[Citation] = []
    for citation in citations:
        key = (citation.file_path, citation.start_line, citation.end_line)
        if key in seen:
            continue
        seen.add(key)
        result.append(citation)
    return result


def _read_snippet(repo_root: str, citation: Citation, context_lines: int = 4) -> SourceSnippet:
    path = Path(repo_root) / citation.file_path
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return SourceSnippet(file_path=citation.file_path, start_line=citation.start_line, end_line=citation.end_line, content="")
    start = max(1, citation.start_line - context_lines)
    end = min(len(lines), citation.end_line + context_lines)
    content = "\n".join(f"{line_number}: {lines[line_number - 1]}" for line_number in range(start, end + 1))
    return SourceSnippet(file_path=citation.file_path, start_line=start, end_line=end, content=content)
