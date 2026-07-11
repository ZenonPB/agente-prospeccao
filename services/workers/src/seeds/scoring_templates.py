"""Seed default CampaignScoringTemplate para categorias de serviço comuns.

Executar dentro de services/workers/:
    python -m src.seeds.scoring_templates

Idempotente: usa `service_label` (LOWER) como chave — se já existir, atualiza
positive/negative signals e extra_instructions.

Para adicionar uma nova categoria, basta adicionar uma entrada em DEFAULT_TEMPLATES
abaixo ou inserir diretamente um row na tabela campaign_scoring_templates.
"""
import logging
import sys
import os

# Garante que src/ esteja no path tanto para `python -m src.seeds.scoring_templates`
# quanto para `python src/seeds/scoring_templates.py` (cd obrigatório a services/workers).
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, '..'))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from sqlalchemy import func as sqlfunc

from database.session import SessionLocal
from database.models import CampaignScoringTemplate

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')


# Cada template tem:
#   service_label: rótulo único (chave natural; comparado com LOWER())
#   positive_signals: lista de {label, description, weight_hint}
#     weight_hint ∈ "high" | "medium" | "low" — dica de peso relativo
#   negative_signals: mesma estrutura, reduz score quando presente
#   context_signals: sinais contextuais adicionais (região, segmento etc.)
#   requires_technical_report: se a análise técnica do site é relevante
#   requires_business_data: se dados cadastrais (categoria/porte) são relevantes
#   extra_instructions: instrução textual livre injetada no prompt

DEFAULT_TEMPLATES = [
    # ----- Web / Dev -----
    {
        "service_label": "Desenvolvimento de Sites",
        "requires_technical_report": True,
        "requires_business_data": True,
        "positive_signals": [
            {"label": "Site desatualizado / CMS antigo", "description": "WordPress antigo, Joomla, ou sem framework moderno", "weight_hint": "high"},
            {"label": "Ausência de HTTPS / SSL inválido", "description": "Site servido em HTTP sem redirecionamento ou certificado vencido", "weight_hint": "high"},
            {"label": "SEO fraco (title/meta/h1)", "description": "Metadata mínima ou ausente, sem h1", "weight_hint": "medium"},
            {"label": "Site lento", "description": "Load time > 3s", "weight_hint": "medium"},
            {"label": "Sem LGPD/cookies", "description": "Ausência de menção a privacidade na home", "weight_hint": "low"},
            {"label": "Sem formulário / CTA claros", "description": "Sem formulário de contato visível", "weight_hint": "medium"},
            {"label": "Sem responsividade", "description": "Layout não mobile-friendly", "weight_hint": "medium"},
        ],
        "negative_signals": [
            {"label": "Site moderno (Next.js/Nuxt/Astro)", "description": "Stack atual", "weight_hint": "high"},
            {"label": "SSL bem configurado + HSTS", "description": "Headers de segurança presentes", "weight_hint": "medium"},
            {"label": "Site rápido + SEO completo", "description": "Performance e SEO sólidos", "weight_hint": "medium"},
        ],
        "context_signals": [
            {"label": "Segmento", "description": "Considerar fito do segmento com serviços digitais"},
            {"label": "Região", "description": "Presença regional indica oportunidade de agência"},
        ],
        "extra_instructions": (
            "Concentre a análise em oportunidades de modernização/desenvolvimento de site. "
            "Use os dados técnicos do site como evidência primária."
        ),
    },
    {
        "service_label": "SEO / Marketing Digital",
        "requires_technical_report": True,
        "requires_business_data": True,
        "positive_signals": [
            {"label": "SEO técnico ruim", "description": "Title/meta/h1 ausentes ou mal formatados", "weight_hint": "high"},
            {"label": "Sem menção a LGPD/cookies", "description": "Risco legal para marketing", "weight_hint": "medium"},
            {"label": "Performance fraca", "description": "Site lento", "weight_hint": "medium"},
            {"label": "Sem CTA / captura de leads", "description": "Sem formulário visível", "weight_hint": "medium"},
            {"label": "Conteúdo institucional magro", "description": "Poucas páginas/descrições curtas", "weight_hint": "low"},
        ],
        "negative_signals": [
            {"label": "SEO completo (title=h1, meta description, structure)", "description": "Prática sólida", "weight_hint": "high"},
            {"label": "Site rápido + responsivo", "description": "Boa base técnica", "weight_hint": "low"},
        ],
        "extra_instructions": (
            "Priorize sinais de SEO e marketing. Se a empresa já investe em performance, "
            "identifique gaps de conteúdo ou conversão."
        ),
    },
    # ----- Industrial / Engenharia -----
    {
        "service_label": "Engenharia Mecânica",
        "requires_technical_report": False,
        "requires_business_data": True,
        "positive_signals": [
            {"label": "Tipo de empresa industrial", "description": "Indústria/fábrica vs. apenas escritório", "weight_hint": "high"},
            {"label": "Porte médio/grande", "description": "Indícios de capacity para projetos complexos", "weight_hint": "high"},
            {"label": "Sinais de expansão", "description": "Filial nova, nova linha de produção etc. (inferível do nome/categoria)", "weight_hint": "high"},
            {"label": "Setor com necessidade de automação", "description": "Metalomecânica, plásticos, automotivo etc.", "weight_hint": "high"},
            {"label": "Sinais de processos manuais", "description": "Sem menção a sistemas ERP/sistemas, site institucional básico", "weight_hint": "medium"},
            {"label": "Equipamentos/investimento em ativos", "description": "Categoria sugere CAPEX (usinagem, caldeiraria etc.)", "weight_hint": "medium"},
            {"label": "Frota/logística própria", "description": "Indica operação complexa com potenciais ganhos", "weight_hint": "low"},
        ],
        "negative_signals": [
            {"label": "Microempresa de serviços sob medida", "description": "Sem capacidade de projeto de engenharia", "weight_hint": "medium"},
            {"label": "Categoria não-industrial", "description": "Restaurante, varejo, etc.", "weight_hint": "high"},
        ],
        "context_signals": [
            {"label": "Segmento industrial", "description": "Metalomecânica, plásticos, automotivo, alimento, bebida, energia"},
            {"label": "Região", "description": "Polo industrial regional indica densidade de oportunidade"},
        ],
        "extra_instructions": (
            "NÃO basear a análise em HTTPS/SSL/SEO/performance do site (são pouco "
            "relevantes para vender engenharia mecanica). Priorize sinais de porte, "
            "setor industrial, expansão, equipamentos e processos. Se um site "
            "estiver desatualizado, mencione apenas como evidência secundaria."
        ),
    },
    {
        "service_label": "Automação Industrial",
        "requires_technical_report": False,
        "requires_business_data": True,
        "positive_signals": [
            {"label": "Linha de produção / manufatura", "description": "Categoria sugere fábrica em operação", "weight_hint": "high"},
            {"label": "Sinais de processos manuais / programs legados", "description": "Sem menção a CLP/IoT/SCADA", "weight_hint": "high"},
            {"label": "Escalando produção", "description": "Filial nova / expansão", "weight_hint": "high"},
            {"label": "Setor comum para automação", "description": "Plásticos, alimentos, embalagens, logística", "weight_hint": "medium"},
        ],
        "negative_signals": [
            {"label": "Empresa puramente serviços", "description": "Sem produção física", "weight_hint": "high"},
        ],
        "extra_instructions": (
            "Foque em sinais de operações industriais que podem se beneficiar de "
            "automação. Ignore completamente qualidade do site."
        ),
    },
    # ----- Marketing Digital para varejo específico -----
    {
        "service_label": "Marketing Digital para Petshops",
        "requires_technical_report": True,
        "requires_business_data": True,
        "positive_signals": [
            {"label": "Petshop ativo no Google Places", "description": "Categoria indica operação real de varejo pet", "weight_hint": "high"},
            {"label": "Site ausente ou desatualizado", "description": "Baixa presença digital em segmento que depende de captura local", "weight_hint": "high"},
            {"label": "Sem Google Meu Negócio otimizado", "description": "Descrição curta, sem produtos/serviços destacados", "weight_hint": "medium"},
            {"label": "Ausência de WhatsApp/CTA visível no site", "description": "Perde conversão de clientes que querem agendar banho/tosa/vet", "weight_hint": "high"},
            {"label": "SEO local fraco", "description": "Title/meta ausentes, sem menção à cidade", "weight_hint": "medium"},
            {"label": "Sem e-commerce / catálogo de produtos", "description": "Perde venda de ração/acessórios para concorrentes online", "weight_hint": "medium"},
            {"label": "Sem campanhas de captação de leads", "description": "Sem formulário visível ou popup", "weight_hint": "medium"}
        ],
        "negative_signals": [
            {"label": "Site moderno com e-commerce integrado", "description": "Já tem loja online atualizada", "weight_hint": "high"},
            {"label": "Presença digital madura", "description": "Site responsivo + SEO local + CTA WhatsApp", "weight_hint": "medium"}
        ],
        "context_signals": [
            {"label": "Região", "description": "Petshops dependem de tráfego local — considerar densidade urbana"},
            {"label": "Serviços adicionais", "description": "Banho/tosa/veterinária aumentam ticket médio e LTV"}
        ],
        "extra_instructions": (
            "Foque em oportunidades de marketing digital para petshops: captura local "
            "(Google Meu Negócio), conversão via WhatsApp, e-commerce de ração/acessórios. "
            "Não valorize apenas qualidade técnica do site — pondere SEO local e CTA."
        ),
    },
    {
        "service_label": "Marketing Digital para Academias",
        "requires_technical_report": True,
        "requires_business_data": True,
        "positive_signals": [
            {"label": "Academia ativa no Google Places", "description": "Categoria sugere operação real", "weight_hint": "high"},
            {"label": "Sem site ou site básico institucional", "description": "Baixa capacidade de captação digital de alunos", "weight_hint": "high"},
            {"label": "Sem área de membros/agendamento online", "description": "Perde retenção e upsell de planos", "weight_hint": "high"},
            {"label": "Sem vitrine de planos/preços", "description": "Falta clareza comercial = conversão baixa", "weight_hint": "medium"},
            {"label": "CTA/WhatsApp não evidente", "description": "Lead interessado não consegue agendar aula experimental", "weight_hint": "high"},
            {"label": "Conteúdo fraco em redes sociais", "description": "Sem integração visível IG/FB no site", "weight_hint": "medium"}
        ],
        "negative_signals": [
            {"label": "Academia com app próprio e área membros", "description": "Stack madura", "weight_hint": "high"},
            {"label": "Site moderno com agendamento + vitrine de planos", "description": "Boa presença digital", "weight_hint": "medium"}
        ],
        "extra_instructions": (
            "Foque em oportunidades de marketing digital para academias: captação de "
            "alunos (landing pages, anúncios), retenção via área de membros e agendamento. "
            "Pondere fortemente ausência de CTA/WhatsApp e ausência de vitrine de planos."
        ),
    },
    {
        "service_label": "Marketing Digital para Farmácias",
        "requires_technical_report": True,
        "requires_business_data": True,
        "positive_signals": [
            {"label": "Farmácia ativa no Google Places", "description": "Operação real de varejo farmacêutico", "weight_hint": "high"},
            {"label": "Sem site ou site institucional básico", "description": "Perde captação digital de clientes", "weight_hint": "high"},
            {"label": "Sem e-commerce / entrega online", "description": "Perde vendas para apps concorrentes (RD Saúde, Afya)", "weight_hint": "high"},
            {"label": "Sem programa de fidelidade digital", "description": "Oportunidade de retenção/LTV", "weight_hint": "medium"},
            {"label": "Sem clareza em serviços (receitas, convênios)", "description": "Perde leads de clientes que buscam conveniência", "weight_hint": "medium"},
            {"label": "WhatsApp/CTA não visível", "description": "Perde pedidos de entrega de receitas", "weight_hint": "high"}
        ],
        "negative_signals": [
            {"label": "Farmácia com e-commerce próprio e entrega", "description": "Stack madura", "weight_hint": "high"},
            {"label": "Site moderno com app de receitas e fidelidade", "description": "Boa presença digital", "weight_hint": "medium"}
        ],
        "extra_instructions": (
            "Foque em oportunidades de marketing digital para farmácias: e-commerce "
            "de medicamentos, gestão de receitas online, programa de fidelidade. "
            "Pondere ausência de CTA/WhatsApp e ausência de delivery como prioridades."
        ),
    },
    # ----- Serviços gerais -----
    {
        "service_label": "Consultoria Empresarial",
        "requires_technical_report": False,
        "requires_business_data": True,
        "positive_signals": [
            {"label": "Empresa com certo porte", "description": "Indícios de estrutura organizacional", "weight_hint": "high"},
            {"label": "Crescimento/expansão", "description": "Sinais de abertura de filiais / nova área", "weight_hint": "high"},
            {"label": "Setor em transformação", "description": "Mudanças regulatórias, digital etc.", "weight_hint": "medium"},
            {"label": "Equipe / organograma mencionado", "description": "Indica maturidade gerencial", "weight_hint": "medium"},
        ],
        "negative_signals": [
            {"label": "Microempreendedor individual", "description": "Sem equipe / estrutura", "weight_hint": "high"},
        ],
        "extra_instructions": (
            "Foque em maturidade organizacional e sinais de crescimento. "
            "Site é evidência secundária."
        ),
    },
    {
        "service_label": "Genérico",
        "requires_technical_report": True,
        "requires_business_data": True,
        "positive_signals": [
            {"label": "Site desatualizado", "description": "Tecnologias antigas detectadas", "weight_hint": "medium"},
            {"label": "Empresa ativa / porte relevante", "description": "Categoria e localização sugerem operação real", "weight_hint": "medium"},
            {"label": "Sinais de crescimento", "description": "Expansão, nova filial, novos serviços", "weight_hint": "medium"},
        ],
        "negative_signals": [
            {"label": "Indústria inativa ou kategória irrelevante", "description": "Sem fito com o serviço", "weight_hint": "medium"},
        ],
        "extra_instructions": (
            "Template genérico usado quando target_service da campanha não tem "
            "template específico. A IA deve inferir critérios relevantes a partir "
            "do target_service e target_segment fornecidos."
        ),
    },
]


def upsert_template(db, tmpl: dict) -> CampaignScoringTemplate:
    label_lower = tmpl["service_label"].lower().strip()
    existing = db.query(CampaignScoringTemplate).filter(
        sqlfunc.lower(CampaignScoringTemplate.service_label) == label_lower
    ).first()

    fields = {
        "service_label": tmpl["service_label"],
        "positive_signals": tmpl["positive_signals"],
        "negative_signals": tmpl["negative_signals"],
        "context_signals": tmpl.get("context_signals", []),
        "requires_technical_report": tmpl.get("requires_technical_report", True),
        "requires_business_data": tmpl.get("requires_business_data", True),
        "extra_instructions": tmpl.get("extra_instructions"),
        "is_active": True,
    }

    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        db.flush()
        logger.info("Atualizado template: %s", existing.service_label)
        return existing

    obj = CampaignScoringTemplate(**fields)
    db.add(obj)
    db.flush()
    logger.info("Criado template: %s", obj.service_label)
    return obj


def run_seed():
    db = SessionLocal()
    try:
        for tmpl in DEFAULT_TEMPLATES:
            upsert_template(db, tmpl)
        db.commit()
        logger.info("Seed finalizado: %d templates ativos",
                    db.query(CampaignScoringTemplate).filter(CampaignScoringTemplate.is_active.is_(True)).count())
    except Exception as e:
        db.rollback()
        logger.error("Erro no seed: %s", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
