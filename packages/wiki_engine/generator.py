from __future__ import annotations

from pathlib import Path

from packages.code_intelligence.models import CodeSymbol, RepoGraph
from packages.model_gateway.base import BaseModelClient
from packages.repo_ingestion.models import RepoProfile
from packages.wiki_engine.citation_binder import CitationBinder, first_citation_for_file
from packages.wiki_engine.checker import WikiChecker
from packages.wiki_engine.diagram_generator import DiagramGenerator
from packages.wiki_engine.models import Citation, WikiPage, WikiSection
from packages.wiki_engine.planner import WikiPageSpec, WikiPlanner


class WikiGenerator:
    def __init__(self, model_client: BaseModelClient) -> None:
        self.model_client = model_client
        self.planner = WikiPlanner()
        self.citation_binder = CitationBinder()
        self.diagram_generator = DiagramGenerator()
        self.checker = WikiChecker()

    async def generate(self, profile: RepoProfile, file_paths: list[str], symbols: list[CodeSymbol], graph: RepoGraph) -> list[WikiPage]:
        pages: list[WikiPage] = []
        for spec in self.planner.plan(profile):
            page = self._generate_page(spec, profile, file_paths, symbols, graph)
            page = self.citation_binder.bind_page(page, profile.local_path, file_paths)
            page.invalid_citation_warnings = self.checker.check_page(page)
            pages.append(page)
        return pages

    def _generate_page(self, spec: WikiPageSpec, profile: RepoProfile, file_paths: list[str], symbols: list[CodeSymbol], graph: RepoGraph) -> WikiPage:
        primary_files = _primary_files(profile, file_paths)
        citations = [first_citation_for_file(profile.local_path, path) for path in primary_files[:3]]
        symbol_summary = _symbol_summary(symbols)

        if spec.slug == "overview":
            sections = [
                WikiSection(
                    heading="Repository shape",
                    content=(
                        f"{profile.name} contains {profile.file_count} indexed files. "
                        f"Detected languages: {_join(profile.languages)}. Frameworks: {_join(profile.frameworks)}."
                    ),
                    citations=citations[:2],
                ),
                WikiSection(
                    heading="Primary evidence",
                    content=f"Important files include {_join(profile.important_files[:8])}.",
                    citations=citations,
                ),
            ]
            diagrams = [self.diagram_generator.architecture_diagram(profile)]
        elif spec.slug == "architecture":
            sections = [
                WikiSection(
                    heading="Architecture map",
                    content=(
                        f"The current architecture is inferred from important directories {_join(profile.important_directories)} "
                        f"and {len(graph.edges)} RepoKG edges."
                    ),
                    citations=citations,
                )
            ]
            diagrams = [self.diagram_generator.architecture_diagram(profile), self.diagram_generator.dependency_diagram(graph)]
        elif spec.slug == "core-modules":
            sections = [
                WikiSection(
                    heading="Core symbols",
                    content=symbol_summary or "No high-level code symbols were extracted from the supported languages yet.",
                    citations=_citations_from_symbols(profile.local_path, symbols[:6]),
                )
            ]
            diagrams = [self.diagram_generator.dependency_diagram(graph)]
        elif spec.slug == "important-files":
            sections = [
                WikiSection(
                    heading="Files to inspect first",
                    content="\n".join(f"- {path}" for path in profile.important_files[:12]) or "No important files were detected.",
                    citations=citations,
                )
            ]
            diagrams = []
        elif spec.slug == "how-to-run":
            sections = [
                WikiSection(
                    heading="Setup clues",
                    content=_how_to_run(profile),
                    citations=[first_citation_for_file(profile.local_path, path) for path in profile.dependency_files[:4]],
                )
            ]
            diagrams = []
        elif spec.slug == "reading-guide":
            sections = [
                WikiSection(
                    heading="Recommended order",
                    content=_reading_guide(profile, symbols),
                    citations=citations,
                )
            ]
            diagrams = []
        else:
            sections = [
                WikiSection(
                    heading="Evidence-backed notes",
                    content=_ml_page_content(spec.title, profile, symbols),
                    citations=citations or _citations_from_symbols(profile.local_path, symbols[:3]),
                )
            ]
            diagrams = [self.diagram_generator.dependency_diagram(graph)]

        return WikiPage(
            slug=spec.slug,
            title=spec.title,
            summary=f"{spec.title} for {profile.name}, generated from RepoProfile, symbols, RepoKG, and source citations.",
            sections=sections,
            diagrams=diagrams,
            related_pages=_related_pages(spec.slug),
        )


def _primary_files(profile: RepoProfile, file_paths: list[str]) -> list[str]:
    candidates = [
        *profile.readme_files,
        *profile.entrypoints,
        *profile.dependency_files,
        *profile.config_files,
        *profile.important_files,
        *file_paths[:3],
    ]
    return list(dict.fromkeys(path for path in candidates if path in set(file_paths)))


def _symbol_summary(symbols: list[CodeSymbol]) -> str:
    major = [symbol for symbol in symbols if symbol.type in {"class", "function"}][:12]
    return "\n".join(f"- `{symbol.name}` ({symbol.type}) in `{symbol.file_path}:{symbol.start_line}`" for symbol in major)


def _citations_from_symbols(repo_root: str, symbols: list[CodeSymbol]) -> list[Citation]:
    citations: list[Citation] = []
    for symbol in symbols:
        citations.append(Citation(file_path=symbol.file_path, start_line=symbol.start_line, end_line=symbol.end_line))
    return citations


def _how_to_run(profile: RepoProfile) -> str:
    managers = set(profile.package_managers)
    lines: list[str] = []
    if "npm" in managers or "pnpm" in managers or "yarn" in managers:
        lines.append("Install JavaScript dependencies using the detected package manager, then inspect `package.json` scripts.")
    if {"pip", "poetry", "pipenv", "conda"} & managers:
        lines.append("Create a Python environment and install dependencies from the detected dependency files.")
    if profile.entrypoints:
        lines.append(f"Likely entrypoints: {_join(profile.entrypoints)}.")
    if not lines:
        lines.append("No explicit runtime entrypoint was detected; start with README and dependency files.")
    return " ".join(lines)


def _reading_guide(profile: RepoProfile, symbols: list[CodeSymbol]) -> str:
    steps = [
        "1. Read the README or top-level documentation for project intent.",
        "2. Inspect dependency and config files to understand runtime assumptions.",
        "3. Open likely entrypoints and follow imports into core modules.",
    ]
    if symbols:
        steps.append("4. Use the symbol index to jump to classes and functions that define the main behavior.")
    if profile.test_files:
        steps.append("5. Read tests to confirm expected behavior and integration points.")
    return "\n".join(steps)


def _ml_page_content(title: str, profile: RepoProfile, symbols: list[CodeSymbol]) -> str:
    lower_title = title.lower()
    matching = [
        symbol for symbol in symbols
        if any(keyword in symbol.name.lower() or keyword in symbol.file_path.lower() for keyword in lower_title.split())
    ][:8]
    if matching:
        return "\n".join(f"- `{symbol.name}` in `{symbol.file_path}`" for symbol in matching)
    return f"{title} is inferred from ML-related dependencies, entrypoints, and source structure."


def _related_pages(slug: str) -> list[str]:
    mapping = {
        "overview": ["Architecture", "Core Modules"],
        "architecture": ["Overview", "Core Modules"],
        "core-modules": ["Architecture", "Important Files"],
        "important-files": ["How to Run", "Reading Guide"],
        "how-to-run": ["Important Files", "Reading Guide"],
        "reading-guide": ["Overview", "Core Modules"],
    }
    return mapping.get(slug, ["Overview", "Core Modules"])


def _join(values: list[str]) -> str:
    return ", ".join(values) if values else "none detected"
