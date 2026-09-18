"""Piloto Araraquara: Landing Pages → clínicas de psicologia (PR E).

Cobre o caminho operacional com dados em layout oficial (fiel ao
NOVOLAYOUTDOSDADOSABERTOSDOCNPJ): overlay por workspace → import filtrado →
discovery Registry → entity resolution → Company → shadow UNKNOWN →
budget R$0. Sem outreach, sem rede, sem provider pago.

Honestidade: fixtures provam o caminho, não validação operacional nem
evidência comercial. Snapshot real continua gate do readiness.
"""
from __future__ import annotations

import os
import uuid as uuid_mod

import pytest

E2E_DATABASE_URL = os.environ.get("E2E_DATABASE_URL")
needs_pg = pytest.mark.skipif(not E2E_DATABASE_URL, reason="E2E_DATABASE_URL não definido")

MUN_ARARAQUARA = "3503208"


def _estab(basico, ordem, dv, fantasia, situacao, cnae, secundarias, uf, mun):
    cols = [basico, ordem, dv, "1", fantasia, situacao, "20200115", "00", "",
            "105", "20100110", cnae, secundarias, "RUA", "A", "10", "", "B",
            "20031170", uf, mun, "21", "1", "", "", "", "", "", "", ""]
    assert len(cols) == 30
    return ";".join(f'"{c}"' for c in cols)


def test_overlay_piloto_e_valido_e_nao_toca_o_base():
    from services.pilot.araraquara import (
        PILOT_CNAES,
        build_pilot_overlay,
    )
    from services.prospecting.default_profiles import get_base_registry
    from services.prospecting.offer_profile import OfferProfile
    from services.prospecting.offer_profile_validator import validate_profile

    base = get_base_registry().get("landing_page")
    snapshot = build_pilot_overlay(base)
    assert PILOT_CNAES == ["8650-0/03"]
    profile = OfferProfile.from_dict(snapshot)
    assert profile.key == "landing_page"
    assert profile.icp["cnaes"] == ["8650-0/03"]
    assert profile.icp["geography"]["states"] == ["SP"]
    assert profile.icp["geography"]["municipality_code"] == MUN_ARARAQUARA
    assert "cnae_discovery" in (profile.discovery.get("providers") or [])
    errors = [p for p in validate_profile(profile) if not p.startswith("aviso:")]
    assert errors == []
    # Base intacta: sem CNAE de psicologia, sem hardcode no core.
    assert "8650-0/03" not in (base.icp.get("cnaes") or [])


def test_builder_generico_nao_conhece_vertical():
    from services.prospecting.default_profiles import get_base_registry
    from services.prospecting.offer_profile import OfferProfile
    from services.prospecting.workspace_overlay import build_workspace_overlay

    base = get_base_registry().get("landing_page")
    original = base.version
    snapshot = build_workspace_overlay(
        base, version="9.9", icp_overrides={"cnaes": ["25"]})
    assert OfferProfile.from_dict(snapshot).version == "9.9"
    assert base.version == original
    with pytest.raises(ValueError):
        build_workspace_overlay(base, version="invalida")


def test_overlay_resolve_filtros_do_registry():
    from services.pilot.araraquara import build_pilot_overlay
    from services.prospecting.default_profiles import get_base_registry
    from services.prospecting.offer_profile import OfferProfile
    from services.registry.targeting import TargetingResult

    profile = OfferProfile.from_dict(
        build_pilot_overlay(get_base_registry().get("landing_page")))
    outcome = TargetingResult.from_offer(
        profile.icp, profile.discovery, target_candidates=20)
    assert outcome.filters is not None
    assert outcome.filters.municipio_cod == MUN_ARARAQUARA
    assert outcome.filters.uf == "SP"
    assert "8650003" in (outcome.filters.cnaes or [])


def _db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)()


@needs_pg
def test_smoke_piloto_aponta_caminho_completo(tmp_path):
    from services.pilot.araraquara import run_pilot_smoke

    engine, db = _db()
    org_id = None
    try:
        org_id = _prepare(db, tmp_path)
        report = _run_smoke(run_pilot_smoke, db, org_id)
        assert report["status"] == "success"
        assert report["candidatos"] == 3
        assert report["ativas"] == 2
        assert report["cnae_principal"] == 2
        assert report["cnae_secundario"] == 1
        assert report["empresas_materializadas"] == 3
        assert report["duplicatas_evitadas"] == 3
        assert report["custo_estimado"] == 0.0
        assert report["falhas"] == 0
        assert report["prova_sem_pago"] is True
        assert report["dimensoes_unknown"] is True
        assert report["proveniencias_ok"] is True
    finally:
        _cleanup(db, org_id)
        db.close()
        engine.dispose()


def _prepare(db, tmp_path):
    import uuid as uuid_mod

    from database.learning_models import OfferProfileVersion
    from database.models import Organization, RegistryCompany
    from services.pilot.araraquara import (
        PILOT_MONTH,
        build_pilot_overlay,
    )
    from services.prospecting.default_profiles import get_base_registry
    from services.prospecting.offer_profile import OfferProfile
    from services.registry.importer import RegistryFileSpec, RegistryImporter
    from services.registry.scope import parse_scope

    org = Organization(name="Org Piloto Araraquara",
                       slug=f"piloto-araraquara-{uuid_mod.uuid4().hex[:8]}")
    db.add(org)
    db.flush()
    snapshot = build_pilot_overlay(get_base_registry().get("landing_page"))
    profile = OfferProfile.from_dict(snapshot)
    db.add(OfferProfileVersion(
        organization_id=org.id, offer_key=profile.key, version=profile.version,
        profile_snapshot=snapshot, is_active=True))
    rows = [
        _estab("33000167", "0001", "01", "CLINICA MENTE VIVA", "02",
               "8650003", "", "SP", MUN_ARARAQUARA),
        _estab("33592510", "0001", "54", "ESPACO PSI", "02",
               "8630504", "8650003", "SP", MUN_ARARAQUARA),
        _estab("60701190", "0001", "04", "PSI SAO PAULO", "02",
               "8650003", "", "SP", "3550308"),
        _estab("00000000", "0001", "91", "PSI INATIVA", "08",
               "8650003", "", "SP", MUN_ARARAQUARA),
    ]
    festab = tmp_path / "ESTABELE0"
    festab.write_text("\n".join(rows), encoding="latin-1")
    femp = tmp_path / "EMPRESA0"
    femp.write_text("\n".join([
        '"33000167";"MENTE VIVA LTDA";"2062";"49";"10000,00";"01";""',
        '"33592510";"ESPACO PSI LTDA";"2062";"49";"20000,00";"03";""',
        '"00000000";"PSI INATIVA LTDA";"2062";"49";"5000,00";"01";""',
    ]), encoding="latin-1")
    fcnae = tmp_path / "CNAE"
    fcnae.write_text('"8650003";"Atividades de psicologia e psicanálise"',
                     encoding="latin-1")
    scope = parse_scope(ufs=["SP"], municipio_cods=[MUN_ARARAQUARA], cnaes=["8650-0/03"])
    snap = RegistryImporter(db, batch_size=10).import_snapshot(
        snapshot_month=PILOT_MONTH,
        files=[
            RegistryFileSpec(table_kind="estabelecimentos", path=str(festab),
                             file_name="ESTABELE0"),
            RegistryFileSpec(table_kind="empresas", path=str(femp), file_name="EMPRESA0"),
            RegistryFileSpec(table_kind="cnaes", path=str(fcnae), file_name="CNAE"),
        ],
        scope=scope,
    )
    assert snap.status == "COMPLETED"
    scoped = db.query(RegistryCompany).filter_by(source_snapshot=PILOT_MONTH).count()
    assert scoped == 3
    return org.id


def _run_smoke(runner, db, org_id):
    import asyncio

    from services.pilot.araraquara import PILOT_MONTH

    return asyncio.run(runner(db, org_id, snapshot_month=PILOT_MONTH))


def _cleanup(db, org_id):
    from database.learning_models import OfferProfileVersion
    from database.models import Company, CompanyAlias, Organization, RegistryCnae, RegistryCompany, RegistryCompanyCnae, RegistrySnapshot

    for cnpj in ("33000167000101", "33592510000154", "00000000000191"):
        db.query(RegistryCompanyCnae).filter_by(cnpj=cnpj).delete(
            synchronize_session=False)
        row = db.query(RegistryCompany).filter_by(cnpj=cnpj).first()
        if row is not None:
            db.delete(row)
    label = db.query(RegistryCnae).filter_by(codigo="8650003").first()
    if label is not None:
        db.delete(label)
    for month in ("2026-08",):
        snap = db.query(RegistrySnapshot).filter_by(
            source="receita_cnpj", snapshot_month=month).first()
        if snap is not None:
            db.delete(snap)
    if org_id is not None:
        db.query(CompanyAlias).filter_by(organization_id=org_id).delete(
            synchronize_session=False)
        db.query(Company).filter_by(organization_id=org_id).delete(
            synchronize_session=False)
        db.query(OfferProfileVersion).filter_by(organization_id=org_id).delete(
            synchronize_session=False)
        org = db.query(Organization).filter_by(id=org_id).first()
        if org is not None:
            db.delete(org)
    db.commit()


def test_politica_orcamento_zero_bloqueia_pago():
    from services.prospecting.provider_access_policy import ProviderAccessPolicy
    from services.prospecting.provider_planner import ProviderPolicy

    policy = ProviderAccessPolicy()
    allowed, reason = policy.allows(ProviderPolicy(
        provider="hunter", capability="contact_enrichment", cost_per_request=0.02))
    assert allowed is False
    assert reason == "paid_provider_disabled"
