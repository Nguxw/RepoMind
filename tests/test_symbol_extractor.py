from pathlib import Path

from packages.code_intelligence.symbol_extractor import extract_symbols


def test_extract_python_symbols_classes_methods_functions_and_imports(tmp_path: Path):
    source = """import os
from pathlib import Path


class Trainer:
    def __init__(self, root: Path):
        self.root = root

    async def fit(self):
        return self.root


def train(config):
    return Trainer(Path(config)).fit()
"""
    (tmp_path / "train.py").write_text(source, encoding="utf-8")

    symbols = extract_symbols(tmp_path, ["train.py"])
    by_type_name = {(symbol.type, symbol.name): symbol for symbol in symbols}

    assert ("import", "os") in by_type_name
    assert ("import", "pathlib import Path") in by_type_name
    assert ("class", "Trainer") in by_type_name
    assert ("method", "__init__") in by_type_name
    assert ("method", "fit") in by_type_name
    assert ("function", "train") in by_type_name
    assert by_type_name[("function", "train")].start_line == 13
    assert by_type_name[("class", "Trainer")].signature == "class Trainer:"


def test_extract_javascript_and_typescript_symbols(tmp_path: Path):
    (tmp_path / "index.ts").write_text(
        """import express from "express";
export class ApiServer {
  start() {
    return true;
  }
}
export const buildApp = () => express();
export { ApiServer } from "./server";
""",
        encoding="utf-8",
    )

    symbols = extract_symbols(tmp_path, ["index.ts"])
    by_type_name = {(symbol.type, symbol.name): symbol for symbol in symbols}

    assert ("import", "express") in by_type_name
    assert ("class", "ApiServer") in by_type_name
    assert ("method", "start") in by_type_name
    assert ("function", "buildApp") in by_type_name
    assert ("export", "./server") in by_type_name
