"""Geração do relatório executivo em PDF — Item 2.3 do roadmap.

Renderiza um relatório **completo/detalhado** via WeasyPrint (HTML→PDF):
visão executiva, funil, por campanha, por consultor, top leads, geo e
evolução temporal. Tudo **org-scoped** (os dados vêm do `AnalyticsService`).

Notas:
- No Windows, o WeasyPrint exige o runtime GTK/Pango. Detectamos o diretório
  dos DLLs (`GTK3-Runtime Win64`, `Gtk-Runtime`) e o adicionamos ao search
  path antes do import. Em Linux/macOS o runtime é instalado pelo sistema.
- Cache em memória do HTML agregado (item 2.3.4) para não recalcular em cada
  export. TTL padrão 5 minutos.
"""
import html
import logging
import os
import time
import sys
from typing import Optional

from sqlalchemy.orm import Session

from src.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

# Diretórios comuns do runtime GTK no Windows (ordem de preferência).
_GTK_BIN_DIRS = [
    r"C:\Program Files\GTK3-Runtime Win64\bin",
    r"C:\Program Files\Gtk-Runtime\bin",
]

# Cache do HTML agregado: {key: (timestamp, html_str)}.
_html_cache: dict = {}
_HTML_CACHE_TTL = 300  # segundos


def _setup_windows_gtk() -> None:
    """Adiciona o diretório do runtime GTK ao DLL search path (Windows)."""
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return
    for directory in _GTK_BIN_DIRS:
        if os.path.isdir(directory):
            try:
                os.add_dll_directory(directory)
                return
            except OSError:
                continue


def _weasyprint_available() -> bool:
    try:
        import weasyprint  # noqa: F401
        return True
    except Exception:
        return False


def _cache_key(org_id, from_date, to_date) -> str:
    return f"{org_id}|{from_date or ''}|{to_date or ''}"


def _get_cached(key: str) -> Optional[str]:
    item = _html_cache.get(key)
    if not item:
        return None
    ts, value = item
    if time.time() - ts > _HTML_CACHE_TTL:
        _html_cache.pop(key, None)
        return None
    return value


def _fmt_currency(value: float) -> str:
    try:
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


def _fmt_pct(value: float) -> str:
    return f"{value or 0:.1f}%"


def _bar(value: int, max_value: int) -> str:
    """Barra CSS simples para gráfico em tabelas (proporcional ao máximo)."""
    if max_value <= 0:
        pct = 0
    else:
        pct = int((value or 0) / max_value * 100)
    return (
        f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div>'
        f'<span class="bar-label">{value}</span>'
    )


def _build_html(org_name: str, from_label: str, to_label: str, data: dict) -> str:
    """Monta o HTML do relatório a partir dos dados agregados."""
    ov = data.get("overview", {})
    consultants = data.get("consultants", [])
    campaigns = data.get("campaigns", [])
    ranking = data.get("ranking", {}).get("items", [])
    geo = data.get("geo", {})
    timeline = data.get("timeline", [])

    # ---------- funil (tabela) ----------
    funnel_rows = ""
    max_funnel = max([s.get("count", 0) for s in ov.get("funnel", [])] or [0])
    for stage in ov.get("funnel", []):
        funnel_rows += (
            "<tr>"
            f"<td class='stage-name'>{html.escape(stage['stage'])}</td>"
            f"<td>{_bar(stage['count'], max_funnel)}</td>"
            "</tr>"
        )

    # ---------- KPIs visão executiva ----------
    kpis = [
        ("Leads", ov.get("total_leads", 0)),
        ("Qualificados", ov.get("qualified_leads", 0)),
        ("Contatados", ov.get("contacted_leads", 0)),
        ("Reuniões", ov.get("meetings_scheduled", 0)),
        ("Convertidos", ov.get("converted_leads", 0)),
        ("Receita", _fmt_currency(ov.get("total_revenue", 0))),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="kpi-value">{html.escape(str(v))}</div>'
        f'<div class="kpi-label">{html.escape(k)}</div></div>'
        for k, v in kpis
    )

    rates = [
        ("Conversão", _fmt_pct(ov.get("conversion_rate", 0))),
        ("Taxa de resposta", _fmt_pct(ov.get("response_rate", 0))),
        ("Reunião / qualificado", _fmt_pct(ov.get("meeting_rate", 0))),
    ]
    rates_html = "".join(
        f'<div class="rate"><span class="rate-value">{html.escape(v)}</span>'
        f'<span class="rate-label">{html.escape(k)}</span></div>'
        for k, v in rates
    )

    # ---------- campanhas ----------
    campaign_rows = ""
    max_camp = max([c.get("leads", 0) for c in campaigns] or [0])
    for c in campaigns:
        campaign_rows += (
            "<tr>"
            f"<td class='campaign-name'>{html.escape(c['name'])}</td>"
            f"<td>{_bar(c['leads'], max_camp)}</td>"
            f"<td>{c['qualified_leads']}</td>"
            f"<td>{c['meetings']}</td>"
            f"<td>{c['converted_leads']}</td>"
            f"<td>{_fmt_pct(c['conversion_rate'])}</td>"
            f"<td>{_fmt_currency(c['revenue'])}</td>"
            "</tr>"
        )
    if not campaigns:
        campaign_rows = (
            "<tr><td colspan='7' class='empty'>Nenhuma campanha no período.</td></tr>"
        )

    # ---------- consultores ----------
    consultant_rows = ""
    max_cons = max([c.get("assigned_leads", 0) for c in consultants] or [0])
    for c in consultants:
        consultant_rows += (
            "<tr>"
            f"<td>{html.escape(c['name'] or 'Sem nome')}</td>"
            f"<td>{_bar(c['assigned_leads'], max_cons)}</td>"
            f"<td>{c['contacted_leads']}</td>"
            f"<td>{c['meetings']}</td>"
            f"<td>{c['proposals_sent']}</td>"
            f"<td>{c['converted_leads']}</td>"
            f"<td>{_fmt_pct(c['conversion_rate'])}</td>"
            "</tr>"
        )
    if not consultants:
        consultant_rows = (
            "<tr><td colspan='7' class='empty'>Nenhum consultor no período.</td></tr>"
        )

    # ---------- top leads ----------
    ranking_rows = ""
    for i, lead in enumerate(ranking[:20], start=1):
        status = lead.get("status") or "—"
        conv_badge = (
            '<span class="badge badge-converted">Convertido</span>'
            if lead.get("converted")
            else f'<span class="badge badge-status">{html.escape(status)}</span>'
        )
        ranking_rows += (
            "<tr>"
            f"<td class='num'>{i}</td>"
            f"<td>{html.escape(lead['company_name'])}</td>"
            f"<td>{html.escape(lead.get('city') or '—')}</td>"
            f"<td>{html.escape(lead.get('state') or '—')}</td>"
            f"<td class='score'>{lead.get('qualification_score', 0)}</td>"
            f"<td>{conv_badge}</td>"
            "</tr>"
        )
    if not ranking:
        ranking_rows = (
            "<tr><td colspan='6' class='empty'>Nenhum lead no período.</td></tr>"
        )

    # ---------- geo ----------
    geo_rows = ""
    max_geo = max([c.get("count", 0) for c in geo.get("cities", [])] or [0])
    for c in geo.get("cities", [])[:12]:
        geo_rows += (
            "<tr>"
            f"<td>{html.escape(c['city'])}</td>"
            f"<td>{html.escape(c.get('state') or '—')}</td>"
            f"<td>{_bar(c['count'], max_geo)}</td>"
            f"<td>{c.get('avg_score', 0)}</td>"
            f"<td>{c.get('converted', 0)}</td>"
            "</tr>"
        )
    if not geo.get("cities"):
        geo_rows = "<tr><td colspan='5' class='empty'>Sem dados geográficos.</td></tr>"

    # ---------- timeline (gráfico de barras CSS) ----------
    timeline_html = ""
    if timeline:
        max_tl = max([max(r.get("new_leads", 0), r.get("meetings", 0), r.get("closed", 0)) for r in timeline] or [1])
        bars = ""
        for r in timeline[:14]:
            d = (r.get("date") or "")[:10]
            new_h = max(4, int((r.get("new_leads", 0) or 0) / max_tl * 80))
            meet_h = max(4, int((r.get("meetings", 0) or 0) / max_tl * 80))
            closed_h = max(4, int((r.get("closed", 0) or 0) / max_tl * 80))
            bars += (
                f'<div class="tl-col">'
                f'<div class="tl-stack">'
                f'<div class="tl-bar tl-new" style="height:{new_h}px"></div>'
                f'<div class="tl-bar tl-meeting" style="height:{meet_h}px"></div>'
                f'<div class="tl-bar tl-closed" style="height:{closed_h}px"></div>'
                f'</div>'
                f'<div class="tl-date">{html.escape(d)}</div>'
                f'</div>'
            )
        timeline_html = (
            '<div class="timeline-chart">' + bars + "</div>"
            '<div class="legend">'
            '<span><span class="dot dot-new"></span> Novos</span>'
            '<span><span class="dot dot-meeting"></span> Reuniões</span>'
            '<span><span class="dot dot-closed"></span> Fechados</span>'
            "</div>"
        )

    period_label = f"{html.escape(from_label)} — {html.escape(to_label)}"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4;
    margin: 2cm 1.8cm;
    @bottom-center {{
      content: "Agente Prospecção — Página " counter(page) " de " counter(pages);
      font-size: 8pt;
      color: #94a3b8;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    color: #1e293b;
    font-size: 9.5pt;
    line-height: 1.45;
    margin: 0;
  }}
  .header {{
    border-bottom: 3px solid #0f766e;
    padding-bottom: 14px;
    margin-bottom: 18px;
  }}
  .header h1 {{
    font-size: 20pt;
    margin: 0 0 4px 0;
    color: #0f172a;
  }}
  .header .org {{
    font-size: 12pt;
    color: #0f766e;
    font-weight: 600;
  }}
  .header .period {{
    font-size: 9pt;
    color: #64748b;
    margin-top: 4px;
  }}
  h2 {{
    font-size: 13pt;
    color: #0f172a;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 4px;
    margin: 22px 0 10px 0;
  }}
  .kpis {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 6px;
  }}
  .kpi {{
    flex: 1 1 15%;
    min-width: 90px;
    background: #f1f5f9;
    border-radius: 8px;
    padding: 10px 12px;
    text-align: center;
  }}
  .kpi-value {{ font-size: 15pt; font-weight: 700; color: #0f172a; }}
  .kpi-label {{ font-size: 8pt; color: #64748b; margin-top: 2px; }}
  .rates {{
    display: flex;
    gap: 12px;
    margin: 8px 0;
  }}
  .rate {{
    display: flex; flex-direction: column; align-items: center;
    background: #0f766e; color: #fff; border-radius: 8px; padding: 8px 16px;
  }}
  .rate-value {{ font-size: 14pt; font-weight: 700; }}
  .rate-label {{ font-size: 7.5pt; opacity: 0.85; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 6px 0 12px 0;
  }}
  th {{
    text-align: left;
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #64748b;
    border-bottom: 1.5px solid #cbd5e1;
    padding: 5px 6px;
  }}
  td {{
    padding: 5px 6px;
    border-bottom: 1px solid #e2e8f0;
    vertical-align: middle;
  }}
  tr:last-child td {{ border-bottom: none; }}
  .num {{ color: #94a3b8; width: 24px; }}
  .score {{ font-weight: 700; color: #0f766e; }}
  .empty {{ color: #94a3b8; text-align: center; padding: 14px; font-style: italic; }}
  .bar-track {{
    display: inline-block; vertical-align: middle;
    width: 120px; height: 8px; background: #e2e8f0; border-radius: 4px;
    margin-right: 6px; overflow: hidden;
  }}
  .bar-fill {{ height: 100%; background: #0f766e; border-radius: 4px; }}
  .bar-label {{ font-size: 8.5pt; color: #334155; }}
  .badge {{
    display: inline-block; font-size: 7.5pt; padding: 2px 7px;
    border-radius: 999px;
  }}
  .badge-converted {{ background: #d1fae5; color: #065f46; }}
  .badge-status {{ background: #e2e8f0; color: #334155; }}
  .timeline-chart {{
    display: flex; align-items: flex-end; gap: 6px;
    height: 130px; padding-top: 10px; border-bottom: 1px solid #cbd5e1;
  }}
  .tl-col {{ flex: 1; text-align: center; }}
  .tl-stack {{
    display: flex; align-items: flex-end; justify-content: center; gap: 2px;
    height: 90px;
  }}
  .tl-bar {{ width: 8px; border-radius: 2px 2px 0 0; }}
  .tl-new {{ background: #0f766e; }}
  .tl-meeting {{ background: #f59e0b; }}
  .tl-closed {{ background: #6366f1; }}
  .tl-date {{ font-size: 7pt; color: #94a3b8; margin-top: 4px; }}
  .legend {{ font-size: 8pt; color: #475569; margin-top: 6px; }}
  .legend span {{ margin-right: 14px; }}
  .dot {{ display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 4px; }}
  .dot-new {{ background: #0f766e; }}
  .dot-meeting {{ background: #f59e0b; }}
  .dot-closed {{ background: #6366f1; }}
  .footer-note {{ font-size: 7.5pt; color: #94a3b8; margin-top: 24px; border-top: 1px solid #e2e8f0; padding-top: 8px; }}
</style>
</head>
<body>
  <div class="header">
    <h1>Relatório de Prospecção</h1>
    <div class="org">{html.escape(org_name)}</div>
    <div class="period">Período: {period_label}</div>
  </div>

  <h2>Visão executiva</h2>
  <div class="kpis">{kpi_html}</div>
  <div class="rates">{rates_html}</div>

  <h2>Funil</h2>
  <table>
    <thead><tr><th>Etapa</th><th>Leads</th></tr></thead>
    <tbody>{funnel_rows}</tbody>
  </table>

  <h2>Desempenho por campanha</h2>
  <table>
    <thead><tr><th>Campanha</th><th>Leads</th><th>Qualificados</th><th>Reuniões</th><th>Convertidos</th><th>Conv. %</th><th>Receita</th></tr></thead>
    <tbody>{campaign_rows}</tbody>
  </table>

  <h2>Desempenho por consultor</h2>
  <table>
    <thead><tr><th>Consultor</th><th>Atribuídos</th><th>Contatados</th><th>Reuniões</th><th>Propostas</th><th>Convertidos</th><th>Conv. %</th></tr></thead>
    <tbody>{consultant_rows}</tbody>
  </table>

  <h2>Top leads</h2>
  <table>
    <thead><tr><th>#</th><th>Empresa</th><th>Cidade</th><th>UF</th><th>Score</th><th>Status</th></tr></thead>
    <tbody>{ranking_rows}</tbody>
  </table>

  <h2>Distribuição geográfica</h2>
  <table>
    <thead><tr><th>Cidade</th><th>UF</th><th>Leads</th><th>Score médio</th><th>Convertidos</th></tr></thead>
    <tbody>{geo_rows}</tbody>
  </table>

  <h2>Evolução temporal</h2>
  {timeline_html}

  <div class="footer-note">
    Relatório gerado automaticamente pelo Agente Prospecção. Dados restritos à organização
    e ao período selecionado. Análise de sites 100% passiva (Lei 12.737/2012).
  </div>
</body>
</html>"""


def build_report_pdf(
    db: Session,
    org_name: str,
    org_id,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> bytes:
    """Gera o PDF do relatório executivo da organização.

    Reusa `AnalyticsService` (org-scoped). Lança `RuntimeError` se o WeasyPrint
    não estiver disponível no ambiente (fallback para o caller tratar 503).
    """
    svc = AnalyticsService(db, org_id)

    data = {
        "overview": svc.overview(from_date=from_date, to_date=to_date),
        "consultants": svc.consultants(from_date=from_date, to_date=to_date),
        "campaigns": svc.campaigns(from_date=from_date, to_date=to_date),
        "ranking": svc.leads_ranking(sort_by="score", from_date=from_date, to_date=to_date, limit=20),
        "geo": svc.geo(from_date=from_date, to_date=to_date),
        "timeline": svc.timeline(group_by="day", from_date=from_date, to_date=to_date),
    }

    from_label = from_date or "início"
    to_label = to_date or "hoje"
    key = _cache_key(org_id, from_date, to_date)
    cached = _get_cached(key)
    if cached:
        html_content = cached
    else:
        html_content = _build_html(org_name, from_label, to_label, data)
        _html_cache[key] = (time.time(), html_content)

    _setup_windows_gtk()
    if not _weasyprint_available():
        raise RuntimeError("WeasyPrint indisponível no ambiente (runtime GTK/Pango ausente)")

    import weasyprint

    doc = weasyprint.HTML(string=html_content).render()
    return doc.write_pdf()
