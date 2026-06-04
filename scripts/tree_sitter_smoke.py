from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.code_intelligence.symbol_extractor import extract_symbols


def main() -> None:
    installed = {
        "tree_sitter": bool(importlib.util.find_spec("tree_sitter")),
        "tree_sitter_language_pack": bool(importlib.util.find_spec("tree_sitter_language_pack")),
        "tree_sitter_languages": bool(importlib.util.find_spec("tree_sitter_languages")),
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "sample.py").write_text("import os\n\ndef main():\n    return os.getcwd()\n", encoding="utf-8")
        (root / "sample.ts").write_text("import express from 'express';\nexport const app = () => express();\n", encoding="utf-8")
        symbols = extract_symbols(root, ["sample.py", "sample.ts"])

    parser_names = sorted({symbol.metadata.get("parser", "unknown") for symbol in symbols})
    print(
        {
            "installed": installed,
            "symbol_count": len(symbols),
            "parsers_used": parser_names,
            "tree_sitter_live": any(str(name).startswith("tree-sitter") for name in parser_names),
        }
    )


if __name__ == "__main__":
    main()
