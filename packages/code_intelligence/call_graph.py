from __future__ import annotations

import ast
import re
from pathlib import Path

from packages.code_intelligence.models import CodeCall, CodeSymbol


def extract_calls(root: str | Path, file_paths: list[str], symbols: list[CodeSymbol]) -> list[CodeCall]:
    symbol_by_file = _symbols_by_file(symbols)
    calls: list[CodeCall] = []
    for file_path in sorted(file_paths):
        suffix = Path(file_path).suffix.lower()
        if suffix == ".py":
            calls.extend(_extract_python_calls(Path(root) / file_path, file_path, symbol_by_file.get(file_path, [])))
        elif suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}:
            calls.extend(_extract_js_ts_calls(Path(root) / file_path, file_path, symbol_by_file.get(file_path, [])))
    return sorted(calls, key=lambda call: (call.file_path, call.line, call.caller_name, call.callee_name))


def _symbols_by_file(symbols: list[CodeSymbol]) -> dict[str, list[CodeSymbol]]:
    grouped: dict[str, list[CodeSymbol]] = {}
    for symbol in symbols:
        if symbol.type in {"function", "method"}:
            grouped.setdefault(symbol.file_path, []).append(symbol)
    return grouped


def _extract_python_calls(path: Path, relative_path: str, symbols: list[CodeSymbol]) -> list[CodeCall]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return []

    calls: list[CodeCall] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        caller = _find_symbol(symbols, node.name, node.lineno)
        if caller is None:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                callee = _python_call_name(child.func)
                if callee:
                    calls.append(
                        CodeCall(
                            caller_symbol_id=caller.id,
                            caller_name=caller.name,
                            callee_name=callee,
                            file_path=relative_path,
                            line=getattr(child, "lineno", node.lineno),
                            language="Python",
                            metadata={"parser": "python-ast"},
                        )
                    )
    return calls


def _extract_js_ts_calls(path: Path, relative_path: str, symbols: list[CodeSymbol]) -> list[CodeCall]:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []

    calls: list[CodeCall] = []
    for symbol in symbols:
        if symbol.type not in {"function", "method"}:
            continue
        for line_number in range(symbol.start_line, min(symbol.end_line, len(lines)) + 1):
            line = lines[line_number - 1]
            for match in re.finditer(r"\b([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)\s*\(", line):
                callee = match.group(1)
                if callee in {symbol.name, "if", "for", "while", "switch", "return", "function"}:
                    continue
                calls.append(
                    CodeCall(
                        caller_symbol_id=symbol.id,
                        caller_name=symbol.name,
                        callee_name=callee,
                        file_path=relative_path,
                        line=line_number,
                        language=symbol.language,
                        metadata={"parser": "regex"},
                    )
                )
    return calls


def _find_symbol(symbols: list[CodeSymbol], name: str, line: int) -> CodeSymbol | None:
    for symbol in symbols:
        if symbol.name == name and symbol.start_line == line:
            return symbol
    for symbol in symbols:
        if symbol.name == name and symbol.start_line <= line <= symbol.end_line:
            return symbol
    return None


def _python_call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _python_call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None
