from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable

from packages.code_intelligence.models import CodeSymbol

PYTHON_EXTENSIONS = {".py"}
JAVASCRIPT_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs"}
TYPESCRIPT_EXTENSIONS = {".ts", ".tsx", ".mts", ".cts"}
SUPPORTED_EXTENSIONS = PYTHON_EXTENSIONS | JAVASCRIPT_EXTENSIONS | TYPESCRIPT_EXTENSIONS


def extract_symbols_from_file(root: str | Path, relative_path: str) -> list[CodeSymbol]:
    path = Path(root) / relative_path
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return []
    source = _safe_read(path)
    if source is None:
        return []

    tree_sitter_symbols = _extract_with_tree_sitter(relative_path, source)
    if tree_sitter_symbols is not None:
        return tree_sitter_symbols

    if path.suffix.lower() in PYTHON_EXTENSIONS:
        return _extract_python_with_ast(relative_path, source)
    if path.suffix.lower() in JAVASCRIPT_EXTENSIONS | TYPESCRIPT_EXTENSIONS:
        return _extract_js_ts_with_regex(relative_path, source)
    return []


def _extract_with_tree_sitter(relative_path: str, source: str) -> list[CodeSymbol] | None:
    parser = _load_tree_sitter_parser(_language_key(relative_path))
    if parser is None:
        return None

    source_bytes = source.encode("utf-8")
    try:
        tree = parser.parse(source_bytes)
    except Exception:
        return None

    symbols: list[CodeSymbol] = []

    def visit(node, in_class: bool = False) -> None:
        node_type = getattr(node, "type", "")
        if node_type in {"class_definition", "class_declaration"}:
            symbols.append(_symbol_from_tree_sitter_node(relative_path, source, node, "class"))
            in_class = True
        elif node_type in {"function_definition", "function_declaration"}:
            symbol_type = "method" if in_class else "function"
            symbols.append(_symbol_from_tree_sitter_node(relative_path, source, node, symbol_type))
        elif node_type in {"method_definition"}:
            symbols.append(_symbol_from_tree_sitter_node(relative_path, source, node, "method"))
        elif node_type in {"import_statement", "import_from_statement"}:
            symbols.append(_symbol_from_tree_sitter_node(relative_path, source, node, "import"))
        elif node_type in {"export_statement"}:
            symbols.append(_symbol_from_tree_sitter_node(relative_path, source, node, "export"))

        for child in getattr(node, "children", []):
            visit(child, in_class=in_class)

    visit(tree.root_node)
    return _dedupe_symbols(symbols)


def _load_tree_sitter_parser(language: str | None):
    if language is None:
        return None

    for module_name in ("tree_sitter_language_pack", "tree_sitter_languages"):
        try:
            module = __import__(module_name, fromlist=["get_parser"])
            get_parser = getattr(module, "get_parser")
            return get_parser(language)
        except Exception:
            continue
    return None


def _symbol_from_tree_sitter_node(relative_path: str, source: str, node, symbol_type: str) -> CodeSymbol:
    start_line = _point_line(getattr(node, "start_point", (0, 0)))
    end_line = _point_line(getattr(node, "end_point", (start_line - 1, 0)))
    signature = _line_at(source, start_line)
    name_node = None
    try:
        name_node = node.child_by_field_name("name")
    except Exception:
        name_node = None
    name = _node_text(source, name_node) if name_node is not None else _name_from_signature(symbol_type, signature)
    return _make_symbol(
        relative_path=relative_path,
        name=name,
        symbol_type=symbol_type,
        start_line=start_line,
        end_line=max(start_line, end_line),
        signature=signature,
        language=_language_name(relative_path),
        metadata={"parser": "tree-sitter"},
    )


def _extract_python_with_ast(relative_path: str, source: str) -> list[CodeSymbol]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    lines = source.splitlines()
    symbols: list[CodeSymbol] = []
    class_ranges: list[tuple[int, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_ranges.append((node.lineno, getattr(node, "end_lineno", node.lineno)))
            symbols.append(
                _make_symbol(
                    relative_path,
                    node.name,
                    "class",
                    node.lineno,
                    getattr(node, "end_lineno", node.lineno),
                    _signature(lines, node.lineno),
                    "Python",
                    {"parser": "python-ast"},
                )
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            in_class = any(start < node.lineno <= end for start, end in class_ranges)
            symbols.append(
                _make_symbol(
                    relative_path,
                    node.name,
                    "method" if in_class else "function",
                    node.lineno,
                    getattr(node, "end_lineno", node.lineno),
                    _signature(lines, node.lineno),
                    "Python",
                    {"parser": "python-ast"},
                )
            )
        elif isinstance(node, ast.Import):
            names = ", ".join(alias.name for alias in node.names)
            symbols.append(
                _make_symbol(
                    relative_path,
                    names,
                    "import",
                    node.lineno,
                    node.lineno,
                    _signature(lines, node.lineno),
                    "Python",
                    {"parser": "python-ast", "module": names},
                )
            )
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            imported = ", ".join(alias.name for alias in node.names)
            name = f"{module} import {imported}".strip()
            symbols.append(
                _make_symbol(
                    relative_path,
                    name,
                    "import",
                    node.lineno,
                    node.lineno,
                    _signature(lines, node.lineno),
                    "Python",
                    {"parser": "python-ast", "module": module, "names": imported},
                )
            )

    return _dedupe_symbols(symbols)


def _extract_js_ts_with_regex(relative_path: str, source: str) -> list[CodeSymbol]:
    lines = source.splitlines()
    symbols: list[CodeSymbol] = []
    class_stack: list[tuple[int, int]] = []

    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        class_match = re.match(r"(?:export\s+default\s+|export\s+)?class\s+([A-Za-z_$][\w$]*)", stripped)
        if class_match:
            end_line = _rough_block_end(lines, index)
            class_stack.append((index, end_line))
            symbols.append(_make_symbol(relative_path, class_match.group(1), "class", index, end_line, stripped, _language_name(relative_path), {"parser": "regex"}))
            continue

        import_match = re.match(r"import\s+(?:.+?\s+from\s+)?['\"]([^'\"]+)['\"]", stripped)
        if import_match:
            symbols.append(_make_symbol(relative_path, import_match.group(1), "import", index, index, stripped, _language_name(relative_path), {"parser": "regex", "module": import_match.group(1)}))
            continue

        export_from_match = re.match(r"export\s+.+?\s+from\s+['\"]([^'\"]+)['\"]", stripped)
        if export_from_match:
            symbols.append(_make_symbol(relative_path, export_from_match.group(1), "export", index, index, stripped, _language_name(relative_path), {"parser": "regex", "module": export_from_match.group(1)}))
            continue

        function_match = re.match(r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", stripped)
        if function_match:
            in_class = _line_inside_ranges(index, class_stack)
            symbols.append(_make_symbol(relative_path, function_match.group(1), "method" if in_class else "function", index, _rough_block_end(lines, index), stripped, _language_name(relative_path), {"parser": "regex"}))
            continue

        arrow_match = re.match(r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>", stripped)
        if arrow_match:
            symbols.append(_make_symbol(relative_path, arrow_match.group(1), "function", index, _rough_block_end(lines, index), stripped, _language_name(relative_path), {"parser": "regex"}))
            continue

        method_match = re.match(r"(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{", stripped)
        if method_match and _line_inside_ranges(index, class_stack):
            symbols.append(_make_symbol(relative_path, method_match.group(1), "method", index, _rough_block_end(lines, index), stripped, _language_name(relative_path), {"parser": "regex"}))

    return _dedupe_symbols(symbols)


def _make_symbol(
    relative_path: str,
    name: str,
    symbol_type: str,
    start_line: int,
    end_line: int,
    signature: str,
    language: str,
    metadata: dict,
) -> CodeSymbol:
    clean_name = name.strip() or "<anonymous>"
    clean_type = symbol_type
    return CodeSymbol(
        id=f"{relative_path}:{start_line}:{clean_type}:{clean_name}",
        name=clean_name,
        type=clean_type,
        file_path=relative_path,
        start_line=start_line,
        end_line=max(start_line, end_line),
        signature=signature.strip(),
        language=language,
        metadata=metadata,
    )


def _dedupe_symbols(symbols: Iterable[CodeSymbol]) -> list[CodeSymbol]:
    seen: set[str] = set()
    result: list[CodeSymbol] = []
    for symbol in symbols:
        if symbol.id in seen:
            continue
        seen.add(symbol.id)
        result.append(symbol)
    return sorted(result, key=lambda item: (item.file_path, item.start_line, item.type, item.name))


def _language_key(relative_path: str) -> str | None:
    suffix = Path(relative_path).suffix.lower()
    if suffix in PYTHON_EXTENSIONS:
        return "python"
    if suffix in JAVASCRIPT_EXTENSIONS:
        return "javascript"
    if suffix in TYPESCRIPT_EXTENSIONS:
        return "typescript"
    return None


def _language_name(relative_path: str) -> str:
    suffix = Path(relative_path).suffix.lower()
    if suffix in PYTHON_EXTENSIONS:
        return "Python"
    if suffix in JAVASCRIPT_EXTENSIONS:
        return "JavaScript"
    if suffix in TYPESCRIPT_EXTENSIONS:
        return "TypeScript"
    return "Unknown"


def _point_line(point) -> int:
    row = getattr(point, "row", None)
    if row is not None:
        return row + 1
    return int(point[0]) + 1


def _node_text(source: str, node) -> str:
    if node is None:
        return ""
    return source.encode("utf-8")[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")


def _name_from_signature(symbol_type: str, signature: str) -> str:
    if symbol_type in {"import", "export"}:
        match = re.search(r"['\"]([^'\"]+)['\"]", signature)
        return match.group(1) if match else signature
    match = re.search(r"(?:class|function|def)\s+([A-Za-z_$][\w$]*)", signature)
    return match.group(1) if match else "<anonymous>"


def _signature(lines: list[str], line_number: int) -> str:
    if 1 <= line_number <= len(lines):
        return lines[line_number - 1].strip()
    return ""


def _line_at(source: str, line_number: int) -> str:
    return _signature(source.splitlines(), line_number)


def _rough_block_end(lines: list[str], start_line: int) -> int:
    start_index = start_line - 1
    balance = 0
    saw_open = False
    for index in range(start_index, len(lines)):
        line = lines[index]
        balance += line.count("{")
        if "{" in line:
            saw_open = True
        balance -= line.count("}")
        if saw_open and balance <= 0:
            return index + 1
    return start_line


def _line_inside_ranges(line_number: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start < line_number <= end for start, end in ranges)


def _safe_read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
