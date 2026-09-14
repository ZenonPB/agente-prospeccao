"""Varredura estática de pureza do core (Task 2).

Detecta duas formas de acoplamento a vertical dentro do core:

``identity_literal``
    Literal de string igual à chave de uma oferta/vertical conhecida.

``identity_branch``
    Comparação entre identidade de perfil e literal de domínio.

A estratégia é um ratchet: violações corrigidas são removidas do baseline e
não podem reaparecer em mudanças futuras.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKERS_SRC = REPO_ROOT / "services" / "workers" / "src"
CORE_DIRS = (WORKERS_SRC / "services" / "prospecting",)
CORE_EXTRA_FILES = (WORKERS_SRC / "services" / "discovery_planner_service.py",)
CORE_EXCLUDED_FILES = frozenset({"default_profiles.py", "__init__.py"})

OFFER_KEYS = frozenset({
    "landing_page", "mechanical_project", "technical_drawing",
    "machine_manual", "trophies", "web_erp",
})
VERTICAL_KEYS = frozenset({
    "digital", "mechanical_engineering", "awards", "business_systems",
})
FORBIDDEN_IDENTITIES = OFFER_KEYS | VERTICAL_KEYS
IDENTITY_HINTS = ("profile_key", "offer_key", "offer_profile_key", "vertical", "archetype")

KIND_LITERAL = "identity_literal"
KIND_BRANCH = "identity_branch"


@dataclass(frozen=True)
class Violation:
    module: str
    kind: str
    detail: str
    line: int


KNOWN_VIOLATIONS: Dict[Tuple[str, str], Tuple[int, str]] = {
    ("services/discovery_planner_service.py", KIND_BRANCH): (
        1, "Task 5 — planner genérico dirigido por OfferProfile",
    ),
}


def core_modules() -> List[Path]:
    files: List[Path] = []
    for directory in CORE_DIRS:
        files.extend(
            path for path in sorted(directory.glob("*.py"))
            if path.name not in CORE_EXCLUDED_FILES
        )
    files.extend(path for path in CORE_EXTRA_FILES if path.exists())
    return files


def _relative(path: Path) -> str:
    return path.relative_to(WORKERS_SRC).as_posix()


def _docstring_nodes(tree: ast.AST) -> Set[int]:
    ids: Set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if not body:
                continue
            first = body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


def _mentions_identity(node: ast.AST) -> bool:
    try:
        rendered = ast.unparse(node)
    except Exception:  # pragma: no cover
        return False
    lowered = rendered.lower()
    return any(hint in lowered for hint in IDENTITY_HINTS)


def _domain_literals(node: ast.AST) -> List[str]:
    values: List[str] = []
    for inner in ast.walk(node):
        if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
            if inner.value in IDENTITY_HINTS:
                continue
            values.append(inner.value)
    return values


def scan_module(path: Path) -> List[Violation]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    module = _relative(path)
    docstrings = _docstring_nodes(tree)
    violations: List[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings and node.value in FORBIDDEN_IDENTITIES:
            violations.append(Violation(
                module=module,
                kind=KIND_LITERAL,
                detail=f"literal {node.value!r}",
                line=node.lineno,
            ))
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            if any(_mentions_identity(part) for part in operands):
                literals = [
                    value for part in operands for value in _domain_literals(part)
                ]
                if literals:
                    violations.append(Violation(
                        module=module,
                        kind=KIND_BRANCH,
                        detail=f"comparação de identidade com {literals!r}",
                        line=node.lineno,
                    ))
    return violations


def scan_core() -> List[Violation]:
    found: List[Violation] = []
    for path in core_modules():
        found.extend(scan_module(path))
    return found


def counts_by_module_kind(violations: List[Violation]) -> Dict[Tuple[str, str], int]:
    counts: Dict[Tuple[str, str], int] = {}
    for violation in violations:
        key = (violation.module, violation.kind)
        counts[key] = counts.get(key, 0) + 1
    return counts


def allowed_counts() -> Dict[Tuple[str, str], int]:
    return {key: count for key, (count, _) in KNOWN_VIOLATIONS.items()}


def new_violations(
    found: Dict[Tuple[str, str], int],
    allowed: Dict[Tuple[str, str], int],
) -> Dict[Tuple[str, str], int]:
    return {
        key: count for key, count in found.items()
        if count > allowed.get(key, 0)
    }


def stale_baseline(
    found: Dict[Tuple[str, str], int],
    allowed: Dict[Tuple[str, str], int],
) -> Dict[Tuple[str, str], Tuple[int, int]]:
    return {
        key: (declared, found.get(key, 0))
        for key, declared in allowed.items()
        if found.get(key, 0) < declared
    }
