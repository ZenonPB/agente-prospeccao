"""Fase 2 do loop de aprendizado: compilação de feedbacks em regras.

Cobre a injeção de `learned_instructions` no prompt de scoring e a
`compile_learnings` (LLM mockada): upsert de TemplateLearning, marcação dos
feedbacks como COMPILED e cap/compactação de regras (docs/ai-feedback-loop.md).
"""
from types import SimpleNamespace

from database.models import FeedbackStatus, TemplateLearning
from services.learning_compilation_service import (
    MAX_RULES,
    compile_learnings,
    get_learning_rules,
)
from services.scoring_service import build_prompt


import asyncio

async def _async(value):
    return value


# ------------------------------------------------------------------ fakes ---

class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDB:
    def __init__(self, feedbacks=(), learning=None):
        self.feedbacks = list(feedbacks)
        self.learning = learning
        self.added = []
        self.commits = 0

    def query(self, model):
        from database.models import ScoringFeedback, TemplateLearning
        if model is ScoringFeedback:
            return _FakeQuery(self.feedbacks)
        if model is TemplateLearning:
            return _FakeQuery([self.learning] if self.learning else [])
        return _FakeQuery([])

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1


def _feedback(score=85, suggested=40, reason="site bom, IA exagerou"):
    return SimpleNamespace(
        original_score=score,
        suggested_score=suggested,
        direction=SimpleNamespace(value="MUITO_ALTO"),
        reason=reason,
        status=FeedbackStatus.PENDING,
        created_at=None,
    )


# --------------------------------------------------------------- prompt -----

def test_build_prompt_injeta_regras_aprendidas():
    prompt = build_prompt(
        "Criação de Sites", "clínicas", None,
        [], [], learned_instructions=["sites amadores pesam MAIS"],
    )
    assert "AJUSTES APRENDIDOS COM O TIME" in prompt
    assert "sites amadores pesam MAIS" in prompt


def test_build_prompt_sem_regras_nao_injeta_bloco():
    prompt = build_prompt("Criação de Sites", "clínicas", None, [], [])
    assert "AJUSTES APRENDIDOS COM O TIME" not in prompt


# ----------------------------------------------------------- compilação -----

def test_compile_learnings_cria_regras_e_marca_compiled(monkeypatch):
    fb1, fb2 = _feedback(), _feedback()
    db = _FakeDB(feedbacks=[fb1, fb2])
    monkeypatch.setattr(
        "services.learning_compilation_service._llm_rules",
        lambda *a, **k: _async(["sites atualizados pesam MENOS em redesign"]),
    )

    import asyncio
    out = asyncio.run(compile_learnings(db, "org-1", "tmpl-1"))

    assert out == {
        "compiled": 2,
        "rules": ["sites atualizados pesam MENOS em redesign"],
        "compacted": False,
    }
    assert fb1.status == FeedbackStatus.COMPILED
    assert fb2.status == FeedbackStatus.COMPILED
    learning = db.added[0]
    assert isinstance(learning, TemplateLearning)
    assert learning.instructions == ["sites atualizados pesam MENOS em redesign"]
    assert learning.compiled_from == 2
    assert db.commits == 1


def test_compile_learnings_sem_feedback_nao_chama_llm(monkeypatch):
    db = _FakeDB(feedbacks=[])
    called = {"n": 0}

    async def _boom(*a, **k):
        called["n"] += 1
        return ["x"]

    monkeypatch.setattr("services.learning_compilation_service._llm_rules", _boom)
    import asyncio
    assert asyncio.run(compile_learnings(db, "org-1", "tmpl-1")) is None
    assert called["n"] == 0
    assert db.commits == 0


def test_compile_learnings_falha_llm_mantem_feedbacks_pendentes(monkeypatch):
    fb = _feedback()
    db = _FakeDB(feedbacks=[fb])
    monkeypatch.setattr(
        "services.learning_compilation_service._llm_rules", lambda *a, **k: _async(None),
    )
    import asyncio
    assert asyncio.run(compile_learnings(db, "org-1", "tmpl-1")) is None
    assert fb.status == FeedbackStatus.PENDING
    assert db.commits == 0


def _db_com_regras_existentes(n=9):
    existing = [f"regra {i}" for i in range(n)]
    return _FakeDB(
        feedbacks=[_feedback()],
        learning=SimpleNamespace(
            instructions=list(existing), compiled_from=n, organization_id="org-1",
            template_id="tmpl-1",
        ),
    )


def test_cap_compacta_regras_excedentes(monkeypatch):
    db = _db_com_regras_existentes(n=10)
    merged = [f"mesclada {i}" for i in range(MAX_RULES)]

    async def fake_llm(system_prompt, user_prompt, *a, **k):
        if "Compacte" in user_prompt:
            return list(merged)
        return ["regra nova"]

    monkeypatch.setattr("services.learning_compilation_service._llm_rules", fake_llm)
    import asyncio
    out = asyncio.run(compile_learnings(db, "org-1", "tmpl-1"))

    assert out["compacted"] is True
    assert out["rules"] == merged
    assert db.learning.instructions == merged


def test_cap_sem_compactacao_llm_mantem_mais_recentes(monkeypatch):
    db = _db_com_regras_existentes()

    async def fake_llm(system_prompt, user_prompt, *a, **k):
        if "Compacte" in user_prompt:
            return None  # compactação falha
        return ["regra nova"]

    monkeypatch.setattr("services.learning_compilation_service._llm_rules", fake_llm)
    import asyncio
    out = asyncio.run(compile_learnings(db, "org-1", "tmpl-1"))

    assert out["compacted"] is False
    assert len(out["rules"]) == MAX_RULES
    assert out["rules"][-1] == "regra nova"


def test_get_learning_rules_vazio_sem_template():
    db = _FakeDB()
    assert get_learning_rules(db, "org-1", None) == []
    assert get_learning_rules(db, None, "tmpl-1") == []


