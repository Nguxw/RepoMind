from __future__ import annotations

from packages.wiki_engine.models import WikiPage


class WikiChecker:
    def check_page(self, page: WikiPage) -> list[str]:
        warnings = list(page.invalid_citation_warnings)
        for section in page.sections:
            for citation in section.citations:
                if citation.status != "valid":
                    warnings.append(f"{page.title}: invalid citation {citation.file_path}:{citation.start_line}-{citation.end_line}")
        return sorted(dict.fromkeys(warnings))
