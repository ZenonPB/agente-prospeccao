from services.prospecting.evidence_context import build_evidence_context


def test_contexto_e_deterministico_e_preserva_provenance():
    a = {"title": "CNPJ ativo", "source": "registry", "confidence": 0.9,
         "observed_at": "2026-09-18T12:00:00Z", "epistemic": "FACT"}
    b = {"title": "Possível expansão", "source": "intent", "confidence": 70,
         "epistemic": "HYPOTHESIS", "evidence_refs": ["registry:1"]}
    first = build_evidence_context(evidence=[a, b])
    second = build_evidence_context(evidence=[b, a])
    assert first["context_hash"] == second["context_hash"]
    assert first["schema_version"] == "evidence-context-v1"
    facts = [x for x in first["observations"] if x["epistemic"] == "FACT"]
    assert facts[0]["source"] == "registry"
    hypothesis = [x for x in first["observations"] if x["epistemic"] == "HYPOTHESIS"][0]
    assert hypothesis["confidence"] == 0.7
    assert hypothesis["evidence_refs"] == ["registry:1"]


def test_legado_sem_epistemic_nao_e_promovido_a_fact():
    context = build_evidence_context(
        discovery_provenance={"source": "legacy", "description": "dado antigo"}
    )
    assert context["observations"][0]["epistemic"] == "INFERENCE"
