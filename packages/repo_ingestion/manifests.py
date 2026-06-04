from __future__ import annotations

from pathlib import Path

DEPENDENCY_FILE_NAMES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "setup.py",
    "setup.cfg",
    "environment.yml",
    "environment.yaml",
    "conda.yml",
    "conda.yaml",
}

CONFIG_FILE_NAMES = {
    ".dockerignore",
    ".editorconfig",
    ".env.example",
    ".eslintrc",
    ".eslintrc.cjs",
    ".eslintrc.js",
    ".eslintrc.json",
    ".gitignore",
    ".prettierrc",
    ".prettierrc.json",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "jest.config.js",
    "jest.config.ts",
    "mypy.ini",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "pytest.ini",
    "ruff.toml",
    "tailwind.config.js",
    "tailwind.config.ts",
    "tox.ini",
    "tsconfig.json",
    "vite.config.js",
    "vite.config.ts",
}

LANGUAGE_BY_EXTENSION = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".c": "C",
    ".h": "C/C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".sh": "Shell",
    ".sql": "SQL",
}

IMPORTANT_DIRECTORY_NAMES = {
    "app",
    "apps",
    "cmd",
    "config",
    "configs",
    "docs",
    "examples",
    "lib",
    "packages",
    "scripts",
    "server",
    "src",
    "tests",
}

ENTRYPOINT_FILE_NAMES = {
    "app.py",
    "asgi.py",
    "cli.py",
    "index.js",
    "index.ts",
    "main.go",
    "main.js",
    "main.py",
    "main.ts",
    "manage.py",
    "server.js",
    "server.py",
    "server.ts",
    "train.py",
    "wsgi.py",
}


def is_readme(path: str) -> bool:
    return Path(path).name.lower().startswith("readme")


def is_dependency_file(path: str) -> bool:
    return Path(path).name in DEPENDENCY_FILE_NAMES


def is_config_file(path: str) -> bool:
    name = Path(path).name
    return name in CONFIG_FILE_NAMES or name.endswith((".config.js", ".config.ts", ".toml", ".yaml", ".yml"))


def is_test_file(path: str) -> bool:
    normalized = path.replace("\\", "/")
    name = Path(path).name
    return (
        normalized.startswith("tests/")
        or "/tests/" in normalized
        or name.startswith("test_")
        or name.endswith(("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts", ".test.tsx", ".spec.tsx"))
    )


def is_entrypoint(path: str) -> bool:
    normalized = path.replace("\\", "/")
    name = Path(path).name
    if name in ENTRYPOINT_FILE_NAMES:
        return True
    return normalized in {"src/main.py", "src/app.py", "src/index.ts", "src/index.js"}
