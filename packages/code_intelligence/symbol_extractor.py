from __future__ import annotations

from pathlib import Path

from packages.code_intelligence.models import CodeSymbol
from packages.code_intelligence.parser import SUPPORTED_EXTENSIONS, extract_symbols_from_file


def extract_symbols(root: str | Path, file_paths: list[str]) -> list[CodeSymbol]:
    symbols: list[CodeSymbol] = []
    for file_path in sorted(file_paths):
        if Path(file_path).suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        symbols.extend(extract_symbols_from_file(root, file_path))
    return sorted(symbols, key=lambda item: (item.file_path, item.start_line, item.type, item.name))
