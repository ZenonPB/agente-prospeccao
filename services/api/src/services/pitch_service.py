"""Pitch one-pager + site audit legível — Item 2.5 do roadmap.

Consolida dados dispersos do lead (scoring, enriquecimento técnico, company
record, campanha) em dois artefatos narrativos:

- **Pitch one-pager**: visão executiva condensada para o vendedor entrar
  numa reunião confiante — tese comercial, dores prováveis, argumentário,
  CTA sugerido.
- **Site audit**: apresentação consultiva dos dados técnicos já
  coletados (SSL, CMS, SEO, performance, paths) — sem novo enriquecimento.
"""
import html
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.db.models import Lead, Enrichment, Campaign, Contact, CompanyRecord

logger = logging.getLogger(__name__)


def _speed_label(ms: Optional[int]) -> str:
    if ms is None:
        return "Não medido"
    if ms < 1000:
        return f"Rápido ({ms}ms)"
    if ms < 3000:
        return f"Aceitável ({ms}ms)"
    if ms < 6000:
        return f"Lento ({ms}ms)"
    return f"Muito lento ({ms}ms)"


def _ssl_label(enrichment: Optional[Any]) -> str:
    if not enrichment:
        return "Sem dados"
    if enrichment.ssl_ok:
        return "Certificado SSL válido e configurado"
    raw = enrichment.raw_technical_data or {}
    ssl_data = raw.get("ssl", {})
    err = ssl_data.get("error")
    if enrichment.https_redirect_ok:
        return "Redireciona para HTTPS, mas SSL com ressalvas"
    return f"SSL ausente ou inválido{': ' + err if err else ''}"


def _seo_summary(raw: dict) -> list[str]:
    seo = raw.get("seo", {})
    issues = seo.get("issues", [])
    findings: list[str] = []
    if seo.get("has_title"):
        findings.append(f"Title presente: \"{seo.get('title', '')}\"")
    else:
        findings.append("Title ausente")
    if seo.get("has_meta_description"):
        findings.append("Meta description presente")
    else:
        findings.append("Meta description ausente")
    if seo.get("has_h1"):
        findings.append("H1 presente")
    else:
        findings.append("H1 ausente")
    if seo.get("has_lgpd"):
        findings.append("Menção a LGPD/Política de Privacidade encontrada")
    else:
        findings.append("Sem menção a LGPD/Política de Privacidade")
    for issue in issues:
        if issue not in findings:
            findings.append(issue)
    return findings


def build_site_audit(enrichment: Optional[Enrichment]) -> Optional[dict]:
    """Monta o site audit legível a partir dos dados técnicos já coletados."""
    if not enrichment:
        return None
    if not enrichment.website_exists:
        return {
            "available": False,
            "summary": "Lead sem website — análise técnica não aplicável.",
            "sections": [],
        }

    raw = enrichment.raw_technical_data or {}
    sections: list[dict] = []

    sections.append({
        "title": "Certificado SSL / HTTPS",
        "status": "ok" if enrichment.ssl_ok else "warning",
        "detail": _ssl_label(enrichment),
    })

    sections.append({
        "title": "Tecnologia / CMS",
        "status": "info",
        "detail": enrichment.cms or "Não identificada",
    })

    sections.append({
        "title": "Performance",
        "status": "ok" if (enrichment.load_time_ms or 9999) < 3000 else "warning",
        "detail": _speed_label(enrichment.load_time_ms),
    })

    security_issues = enrichment.security_issues or []
    missing_headers = (raw.get("http_headers", {}).get("security_headers_missing") or [])
    sec_items = list(security_issues)
    if missing_headers:
        sec_items.append(f"Headers de segurança ausentes: {', '.join(missing_headers)}")
    sections.append({
        "title": "Segurança",
        "status": "warning" if sec_items else "ok",
        "detail": "; ".join(sec_items) if sec_items else "Nenhum problema de segurança identificado",
        "items": sec_items,
    })

    seo_findings = _seo_summary(raw)
    seo_issues = raw.get("seo", {}).get("issues", [])
    sections.append({
        "title": "SEO e LGPD",
        "status": "warning" if seo_issues else "ok",
        "detail": "; ".join(seo_findings),
        "items": seo_findings,
    })

    exposed = raw.get("exposed_paths", [])
    if exposed:
        sections.append({
            "title": "Caminhos expostos",
            "status": "warning",
            "detail": f"{len(exposed)} caminho(s) sensível(is) acessível(is) publicamente",
            "items": exposed,
        })

    errors = raw.get("errors", [])
    warnings = raw.get("warnings", [])
    overall = raw.get("overall_status", "OK")

    return {
        "available": True,
        "overall_status": overall,
        "summary": f"{len(errors)} erro(s), {len(warnings)} aviso(s)" if (errors or warnings) else "Sem problemas identificados",
        "sections": sections,
        "errors": errors,
        "warnings": warnings,
    }


def build_pitch_one_pager(
    lead: Lead,
    enrichment: Optional[Enrichment],
    campaign: Optional[Campaign],
    contacts: list[Contact],
    company_record: Optional[CompanyRecord],
) -> dict:
    """Consolida o pitch one-pager do lead."""
    identity: dict[str, Any] = {
        "company_name": lead.company_name,
        "category": lead.category,
        "city": lead.city,
        "state": lead.state,
        "website": lead.website,
        "phone": lead.phone,
        "email": lead.email,
    }
    if company_record:
        identity.update({
            "cnpj": company_record.cnpj,
            "razao_social": company_record.razao_social,
            "nome_fantasia": company_record.nome_fantasia,
            "porte": company_record.porte_label or company_record.porte,
            "cnae_principal": company_record.cnae_principal_label or company_record.cnae_principal,
            "data_abertura": company_record.data_abertura,
            "idade_anos": company_record.idade_anos,
            "situacao_cadastral": company_record.situacao_cadastral,
            "capital_social": float(company_record.capital_social) if company_record.capital_social else None,
        })

    campaign_context = None
    if campaign:
        campaign_context = {
            "name": campaign.name,
            "target_service": campaign.target_service,
            "target_segment": campaign.target_segment,
        }

    primary_contact = None
    for c in contacts:
        if c.is_primary:
            primary_contact = {
                "name": c.name,
                "role": c.role_label or (c.role.value if c.role else None),
                "email": c.email,
                "phone": c.phone,
                "linkedin_url": c.linkedin_url,
            }
            break
    if not primary_contact and contacts:
        c = contacts[0]
        primary_contact = {
            "name": c.name,
            "role": c.role_label or (c.role.value if c.role else None),
            "email": c.email,
            "phone": c.phone,
            "linkedin_url": c.linkedin_url,
        }

    pos_factors = []
    neg_factors = []
    for f in (lead.score_factors or []):
        if f.get("impact") == "+":
            pos_factors.append(f)
        else:
            neg_factors.append(f)

    site_audit = build_site_audit(enrichment)

    return {
        "identity": identity,
        "campaign": campaign_context,
        "qualification": {
            "score": lead.qualification_score,
            "priority": lead.priority.value if lead.priority else None,
            "priority_reasoning": lead.priority_reasoning,
            "status": lead.status.value if lead.status else None,
            "primary_need": lead.primary_need,
            "qualification_reason": lead.qualification_reason,
        },
        "executive_summary": lead.executive_summary,
        "pitch": {
            "pitch_angle": lead.pitch_angle,
            "suggested_subject": lead.suggested_subject,
        },
        "score_factors": {
            "positive": pos_factors,
            "negative": neg_factors,
        },
        "evidence": lead.evidence or [],
        "primary_contact": primary_contact,
        "site_audit": site_audit,
    }


def build_lead_pitch_pdf_section(lead: Lead, enrichment: Optional[Enrichment], campaign: Optional[Campaign]) -> str:
    """Gera HTML de uma seção de pitch one-pager para inclusão no PDF."""
    h = html.escape

    score = lead.qualification_score or 0
    priority = lead.priority.value if lead.priority else "—"
    company = h(lead.company_name or "")
    city = h(lead.city or "")
    state = h(lead.state or "")

    executive = h(lead.executive_summary or "Sem resumo executivo.")
    pitch_angle = h(lead.pitch_angle or "")
    suggested_subject = h(lead.suggested_subject or "")
    primary_need = h(lead.primary_need or "")
    reason = h(lead.qualification_reason or "")

    pos_rows = ""
    neg_rows = ""
    for f in (lead.score_factors or []):
        label = h(f.get("label", ""))
        rationale = h(f.get("rationale", ""))
        if f.get("impact") == "+":
            pos_rows += f"<li><strong>{label}</strong> — {rationale}</li>"
        else:
            neg_rows += f"<li><strong>{label}</strong> — {rationale}</li>"

    evidence_rows = ""
    for ev in (lead.evidence or []):
        sev = h(ev.get("severity", "INFO"))
        title = h(ev.get("title", ""))
        desc = h(ev.get("description", ""))
        evidence_rows += f"<tr><td><span class='badge badge-{sev.lower()}'>{sev}</span></td><td><strong>{title}</strong><br/>{desc}</td></tr>"

    site_html = ""
    if enrichment and enrichment.website_exists:
        ssl_label = h(_ssl_label(enrichment))
        cms_label = h(enrichment.cms or "Não identificada")
        speed = h(_speed_label(enrichment.load_time_ms))
        raw = enrichment.raw_technical_data or {}
        seo = _seo_summary(raw)
        seo_html = "".join(f"<li>{h(s)}</li>" for s in seo)
        sec_issues = enrichment.security_issues or []
        sec_html = "".join(f"<li>{h(s)}</li>" for s in sec_issues) if sec_issues else "<li>Nenhum problema detectado</li>"

        site_html = f"""
        <h4>Auditoria do site</h4>
        <table class="mini">
          <tr><td><strong>SSL</strong></td><td>{ssl_label}</td></tr>
          <tr><td><strong>CMS</strong></td><td>{cms_label}</td></tr>
          <tr><td><strong>Performance</strong></td><td>{speed}</td></tr>
        </table>
        <p class="sub">SEO / LGPD:</p><ul class="compact">{seo_html}</ul>
        <p class="sub">Segurança:</p><ul class="compact">{sec_html}</ul>
        """

    campaign_line = ""
    if campaign:
        campaign_line = f"<p class='meta'>Campanha: {h(campaign.name)} — {h(campaign.target_service or '')} / {h(campaign.target_segment or '')}</p>"

    return f"""
    <div class="pitch-card" style="page-break-inside:avoid;margin-bottom:18px;border:1px solid #e2e8f0;border-radius:8px;padding:14px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <h3 style="margin:0;font-size:13pt;">{company}</h3>
        <span class="score" style="font-size:14pt;">{score}</span>
      </div>
      <p class="meta" style="color:#64748b;font-size:8.5pt;margin:0 0 6px 0;">{city}{', ' + state if state else ''} — Prioridade: {priority}</p>
      {campaign_line}
      <p style="font-size:9.5pt;margin:6px 0;">{executive}</p>
      {"<p style='font-size:9pt;'><strong>Gancho:</strong> " + pitch_angle + "</p>" if pitch_angle else ""}
      {"<p style='font-size:9pt;'><strong>Assunto sugerido:</strong> <em>" + suggested_subject + "</em></p>" if suggested_subject else ""}
      {"<p style='font-size:9pt;'><strong>Necessidade primária:</strong> " + primary_need + "</p>" if primary_need else ""}
      {"<p style='font-size:9pt;'><strong>Por que é oportunidade:</strong> " + reason + "</p>" if reason else ""}
      {"<h4>Fatores positivos</h4><ul class='compact'>" + pos_rows + "</ul>" if pos_rows else ""}
      {"<h4>Fatores negativos</h4><ul class='compact'>" + neg_rows + "</ul>" if neg_rows else ""}
      {"<h4>Evidências</h4><table class='mini'>" + evidence_rows + "</table>" if evidence_rows else ""}
      {site_html}
    </div>
    """
