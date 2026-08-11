"""Testes do LinkedIn assistido (roadmap-vendas 4.22).

Cobrem a extração/validação de URL de perfil, a montagem das consultas
sugeridas (padrão e via playbook do template) e a persistência da associação
manual (fonte `manual:<user_id>`, confiança e trilha) com um `db` fake.
"""
from types import SimpleNamespace

from src.db.models import LeadActivityAction
from src.services.linkedin_assist_service import (
    CONF_REVIEW,
    CONF_VALIDATED,
    DEFAULT_ROLE_QUERIES,
    LinkedInAssistService,
    build_linkedin_queries,
    extract_linkedin_username,
)


# ---------------------------------------------------------------------------
# extração/validação de URL
# ---------------------------------------------------------------------------

def test_extract_username_urls_validas():
    assert extract_linkedin_username("https://www.linkedin.com/in/maria-silva") == "maria-silva"
    assert extract_linkedin_username("linkedin.com/in/joao") == "joao"
    assert extract_linkedin_username("https://br.linkedin.com/in/ana-0liveira") == "ana-0liveira"
    assert extract_linkedin_username("https://www.linkedin.com/in/maria-silva/") == "maria-silva"


def test_extract_username_rejeita_formato_invalido():
    assert extract_linkedin_username("https://exemplo.com/in/joao") is None
    assert extract_linkedin_username("https://linkedin.com/company/foo") is None
    assert extract_linkedin_username("não é url") is None
    assert extract_linkedin_username("") is None
    assert extract_linkedin_username("https://linkedin.com/in/jo@o") is None
    assert extract_linkedin_username("https://linkedin.com/in/maria silva") is None


# ---------------------------------------------------------------------------
# consultas sugeridas
# ---------------------------------------------------------------------------

def test_queries_usam_lista_padrao_de_papeis():
    queries = build_linkedin_queries("Padaria Pão Quente", None)
    assert len(queries) == len(DEFAULT_ROLE_QUERIES)
    queries_by_label = {q["label"]: q["query"] for q in queries}
    assert queries_by_label["fundador"] == '"Padaria Pão Quente" fundador linkedin'


def test_queries_respeitam_playbook_do_template():
    playbook = {"linkedin_queries": ["proprietário", "gerente comercial"]}
    queries = build_linkedin_queries("Clínica Vida", playbook)
    assert [q["label"] for q in queries] == ["proprietário", "gerente comercial"]
    assert queries[0]["query"] == '"Clínica Vida" proprietário linkedin'


def test_queries_playbook_vazio_cai_na_lista_padrao():
    assert build_linkedin_queries("X", {"linkedin_queries": []}) == build_linkedin_queries("X", None)
    assert build_linkedin_queries("X", {}) == build_linkedin_queries("X", None)


# ---------------------------------------------------------------------------
# associação manual
# ---------------------------------------------------------------------------

class _FakeDb:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


def _mk_contact():
    return SimpleNamespace(
        linkedin_url=None,
        linkedin_confidence=None,
        raw_data=None,
    )


def test_associate_validado_grava_confianca_e_origem_manual():
    db = _FakeDb()
    lead = SimpleNamespace(id="lead-1")
    contact = _mk_contact()

    LinkedInAssistService().associate(db, lead, contact, "maria-silva", "u1", validated=True)

    assert contact.linkedin_url == "https://www.linkedin.com/in/maria-silva"
    assert contact.linkedin_confidence == CONF_VALIDATED
    assert contact.raw_data["linkedin_source"] == "manual:u1"


def test_associate_sem_confirmacao_fica_candidato_revisao():
    db = _FakeDb()
    lead = SimpleNamespace(id="lead-1")
    contact = _mk_contact()

    LinkedInAssistService().associate(db, lead, contact, "joao", "u2", validated=False)

    assert contact.linkedin_confidence == CONF_REVIEW
    assert contact.raw_data["linkedin_source"] == "manual:u2"


def test_associate_registra_atividade_na_trilha():
    db = _FakeDb()
    lead = SimpleNamespace(id="lead-1")
    contact = _mk_contact()

    LinkedInAssistService().associate(db, lead, contact, "ana", "u1", validated=True)

    assert len(db.added) == 1
    activity = db.added[0]
    assert activity.action == LeadActivityAction.LINKEDIN_ASSOCIATED
    assert activity.lead_id == "lead-1"
    assert activity.user_id == "u1"
    assert "ana" in (activity.detail or "")
