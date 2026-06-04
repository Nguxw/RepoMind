from __future__ import annotations

from dataclasses import dataclass

from packages.repo_ingestion.models import RepoProfile


@dataclass(frozen=True)
class WikiPageSpec:
    title: str
    slug: str


class WikiPlanner:
    DEFAULT_PAGES = [
        WikiPageSpec("Overview", "overview"),
        WikiPageSpec("Architecture", "architecture"),
        WikiPageSpec("Core Modules", "core-modules"),
        WikiPageSpec("Important Files", "important-files"),
        WikiPageSpec("How to Run", "how-to-run"),
        WikiPageSpec("Reading Guide", "reading-guide"),
    ]
    ML_PAGES = [
        WikiPageSpec("Dataset Pipeline", "dataset-pipeline"),
        WikiPageSpec("Model Architecture", "model-architecture"),
        WikiPageSpec("Training Loop", "training-loop"),
        WikiPageSpec("Evaluation Pipeline", "evaluation-pipeline"),
    ]

    def plan(self, profile: RepoProfile) -> list[WikiPageSpec]:
        pages = list(self.DEFAULT_PAGES)
        if _looks_like_ml_project(profile):
            pages.extend(self.ML_PAGES)
        return pages


def _looks_like_ml_project(profile: RepoProfile) -> bool:
    haystack = " ".join([
        *profile.frameworks,
        *profile.dependency_files,
        *profile.entrypoints,
        *profile.important_files,
    ]).lower()
    return any(keyword in haystack for keyword in ["torch", "pytorch", "tensorflow", "sklearn", "scikit", "train.py", "dataset", "model"])
