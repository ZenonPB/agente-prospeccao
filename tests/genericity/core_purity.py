"""Varredura estática de pureza do core (Task 2).

Detecta duas formas de acoplamento a vertical dentro do core:

``identity_literal``
    Literal de string igual à chave de uma oferta/vertical conhecida
    (ex.: ``"trophies"``). É como o core "sabe" o nome de um domínio.

``identity_branch``
    Comparação entre uma expressão de identidade de perfil
    (``profile_key``, ``offer_key``, ``vertical``, ``archetype``) e um literal
    de string (ex.: ``if profile_key == "business_opportunity"``). É como o
    core toma decisão diferente por domínio.

Estratégia de **ratchet**: as violações que já existem hoje estão registradas
em ``KNOWN_VIOLATIONS`` com a Task do roadmap que as remove. O teste falha se
aparecer violação nova (o número não pode subir) e também se uma entrada da
lista ficar obsoleta (o número não pode ficar desatualizado quando cair). Assim
a lista só encolhe.

Por que literal exato: um branch/lookup por domínio usa igualdade exata
(``== "trophies"``, ``.get("trophies")``). Casar substring geraria falso
positivo em prosa ("presença digital") sem ganho de detecção.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKERS_SRC = REPO_ROOT / "services" / "workers" / "src"

# Módulos sob contrato de genericidade: o core dirigido por OfferProfile mais o
# planner de discovery (seam que decide providers).
CORE_DIRS = (WORKERS_SRC / "services" / "prospecting",)
CORE_EXTRA_FILES = (WORKERS_SRC / "services" / "discovery_planner_service.py",)

# `default_profiles` é a camada de configuração: declarar chaves de oferta é
# exatamente a sua função, não uma violação.
CORE_EXCLUDED_FILES = frozenset({"default_profiles.py", "__init__.py"})

# Identidades de domínio que o core não deve conhecer por nome.
OFFER_KEYS = frozenset({
    "landing_page", "mechanical_project", "technical_drawing",
    "machine_manual", "trophies", "web_erp",
})
VERTICAL_KEYS = frozenset({
    "digital", "mechanical_engineering", "awards", "business_systems",
})
FORBIDDEN_IDENTITIES = OFFER_KEYS | VERTICAL_KEYS

# Expressões que denotam identidade de perfil numa comparação.
IDENTITY_HINTS = ("profile_key", "offer_key", "offer_profile_key", "vertical", "archetype")

KIND_LITERAL = "identity_literal"
KIND_BRANCH = "identity_branch"


@dataclass(frozen=True)
class Violation:
    """Uma ocorrência de acoplamento a vertical no core."""
    module: str  # caminho relativo a services/workers/src
    kind: str
    detail: str
    line: int


# Baseline conhecido: violações que existem hoje e a Task que as remove.
# Formato: {(module, kind): (count, task)}
KNOWN_VIOLATIONS: Dict[Tuple[str, str], Tuple[int, str]] = {
    # `plan_discovery` ramifica por profile_key legado em vez de compor o plano
    # a partir de OfferProfile.discovery.
    ("services/discovery_planner_service.py", KIND_BRANCH): (
        1, "Task 5 — planner genérico dirigido por OfferProfile",
    ),
    # offer_key default "trophies", match por "trophies" e leitura do registry
    # com a chave fixa. O comportamento deve vir do OfferProfile da campanha.
    ("services/prospecting/event_opportunity_service.py", KIND_LITERAL): (
        4, "Task 6 — vertical de Troféus parametrizada por perfil",
    ),
    ("services/prospecting/event_opportunity_service.py", KIND_BRANCH): (
        1, "Task 6 — vertical de Troféus parametrizada por perfil",
    ),
}


def core_modules() -> List[Path]:
    """Arquivos Python sob contrato de genericidade, em ordem estável."""
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
    """Ids dos nós Constant que são docstring (documentar domínio é legítimo)."""
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
    """Diz se a expressão referencia identidade de perfil."""
    try:
        rendered = ast.unparse(node)
    except Exception:  # pragma: no cover — unparse cobre as formas usadas
        return False
    lowered = rendered.lower()
    return any(hint in lowered for hint in IDENTITY_HINTS)


def _domain_literals(node: ast.AST) -> List[str]:
    """Literais de string que representam **valor de domínio** na expressão.

    Nomes de campo/chave de identidade (``"offer_key"``, ``"vertical"``, ...)
    são descartados: em ``o["offer_key"] == offer_key`` o literal é o nome da
    coluna, não o nome de uma vertical. Sem esse filtro, todo acesso por chave
    viraria falso positivo.
    """
    values: List[str] = []
    for inner in ast.walk(node):
        if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
            if inner.value in IDENTITY_HINTS:
                continue
            values.append(inner.value)
    return values


def scan_module(path: Path) -> List[Violation]:
    """Coleta as violações de genericidade de um módulo."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    module = _relative(path)
    docstrings = _docstring_nodes(tree)
    violations: List[Violation] = []

    for node in ast.walk(tree):
        # 1) literal de identidade de domínio
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings and node.value in FORBIDDEN_IDENTITIES:
            violations.append(Violation(
                module=module,
                kind=KIND_LITERAL,
                detail=f"literal {node.value!r}",
                line=node.lineno,
            ))
        # 2) decisão por identidade de perfil
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
    """Varre todos os módulos sob contrato."""
    found: List[Violation] = []
    for path in core_modules():
        found.extend(scan_module(path))
    return found


def counts_by_module_kind(violations: List[Violation]) -> Dict[Tuple[str, str], int]:
    """Agrega violações por ``(module, kind)``."""
    counts: Dict[Tuple[str, str], int] = {}
    for violation in violations:
        key = (violation.module, violation.kind)
        counts[key] = counts.get(key, 0) + 1
    return counts

def allowed_counts() -> Dict[Tuple[str, str], int]:
    """Contagens permitidas pelo baseline, sem a anotação de Task."""
    return {key: count for key, (count, _) in KNOWN_VIOLATIONS.items()}


def new_violations(
    found: Dict[Tuple[str, str], int],
    allowed: Dict[Tuple[str, str], int],
) -> Dict[Tuple[str, str], int]:
    """Violações acima do baseline — o ratchet não deixa subir."""
    return {
        key: count for key, count in found.items()
        if count > allowed.get(key, 0)
    }


def stale_baseline(
    found: Dict[Tuple[str, str], int],
    allowed: Dict[Tuple[str, str], int],
) -> Dict[Tuple[str, str], Tuple[int, int]]:
    """Entradas do baseline que já foram (parcialmente) corrigidas.

    Devolve ``{chave: (declarado, encontrado)}``. Serve para forçar a redução da
    lista quando as Tasks 5 e 6 removerem os acoplamentos.
    """
    return {
        key: (declared, found.get(key, 0))
        for key, declared in allowed.items()
        if found.get(key, 0) < declared
    }
