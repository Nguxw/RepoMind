from __future__ import annotations

from pathlib import Path

from packages.wiki_engine.models import Citation, WikiPage


class CitationBinder:
    def bind_page(self, page: WikiPage, repo_root: str | Path, file_paths: list[str]) -> WikiPage:
        known_files = set(file_paths)
        line_counts = {path: _line_count(Path(repo_root) / path) for path in known_files}
        warnings: list[str] = []

        for section in page.sections:
            fixed: list[Citation] = []
            for citation in section.citations:
                if citation.file_path not in known_files:
                    fixed.append(citation.model_copy(update={"status": "invalid", "message": "File does not exist in imported repository."}))
                    warnings.append(f"{citation.file_path}:{citation.start_line}-{citation.end_line} points to a missing file")
                    continue
                max_line = line_counts.get(citation.file_path, 1)
                start_line = max(1, min(citation.start_line, max_line))
                end_line = max(start_line, min(citation.end_line, max_line))
                fixed.append(citation.model_copy(update={"start_line": start_line, "end_line": end_line, "status": "valid", "message": None}))
            section.citations = fixed
        page.invalid_citation_warnings = warnings
        return page


def first_citation_for_file(repo_root: str | Path, file_path: str, max_lines: int = 40) -> Citation:
    count = _line_count(Path(repo_root) / file_path)
    return Citation(file_path=file_path, start_line=1, end_line=min(max(1, count), max_lines))


def _line_count(path: Path) -> int:
    try:
        return max(1, len(path.read_text(encoding="utf-8", errors="ignore").splitlines()))
    except OSError:
        return 1
