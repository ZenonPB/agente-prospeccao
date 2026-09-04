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
#   enrichment_steps: opcional — fontes de informação ("technical_site" |
#     "cnpj_receita" | "business_social"); ausente = derivado dos flags
#   cadence_schedule: opcional — [dia 1ª msg, dia 2ª msg, dia 3ª msg, dia
#     encerramento]; ausente = [0, 3, 7, 14]
#   extra_instructions: instrução textual livre injetada no prompt

DEFAULT_TEMPLATES = [
    # ----- Web / Dev -----
    {
        "service_label": "Desenvolvimento de Sites",
        "requires_technical_report": True,
        "requires_business_data": True,
        # Pré-scoring de discovery (docs/melhorias/01): ausência de site é
        # público-alvo, mas SÓ pontua com alguma presença ativa — sem site E
        # sem nenhuma presença digital não é bom lead de landing page.
        # Empresa COM site também é alvo (site desatualizado = ICP clássico):
        # HAS_OWN_WEBSITE pontua menos que a ausência com tração, mas passa.
        "prescoring_config": {
            "profile": "web_presence",
            "enabled": True,
            "threshold": 45,
            "weights": {
                "HAS_OWN_WEBSITE": 20,
                "NO_OWN_WEBSITE": 25,
                "HAS_INSTAGRAM": 12,
                "HAS_PHONE": 8,
                "GOOGLE_RATING": 15,
                "GOOGLE_RATING_COUNT": 15,
            },
        },
        "playbook": {
            "hooks": [
                "Site da empresa perde cliente porque não converte (sem CTA/formulário na home)",
                "Versão do CMS/plataforma desatualizada deixa o site lento e inseguro",
                "Empresa aparece bem no Google/Maps mas o site não vende — primeira impressão errada",
            ],
            "subject_ideas": [
                "Seu site ainda usa {tech}?",
                "Sobre o {problema_concreto} do site",
                "{empresa} sem formulário de contato na home",
            ],
            "objections": [
                {"objection": "Já temos alguém que cuida do site", "approach": "Oferecer auditoria gratuita comparando com boas práticas atuais"},
                {"objection": "Orçamento apertado", "approach": "Mostrar o custo de continuar sem conversão — site é canal que deveria vender"},
                {"objection": "Não dá tempo de trocar agora", "approach": "Propor mudança incremental: home + formulário primeiro, resto depois"},
            ],
        },
        "positive_signals": [
            {"label": "Site desatualizado / CMS antigo", "description": "WordPress antigo, Joomla, ou sem framework moderno", "weight_hint": "high"},
            {"label": "Ausência de HTTPS / SSL inválido", "description": "Site servido em HTTP sem redirecionamento ou certificado vencido", "weight_hint": "high"},
            {"label": "SEO fraco (title/meta/h1)", "description": "Metadata mínima ou ausente, sem h1", "weight_hint": "medium"},
            {"label": "Site lento", "description": "Load time > 3s", "weight_hint": "medium"},
            {"label": "Sem LGPD/cookies", "description": "Ausência de menção a privacidade na home", "weight_hint": "low"},
            {"label": "Sem formulário / CTA claros", "description": "Critério a CONFIRMAR no HTML: sem formulário de contato visível nem CTA na home", "weight_hint": "medium"},
            {"label": "Sem responsividade (viewport ausente)", "description": "Critério a CONFIRMAR no HTML: meta viewport ausente — provável layout não mobile-friendly", "weight_hint": "medium"},
            {"label": "Sem site próprio / sem presença digital", "description": "Empresa sem website próprio (usa Instagram/Canva/WhatsApp ou não tem presença) — público-alvo direto para desenvolvimento de site", "weight_hint": "high"},
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
            "Use os dados técnicos do site como evidência primária. "
            "Empresa SEM site próprio ou com presença apenas via redes sociais "
            "(Instagram/WhatsApp/Canva) é PÚBLICO-ALVO PRIORITÁRIO para desenvolvimento "
            "de site — trate a ausência de site como oportunidade FORTE (aumenta o score), "
            "nunca como desqualificação. Para esses leads não há relatório técnico: avalie "
            "o fito pelo segmento, categoria e localização."
        ),
    },
    {
        "service_label": "Landing Pages",
        "requires_technical_report": False,
        "requires_business_data": False,
        # Busca multi-query (docs/melhorias/04): variedade semântica já sugerida
        # no template para subnichos de conversão.
        "enrichment_steps": ["business_social", "technical_site"],
        # Landing Page (docs/melhorias/03): o prospect ideal já tem tráfego e
        # reputação mas NÃO converte. Ausência de site SÓ pontua combinada com
        # presença ativa (Instagram/reviews) — ausência total de demanda não
        # vira lead quente.
        "prescoring_config": {
            "profile": "web_presence",
            "enabled": True,
            "threshold": 45,
            "weights": {
                "NO_OWN_WEBSITE": 30,
                "HAS_INSTAGRAM": 15,
                "HAS_PHONE": 8,
                "GOOGLE_RATING": 15,
                "GOOGLE_RATING_COUNT": 15,
            },
        },
        "playbook": {
            "hooks": [
                "Empresa aparece bem no Google/Instagram mas não tem página de conversão — perde cliente para quem tem",
                "Sem site próprio, pedidos/orçamentos dependem de WhatsApp/Instagram e o funil não escala",
                "Presença forte nas redes sem CTA: visita vira 'curtida', não vira lead",
            ],
            "subject_ideas": [
                "Sua página de conversão {empresa}",
                "Seu Instagram atrai — mas converte? Landing page para {serviço}",
                "{empresa} sem formulário/orçamento online",
            ],
            "objections": [
                {"objection": "Já temos Instagram/WhatsApp", "approach": "Reforçar que redes geram contato, mas não funil/tracking; propor landing como camada de conversão e medição"},
                {"objection": "Já temos site", "approach": "Perguntar se o site converte (formulário, CTA, orçamento online); se não, é exatamente o caso de landing"},
                {"objection": "Orçamento apertado", "approach": "Mostrar custo da dependência de WhatsApp/Instagram e o retorno de uma página de conversão simples"},
            ],
        },
        "positive_signals": [
            {"label": "Sem site próprio / sem página de conversão", "description": "Empresa sem website próprio (usa Instagram/Canva/WhatsApp) OU site institucional sem CTA/formulário — público-alvo direto para landing page", "weight_hint": "high"},
            {"label": "Instagram ativo", "description": "Perfil ativo com conteúdo recente — tráfego que não converte", "weight_hint": "medium"},
            {"label": "Reputação Google forte", "description": "Nota >= 4.0 — confiança prévia que uma landing capitaliza", "weight_hint": "medium"},
            {"label": "Volume de avaliações", "description": "Muitas avaliações (>= 30) — negócio com movimento e prova social", "weight_hint": "medium"},
            {"label": "Negócio orientado a agendamento/orçamento", "description": "Setor que vende por orçamento/agenda (salão, clínica, oficina, serviço) — conversão direta na landing", "weight_hint": "medium"},
            {"label": "Dependência de WhatsApp", "description": "Atendimento concentra em WhatsApp — sinal de demanda sem funil", "weight_hint": "low"},
            {"label": "Bom valor por conversão", "description": "Ticket médio do setor comporta investimento em conversão", "weight_hint": "low"},
        ],
        "negative_signals": [
            {"label": "Landing page já forte / converte", "description": "Página de conversão dedicada com CTA/formulário ativo — já tem o que venderíamos", "weight_hint": "high"},
            {"label": "Rede / franquia com presença nacional", "description": "Estrutura corporativa que já investe em conversão", "weight_hint": "medium"},
            {"label": "Atividade digital quase inexistente", "description": "Sem site, sem redes ativas, sem avaliações recentes — ausência de demanda, não só de conversão", "weight_hint": "high"},
            {"label": "Lead sem canal acionável", "description": "Sem telefone/Instagram/WhatsApp/e-mail público — impossível iniciar contato", "weight_hint": "high"},
        ],
        "context_signals": [
            {"label": "Segmento de conversão", "description": "Salões, clínicas, oficinas, serviços locais — negócios que vivem de orçamento/agenda"},
            {"label": "Região", "description": "Presença regional e disputa local por cliente"},
            {"label": "Reputação vs presença", "description": "Boa reputação Google com presença fraca = capital que uma landing converte"},
        ],
        "extra_instructions": (
            "Venda de landing pages (página de conversão). O prospect ideal TEM "
            "tráfego/reputação/presença social mas NÃO possui página dedicada à "
            "conversão (CTA, formulário, orçamento). NÃO infira que toda empresa "
            "sem site é boa: ausência de site só pontua quando combinada com "
            "sinais de tração (Instagram ativo, avaliações, telefone acionável). "
            "Empresa sem site, sem reviews e sem social é ausência de demanda — "
            "não é lead quente. Distinga presença digital sem conversão (público-alvo) "
            "de ausência total de atividade digital (não prospectar)."
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
    {
        "service_label": "Aplicações Web / ERP",
        "requires_technical_report": True,
        "requires_business_data": True,
        # Fit de ERP vem do cadastro/porte — site próprio vale pouco e
        # reputação Google pesa menos que em Landing Pages.
        "prescoring_config": {
            "profile": "business_opportunity",
            "enabled": True,
            # O fit de ERP vem do cadastro (CNAE/porte/idade), pós-gate. O
            # pré-score só corta ausência total de presença — site
            # institucional sem sistema é o público-alvo e precisa passar.
            "threshold": 15,
        },
        "playbook": {
            "hooks": [
                "Empresa ainda opera com planilha/processo manual que um sistema resolveria",
                "Site é só institucional/landing sem área logada — o negócio continua no papel",
                "Crescimento recente e sem sistema: pedidos, agenda e estoque espalhados",
                "Já usa plataforma SaaS (anota.ai, iFood) só para pedidos — e o resto da operação?",
            ],
            "subject_ideas": [
                "Como está o processo de {processo_concreto} hoje na {empresa}?",
                "{empresa} ainda usa planilha para {problema_concreto}?",
                "Sistema para o crescimento da {empresa}",
                "Vocês usam {plataforma_saas} para pedidos — e para estoque/financeiro?",
            ],
            "objections": [
                {"objection": "Já temos um sistema", "approach": "Perguntar o que ele não cobre hoje (relatório, integração, mobilidade) e propor reunião de diagnóstico"},
                {"objection": "Já usamos anota.ai/iFood", "approach": "Reforçar que SaaS de delivery cobre apenas pedidos; perguntar sobre estoque/financeiro/agenda/CRM"},
                {"objection": "É muito caro", "approach": "Mostrar o custo do processo manual (erro humano, tempo, retrabalho) frente a um portal sob medida"},
                {"objection": "Não dá tempo de implantar", "approach": "Propor implantação por fases: módulo crítico primeiro, resto depois"},
            ],
        },
        "positive_signals": [
            {"label": "Sem área logada / portal do cliente", "description": "Nenhuma área logada/portal/painel de cliente no site (medido no HTML)", "weight_hint": "high"},
            {"label": "Site institucional / landing sem função", "description": "Site apenas institucional ou landing page, sem funcionalidade (medido no HTML)", "weight_hint": "high"},
            {"label": "Sem menção a sistema/ERP", "description": "Site não menciona sistema/ERP/software de gestão próprio (medido no HTML)", "weight_hint": "medium"},
            {"label": "Processo manual / planilha", "description": "Indícios de operação por planilha, papel ou WhatsApp no segmento (inferência de segmento, não medido no site)", "weight_hint": "low"},
            {"label": "Crescimento sem sistema", "description": "Sinais de expansão (filial, novos serviços) sem indícios de automação (inferência de segmento)", "weight_hint": "low"},
            {"label": "Lead jovem em estruturação", "description": "Idade cadastral < 2 anos: empresa ainda montando processos, sistema entra junto com a operação", "weight_hint": "medium"},
            {"label": "Operação pequena bem avaliada", "description": "Boa reputação Google (>=4.0) com poucas avaliações (<=30) — operação enxuta, processo provavelmente manual", "weight_hint": "medium"},
            {"label": "CNAE compatível com sistema replicável", "description": "Setor de serviço/operação com processos replicáveis (saúde, educação, serviços especializados, logística, varejo) — público-alvo de ERP", "weight_hint": "medium"},
        ],
        "negative_signals": [
            {"label": "Painel / área do cliente presente", "description": "Área logada, painel ou portal ativo no site (já tem sistema — medido no HTML)", "weight_hint": "high"},
            {"label": "Menção a integrações/API", "description": "Site/empresa cita integrações, API ou sistemas próprios (medido no HTML)", "weight_hint": "high"},
            {"label": "Portal do aluno/cliente ativo", "description": "Portal de cliente/aluno ativo e funcional (medido no HTML)", "weight_hint": "medium"},
            {"label": "Microempresa / MEI", "description": "Porte cadastral indica microempresa/MEI sem operação que justifique sistema", "weight_hint": "high"},
            {"label": "Lead do setor de software / TI / SaaS", "description": "CNAE indica desenvolvimento de software, TI, SaaS, programação — concorrente ou já digital demais", "weight_hint": "high"},
            {"label": "Empresa antiga e estruturada", "description": "Idade cadastral > 10 anos com porte médio/grande — provavelmente já tem sistema legado; fito baixo para troca", "weight_hint": "medium"},
        ],
        "context_signals": [
            {"label": "Segmento", "description": "Educação, saúde, serviços, comércio — setores com processos operacionais que viram sistema"},
            {"label": "Região", "description": "Presença regional indica potencial de atendimento presencial"},
            {"label": "Porte", "description": "Porte cadastral (dados cadastrais) indica capacidade de compra de sistema"},
            {"label": "Idade da empresa", "description": "Idade cadastral: < 2 anos = estruturando (público-alvo); > 10 anos = provavelmente tem sistema"},
            {"label": "Capital social", "description": "Capital social baixo = pouco investimento em TI = boa probabilidade de venda"},
            {"label": "Reputação Google vs porte", "description": "Boa nota com poucas avaliações = operação pequena sem gestão estruturada"},
        ],
        "extra_instructions": (
            "Venda de aplicações web completas ou sistemas ERP. O fito vem PRINCIPALMENTE "
            "do cadastro (porte, idade, CNAE) e do SEGMENTO, NÃO da qualidade técnica "
            "do site. Para quem vende sistema, processo manual/planilha é o público-alvo. "
            "Diferencie claramente:\n"
            "- SaaS de delivery/pedidos (anota.ai, iFood, Rappi, Aimpire, Pedidosky): NÃO "
            "substituem ERP. O lead provavelmente AINDA tem processo manual interno. "
            "Use como gancho: 'vocês já usam X para pedidos — e para o resto?'.\n"
            "- Sistema de gestão PRÓPRIO (área logada + API no domínio próprio do lead): "
            "isso sim indica que o lead já tem automação — reduza o score.\n"
            "- Microempresa/MEI raramente justifica ERP sob medida: pondere baixo.\n"
            "- Lead do setor de software/TI/SaaS é POTENCIAL CONCORRENTE ou já é digital "
            "demais: pondere baixo.\n"
            "- Empresa com < 2 anos está estruturando processos: público-alvo FORTE.\n"
            "- Empresa com > 10 anos e porte médio/grande provavelmente já tem sistema "
            "legado: fito baixo para troca, pondere baixo.\n"
            "NUNCA desqualifique por 'site desatualizado' — para quem vende sistema, "
            "processo manual/planilha é o público-alvo. A presença de área logada/painel/"
            "portal no HTML indica que a empresa JÁ tem sistema (reduz o score); site só "
            "institucional sem função nem menção a sistema indica processo manual (aumenta "
            "o score). Sinais de 'crescimento sem sistema' e 'processo manual' são "
            "inferência de segmento — não podem ser usados como evidência técnica "
            "(pondere baixo)."
        ),
    },
    # ----- Industrial / Engenharia / Fabricação -----
    {
        "service_label": "Engenharia Mecânica & Desenhos Técnicos CAD",
        "requires_technical_report": False,
        "requires_business_data": True,
        # Site/SEO praticamente irrelevantes para indústria — reputação leve;
        # atividade/porte (CNPJ) é que qualifica, e isso só chega depois.
        # O pré-score NÃO tem dados para descartar aqui: o sinal decisivo da
        # vertical (CNAE/atividade industrial) é pós-gate, então o threshold
        # baixo só corta ausência total de presença verificável.
        "prescoring_config": {
            "profile": "industrial",
            "enabled": True,
            "threshold": 20,
        },
        # Fontes de informação: Receita Federal (porte/CNAE/idade) + reputação
        # Google. Auditoria de site não faz sentido para indústria — muitos
        # prospects nem têm site relevante.
        "enrichment_steps": ["cnpj_receita", "business_social"],
        # Ciclo de venda longo (3-6 meses): espaça as 4 mensagens ao longo de
        # 2 meses em vez de 2 semanas (default 0/3/7/14).
        "cadence_schedule": [0, 7, 30, 60],
        "playbook": {
            "hooks": [
                "Empresa necessita de detalhamento de projetos mecânicos 3D/CAD e desenhos técnicos para produção",
                "Operação fabril/usinagem que terceiriza ou necessita de capacidade extra de engenharia e modelagem",
                "Atualização de acervo técnico ou documentação de componentes para fabricação/manutenção",
            ],
            "subject_ideas": [
                "Modelagem 3D e desenhos técnicos CAD para a {empresa}",
                "Capacidade extra em engenharia mecânica para a {empresa}",
                "Detalhamento de projetos e peças para a {empresa}",
            ],
            "objections": [
                {"objection": "Já temos equipe de engenharia interna", "approach": "Oferecer suporte para picos de demanda ou detalhamento 2D/3D especializado"},
                {"objection": "Não terceirizamos projetos", "approach": "Propor teste em um componente/protótipo específico para homologação"},
            ],
        },
        "positive_signals": [
            {"label": "Operação de usinagem / caldeiraria / metalurgia", "description": "Termos de manufatura (torno, cnc, solda, usinagem) ou CNAE industrial detectados", "weight_hint": "high"},
            {"label": "Necessidade de projetos / detalhamento CAD", "description": "Menção a projetos mecânicos, componentes sob medida ou máquinas", "weight_hint": "high"},
            {"label": "Porte industrial médio/grande", "description": "Capacidade operacional e fito para desenvolvimento técnico", "weight_hint": "high"},
            {"label": "Sinais de expansão / novos equipamentos", "description": "Empresa adquirindo máquinas ou ampliando linha de produção", "weight_hint": "medium"},
        ],
        "negative_signals": [
            {"label": "Comércio varejista / serviço sem componente físico", "description": "Sem aderência para engenharia mecânica", "weight_hint": "high"},
            {"label": "Microempresa individual sem produção física", "description": "Sem escala ou demanda para projetos técnicos", "weight_hint": "medium"},
        ],
        "context_signals": [
            {"label": "Segmento industrial", "description": "Metalomecânica, plásticos, automotivo, alimento, bebida, energia"},
            {"label": "Região", "description": "Polo industrial regional indica alta densidade de demanda"},
        ],
        "extra_instructions": (
            "Análise voltada a projetos de Engenharia Mecânica, modelagem 3D, projetos CAD, "
            "detalhamento técnico de peças e automação. Use os termos de capacidade industrial "
            "(usinagem, CNC, solda, máquinas, caldeiraria) e o porte cadastral como evidência primária. "
            "Ignore SSL/SEO/performance do site — avalie pelo segmento, vocação fabril e palavras-chave de negócio."
        ),
    },
    {
        "service_label": "Corte Laser, MDF & Produtos Personalizados",
        "requires_technical_report": True,
        "requires_business_data": True,
        "playbook": {
            "hooks": [
                "Empresa demanda troféus, medalhas, chaveiros ou brindes corporativos sob medida para eventos e premiações",
                "Demanda por peças cortadas a laser em MDF, acrílico ou metal para comunicação visual ou produtos",
                "Necessidade de lote personalizado de brindes ou peças decorativas/promocionais",
            ],
            "subject_ideas": [
                "Troféus, chaveiros e peças personalizadas em MDF para a {empresa}",
                "Corte a laser e brindes sob medida para {empresa}",
                "Premiações e peças em MDF/Acrílico para a {empresa}",
            ],
            "objections": [
                {"objection": "Já temos fornecedor de brindes", "approach": "Oferecer amostra/protótipo sem custo ou orçamento comparativo para o próximo evento"},
                {"objection": "Compramos pronto no mercado", "approach": "Mostrar a valorização da marca com peças 100% personalizadas em MDF/Acrílico"},
            ],
        },
        "positive_signals": [
            {"label": "Organização de eventos / RH / marketing / esportes", "description": "Promove premiações, corridas, homenagens ou eventos corporativos", "weight_hint": "high"},
            {"label": "Palavras-chave de artesanato/comunicação visual/brindes", "description": "Menções a MDF, acrílico, troféus, chaveiros ou peças sob medida", "weight_hint": "high"},
            {"label": "Empresa comercial ou agência consumidora de brindes", "description": "Demanda recorrente de presentes corporativos ou sinalização", "weight_hint": "medium"},
        ],
        "negative_signals": [
            {"label": "Empresa sem eventos ou sem uso de marca física", "description": "Sem aderência para produtos personalizados em MDF/Acrílico", "weight_hint": "high"},
        ],
        "extra_instructions": (
            "Análise para venda de corte a laser, projetos em MDF, acrílico, troféus, chaveiros, "
            "placas e brindes corporativos. Avalie o fito se a empresa realiza eventos, premiações, "
            "ou consome material promocional/comunicação visual sob medida. Ignore métricas de SEO/SSL."
        ),
        "context_signals": [
            {"label": "Segmento", "description": "Eventos, educação, esportes, RH corporativo, agências, comércio"},
        ],
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
        "enrichment_steps": tmpl.get("enrichment_steps"),
        "cadence_schedule": tmpl.get("cadence_schedule"),
        "extra_instructions": tmpl.get("extra_instructions"),
        "playbook": tmpl.get("playbook", {}),
        "prescoring_config": tmpl.get("prescoring_config"),
        "is_active": True,
    }

    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        db.flush()
        logger.info("Atualizado template: %s", existing.service_label)
        cfg = tmpl.get("prescoring_config") or {}
        if isinstance(cfg, dict) and cfg.get("enabled"):
            logger.info("Gate de pré-scoring ATIVADO para template %s (perfil=%s, "
                        "threshold=%s, weights=%s)", existing.service_label,
                        cfg.get("profile"), cfg.get("threshold"), cfg.get("weights"))
        return existing

    obj = CampaignScoringTemplate(**fields)
    db.add(obj)
    db.flush()
    logger.info("Criado template: %s", obj.service_label)
    cfg = tmpl.get("prescoring_config") or {}
    if isinstance(cfg, dict) and cfg.get("enabled"):
        logger.info("Gate de pré-scoring ATIVADO para template %s (perfil=%s, "
                    "threshold=%s, weights=%s)", obj.service_label,
                    cfg.get("profile"), cfg.get("threshold"), cfg.get("weights"))
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
