import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Enum, ForeignKey, ARRAY, Numeric, Boolean, Float, UniqueConstraint, Index, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func
import enum

class Base(DeclarativeBase):
    pass

class LeadStatus(enum.Enum):
    NOVO = "NOVO"
    ANALISADO = "ANALISADO"
    QUALIFICADO = "QUALIFICADO"
    DESQUALIFICADO = "DESQUALIFICADO"
    CONTATADO = "CONTATADO"
    RESPONDIDO = "RESPONDIDO"
    REUNIAO_MARCADA = "REUNIAO_MARCADA"
    REUNIAO_FEITA = "REUNIAO_FEITA"
    PROPOSTA_ENVIADA = "PROPOSTA_ENVIADA"
    PERDIDO = "PERDIDO"

class NegotiationStage(enum.Enum):
    """Funil interno de negociação.

    RD (reunião de demonstração) → ORÇAMENTO → RP (reunião de proposta).
    Etapas comerciais entre o lead responder e o fechamento.
    """
    RD = "RD"
    ORCAMENTO = "ORCAMENTO"
    RP = "RP"

class ContractOutcome(enum.Enum):
    """Resultado do contrato final (planilha: APROVADO/REPROVADO/EM_ANÁLISE)."""
    APROVADO = "APROVADO"
    REPROVADO = "REPROVADO"
    EM_ANALISE = "EM_ANALISE"

class PostSaleChannel(enum.Enum):
    """Canal do pós-venda (planilha Alphamec: WhatsApp/E-mail)."""
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"

class LostReason(enum.Enum):
    """Motivo de perda do lead."""
    PRECO = "PRECO"
    PRAZO = "PRAZO"
    NAO_RESPONDEU = "NAO_RESPONDEU"
    CONCORRENTE = "CONCORRENTE"
    OUTRO = "OUTRO"

class CampaignStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"

class AnalysisProfile(enum.Enum):
    WEB_PRESENCE = "web_presence"
    BUSINESS_OPPORTUNITY = "business_opportunity"

class LeadPriority(enum.Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"

class JobType(enum.Enum):
    LEAD_COLLECTION = "LEAD_COLLECTION"
    LEAD_ENRICHMENT = "LEAD_ENRICHMENT"
    LEAD_SCORING = "LEAD_SCORING"
    OUTREACH_EMAIL = "OUTREACH_EMAIL"

class JobStatus(enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class OrganizationRole(enum.Enum):
    """Papel do membro dentro de uma organização/workspace."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"

class SalesRole(enum.Enum):
    """Papel de venda dentro da organização — o que o membro enxerga/faz.

    - CONSULTOR: trabalha o próprio funil (vê/edita apenas os leads dele ou
      não atribuídos; pode se auto-atribuir).
    - ANALYST: lê tudo da org + BI + exporta PDF (não edita funil).
    - MANAGER: lê tudo + BI + exporta PDF + gerencia papéis.
    """
    CONSULTOR = "CONSULTOR"
    ANALYST = "ANALYST"
    MANAGER = "MANAGER"

class MessageChannel(enum.Enum):
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    LINKEDIN = "LINKEDIN"

class OnboardingStatus(enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DISMISSED = "DISMISSED"

class FollowUpStep(enum.Enum):
    """Etapas da cadência de follow-up — regras de business-rules.

    Sequência padrão: abertura → follow-up 1 → follow-up 2 → encerramento.
    O `day_offset` é o calendário default (0/3/7/14); templates de vertical
    podem sobrescrever os dias (`cadence_schedule`) ao agendar.
    """
    OPENING = "OPENING"
    FOLLOWUP_1 = "FOLLOWUP_1"
    FOLLOWUP_2 = "FOLLOWUP_2"
    CLOSING = "CLOSING"
    # Pós-venda: acompanhamento pós-cliente usando o mesmo
    # motor da cadência (scheduler `run_due` + `send_step`).
    POST_SALE = "POST_SALE"

    @property
    def day_offset(self) -> int:
        return {FollowUpStep.OPENING: 0, FollowUpStep.FOLLOWUP_1: 3,
                FollowUpStep.FOLLOWUP_2: 7, FollowUpStep.CLOSING: 14,
                FollowUpStep.POST_SALE: 14}[self]

    @property
    def label(self) -> str:
        # Sem "dia N" fixo — a data de cada etapa é agendada conforme o
        # template/vertical e exibida na UI (dia corrido do calendário).
        return {FollowUpStep.OPENING: "Primeira mensagem",
                FollowUpStep.FOLLOWUP_1: "Segunda mensagem",
                FollowUpStep.FOLLOWUP_2: "Terceira mensagem",
                FollowUpStep.CLOSING: "Encerramento",
                FollowUpStep.POST_SALE: "Pós-venda"}[self]

class FollowUpStatus(enum.Enum):
    PENDING = "PENDING"       # agendado, aguardando envio (humano ou automático)
    SENT = "SENT"             # enviado
    SKIPPED = "SKIPPED"       # pulado (ex.: opt-out do lead ou lead respondeu)
    CANCELLED = "CANCELLED"   # cancelado (ciclo encerrado cedo)

# Modelos
class Organization(Base):
    """Workspace que agrupa usuários e isola seus dados.

    Cada usuário nasce com uma organização pessoal (criada no registro).
    Membros (OrganizationMember) compartilham campanhas e leads; o papel
    define o que podem gerenciar (owner/admin/member).
    """
    __tablename__ = "organizations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(120), unique=True, nullable=False)
    # Envio automático de follow-ups (opt-in). Default: humano-no-loop.
    # Só com esta flag o scheduler envia e-mails quando a cadência vence.
    auto_send_email = Column(Boolean, default=False, nullable=False, server_default="false")
    # Remetente próprio da org (ex.: vendas@empresa.com.br). Se vazio,
    # usa o remetente global do settings (SMTP_FROM_EMAIL).
    email_from = Column(String(255))
    # Throttling de envio automático: teto diário de e-mails da org
    # (warmup/warm). O scheduler `run_due` nunca ultrapassa este limite no dia.
    daily_email_limit = Column(Integer, default=40, nullable=False, server_default="40")
    # Janela de espalhamento dos envios automáticos (HH:MM, ex. "09:00"
    # e "17:00"). Fora da janela, o scheduler posterga as etapas (fica PENDING).
    send_window_start = Column(String(5), default="09:00", nullable=False, server_default="09:00")
    send_window_end = Column(String(5), default="17:00", nullable=False, server_default="17:00")
    # SLA e lembretes para leads parados (dias). Regras configuráveis
    # por org que alimentam o painel "Ações de hoje" e os alertas do kanban.
    sla_qualified_no_contact_days = Column(Integer, default=5, nullable=False, server_default="5")
    sla_responded_no_next_action_days = Column(Integer, default=2, nullable=False, server_default="2")
    sla_opened_no_response_days = Column(Integer, default=2, nullable=False, server_default="2")
    # Limiar QUALIFICADO/DESQUALIFICADO aplicado em `_persist_scoring`.
    # Calibrável por org via `PATCH /api/orgs/{id}` (sugestão via analytics).
    qualification_threshold = Column(Integer, default=60, nullable=False, server_default="60")
    # URL pública que recebe eventos de lead (POST JSON). Vazio = sem webhook.
    webhook_url = Column(String(255))
    # Segredo compartilhado enviado em X-Webhook-Secret — consumidor valida.
    webhook_secret = Column(String(64))
    # Link de agendamento (Cal.com/Calendly). Injetado no outreach como CTA.
    scheduling_url = Column(String(255))
    # Teto diário de uso por provedor (BYOK vs pool). Sobrescreve o
    # default do settings (`PROVIDER_DAILY_QUOTA`). Ex.: {"GROQ_API_KEY": 500}.
    api_quota = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="organization")
    invites = relationship("Invite", back_populates="organization", cascade="all, delete-orphan")
    secrets = relationship("OrganizationSecret", back_populates="organization", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Organization(id='{self.id}', name='{self.name}')>"


class OrganizationMember(Base):
    """Vínculo de um usuário a uma organização com papel (owner/admin/member)."""
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_members_org_user"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(Enum(OrganizationRole, name='organization_role', create_type=False, values_callable=lambda e: [m.value for m in e]), default=OrganizationRole.MEMBER)
    # Papel de venda por organização: CONSULTOR/ANALYST/MANAGER.
    sales_role = Column(Enum(SalesRole, name='sales_role', create_type=True, values_callable=lambda e: [m.value for m in e]), default=SalesRole.CONSULTOR)
    # Remetente dedicado por consultor (ex.: rapha@alphamec.com.br).
    # Preserva a reputação individual de cada vendedor no envio automático.
    # Se vazio, usa `organizations.email_from`; se este for vazio, o global.
    email_from = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="memberships")

    def __repr__(self):
        return f"<OrganizationMember(org='{self.organization_id}', user='{self.user_id}', role='{self.role.value}')>"


class Invite(Base):
    """Convite pendente para uma organização (owner/admin convida por e-mail)."""
    __tablename__ = "invites"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(Enum(OrganizationRole, name='organization_role', create_type=False, values_callable=lambda e: [m.value for m in e]), default=OrganizationRole.MEMBER)
    sales_role = Column(Enum(SalesRole, name='sales_role', create_type=False, values_callable=lambda e: [m.value for m in e]), default=SalesRole.CONSULTOR)
    token = Column(String(64), unique=True, nullable=False)
    invited_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="invites")
    invited_by = relationship("User", foreign_keys=[invited_by_id])

    def __repr__(self):
        return f"<Invite(org='{self.organization_id}', email='{self.email}', accepted={self.accepted_at is not None})>"


class SalesTarget(Base):
    """Meta de vendas mensal por consultor.

    Define quanto cada consultor deve produzir no mês (`month` "YYYY-MM"):
    meta de reuniões e meta de receita. O BI (`/analytics/consultants`) cruza
    o realizado com estas metas para mostrar atingimento (%).
    """
    __tablename__ = "sales_targets"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", "month", name="uq_sales_targets_org_user_month"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    month = Column(String(7), nullable=False, index=True)
    meetings_target = Column(Integer, default=0, nullable=False)
    revenue_target = Column(Numeric(12, 2), default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    user = relationship("User")

    def __repr__(self):
        return f"<SalesTarget(org='{self.organization_id}', user='{self.user_id}', month='{self.month}')>"


class ConsultantPlaybook(Base):
    """Mensagem que funcionou, anotada pelo próprio consultor.

    Cada registro guarda um subject + body que o autor considera útil
    reutilizar naquela vertical. Outros consultores da org podem ler
    (ver e copiar), mas só o autor ou admin edita/remove. É diferente
    do `CampaignScoringTemplate` (que define como pontuar) e dos
    `playbook` embutidos no template (que alimentam a LLM).
    """
    __tablename__ = "consultant_playbooks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    vertical = Column(String(120))
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    tags = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    author = relationship("User")

    def __repr__(self):
        return f"<ConsultantPlaybook(id='{self.id}', author='{self.author_id}', vertical='{self.vertical}')>"


class OrganizationSecret(Base):
    """Chaves de API próprias da organização (BYOK).

    Quando preenchidas, os workers usam a chave da org em vez do pool global
    (settings), evitando consumir a quota compartilhada. O valor é criptografado
    em repouso (Fernet) usando a `SECRETS_ENCRYPTION_KEY` do settings.

    `key_name` identifica o provedor: `GOOGLE_API_KEY` ou `GROQ_API_KEY`.
    """
    __tablename__ = "organization_secrets"
    __table_args__ = (
        UniqueConstraint("organization_id", "key_name", name="uq_org_secrets_org_key"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    key_name = Column(String(60), nullable=False)
    # Valor criptografado (Fernet token). Nunca a chave em texto puro.
    encrypted_value = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")

    def __repr__(self):
        return f"<OrganizationSecret(org='{self.organization_id}', key='{self.key_name}')>"


class ProviderUsage(Base):
    """Medidor diário de uso de provedores externos por org/key.

    Contabiliza chamadas (Google Places e Groq) por organização e por dia,
    contra um limite configurável (`organizations.api_quota` ou o default do
    settings `PROVIDER_DAILY_QUOTA`). Alimenta o painel de cotas da org e trava
    chamadas excedentes (fail-closed: `remaining <= 0` → o provider não chama).
    """
    __tablename__ = "provider_usage"
    __table_args__ = (
        UniqueConstraint("organization_id", "key_name", "usage_date",
                         name="uq_provider_usage_org_key_date"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    key_name = Column(String(60), nullable=False)
    usage_date = Column(Date, nullable=False)
    count = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")

    def __repr__(self):
        return f"<ProviderUsage(org='{self.organization_id}', key='{self.key_name}', date={self.usage_date}, count={self.count})>"


class OrgAuditEvent(enum.Enum):
    """Eventos administrativos da organização registrados no audit log."""
    ORG_CREATED = "ORG_CREATED"
    ORG_RENAMED = "ORG_RENAMED"
    ORG_SETTINGS_UPDATED = "ORG_SETTINGS_UPDATED"
    MEMBER_ROLE_CHANGED = "MEMBER_ROLE_CHANGED"
    MEMBER_REMOVED = "MEMBER_REMOVED"
    MEMBER_LEFT = "MEMBER_LEFT"
    OWNER_TRANSFERRED = "OWNER_TRANSFERRED"
    INVITE_CREATED = "INVITE_CREATED"
    INVITE_ACCEPTED = "INVITE_ACCEPTED"
    INVITE_REVOKED = "INVITE_REVOKED"
    SECRET_SET = "SECRET_SET"
    SECRET_DELETED = "SECRET_DELETED"
    SALES_TARGET_UPSERTED = "SALES_TARGET_UPSERTED"
    SALES_TARGET_DELETED = "SALES_TARGET_DELETED"


class OrgAuditLog(Base):
    """Trilha de eventos administrativos da organização.

    Dá rastreabilidade à diretoria (quem convidou, mudou papel, removeu
    membro, alterou chave/metas). `actor_name`/`actor_email` são gravados
    junto porque o membro pode ser removido depois.
    """
    __tablename__ = "org_audit_log"
    __table_args__ = (
        Index("ix_org_audit_log_org_created", "organization_id", "created_at"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    actor_name = Column(String(255))
    actor_email = Column(String(255))
    event = Column(Enum(OrgAuditEvent, name='org_audit_event', create_type=True), nullable=False)
    target_type = Column(String(60))
    target_id = Column(String(60))
    detail = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization")
    actor = relationship("User")

    def __repr__(self):
        return f"<OrgAuditLog(org='{self.organization_id}', event='{self.event.value}', at={self.created_at})>"


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(50), default="SALES")
    onboarding_status = Column(Enum(OnboardingStatus, name='onboarding_status', create_type=True), nullable=False, default=OnboardingStatus.NOT_STARTED, server_default="NOT_STARTED")
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    campaigns = relationship("Campaign", back_populates="created_by_user")
    memberships = relationship("OrganizationMember", back_populates="user")

    def __repr__(self):
        return f"<User(id='{self.id}', email='{self.email}')>"

class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    target_service = Column(String(255))
    target_segment = Column(String(100))
    target_city = Column(String(100))
    analysis_profile = Column(Enum(AnalysisProfile, name='analysis_profile', create_type=False, values_callable=lambda e: [m.value for m in e]), nullable=False, default=AnalysisProfile.WEB_PRESENCE)
    scoring_template_id = Column(UUID(as_uuid=True), ForeignKey("campaign_scoring_templates.id"), nullable=True)
    target_state = Column(String(2))
    target_country = Column(String(100))
    # Query otimizada para o Google Places.
    # Quando presente, o pipeline usa esta query em vez de montar uma
    # automaticamente a partir de target_segment/city/state.
    places_query = Column(String(255))
    status = Column(Enum(CampaignStatus, name='campaign_status', create_type=True), default=CampaignStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    created_by_user = relationship("User", back_populates="campaigns")
    organization = relationship("Organization", back_populates="campaigns")
    leads = relationship("Lead", back_populates="campaign")
    jobs = relationship("Job", back_populates="campaign")
    scoring_template = relationship("CampaignScoringTemplate", back_populates="campaigns")

    def __repr__(self):
        return f"<Campaign(id='{self.id}', name='{self.name}')>"

class CampaignScoringTemplate(Base):
    """Template de critérios de scoring contextual por tipo de serviço.

    Permite que a análise da IA seja guiada por critérios relevantes ao serviço
    vendido (ex: 'Desenvolvimento de Sites' valoriza SEO/HTTPS/performance;
    'Engenharia Mecânica' valoriza porte/fábrica/expansão). Editável sem mudar
    código — adiciona-se um novo row para cada nova categoria de serviço.
    """
    __tablename__ = "campaign_scoring_templates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_label = Column(String(255), nullable=False)
    # Critérios positivos: sinais que aumentam o score quando presentes.
    positive_signals = Column(JSONB, nullable=False, default=list)
    # Critérios negativos: sinais que reduzem o score quando presentes.
    negative_signals = Column(JSONB, nullable=False, default=list)
    # Sinais contextuais adicionais (segmento, região etc.) — opcional.
    context_signals = Column(JSONB, default=list)
    # Indica se a análise técnica do site é relevante para este serviço.
    requires_technical_report = Column(Boolean, default=True)
    # Indica se dados cadastrais (categoria/porte/segmento) são relevantes.
    requires_business_data = Column(Boolean, default=True)
    # Fontes de informação da empresa que este serviço usa para avaliar um
    # lead. Valores: "technical_site" (auditoria do site), "cnpj_receita"
    # (porte/CNAE/idade via Receita Federal) e "business_social" (reputação
    # Google). Vazia -> derivada dos flags binários acima (compat retroativa).
    enrichment_steps = Column(JSONB)
    # Dias (a partir do envio) das 4 mensagens de acompanhamento:
    # [1ª mensagem, 2ª mensagem, 3ª mensagem, encerramento].
    # Ex.: [0, 7, 30, 60] para ciclos longos (Engenharia Mecânica/indústria).
    # Vazia -> [0, 3, 7, 14] (default histórico).
    cadence_schedule = Column(JSONB)
    # Instruções extras, free-text, injetadas no prompt.
    extra_instructions = Column(Text)
    # Playbook de outreach por vertical: hooks de abordagem,
    # ideias de assunto e objeções do decisor — injetados no OutreachService
    # para mensagens variarem por serviço/segmento.
    playbook = Column(JSONB, default=dict)
    is_active = Column(Boolean, default=True)
    # Template gerado por IA sob demanda — distingue de seeds manuais.
    is_generated = Column(Boolean, default=False, server_default="false")
    # Org dona do template (NULL = global/seed); templates gerados são por org.
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    campaigns = relationship("Campaign", back_populates="scoring_template")
    organization = relationship("Organization")

    def __repr__(self):
        return f"<CampaignScoringTemplate(id='{self.id}', service='{self.service_label}')>"

class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("organization_id", "place_id", name="uq_leads_org_place_id"),
        UniqueConstraint("organization_id", "cnpj", name="uq_leads_org_cnpj"),
        UniqueConstraint("organization_id", "normalized_domain", name="uq_leads_org_normalized_domain"),
        # Índices compostos que cobrem os filtros mais usados —
        # org + status (+ score) e org + status + data.
        Index("ix_leads_org_status_score", "organization_id", "status", "qualification_score"),
        Index("ix_leads_org_status_created", "organization_id", "status", "created_at"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    place_id = Column(String(255), unique=False, nullable=True)
    # `name` é o nome fantasia/estabelecimento (fonte CSV/CNAE); `company_name`
    # é a razão social/denominação (fonte Places). CSV/CNAE preenchem ambos.
    name = Column(String(255))
    company_name = Column(String(255), nullable=False)
    cnpj = Column(String(14))
    address = Column(String(500))
    website = Column(String(255))
    normalized_domain = Column(String(255))
    phone = Column(String(50))
    whatsapp = Column(String(50))
    email = Column(String(255)) 
    category = Column(String(100)) 
    city = Column(String(100), nullable=False)
    state = Column(String(100))
    country = Column(String(100))
    # Reputação no Google — sinal de oportunidade para
    # serviços: nota baixa + nº de avaliações expõem a dor mais óbvia de um lead.
    google_rating = Column(Float)
    google_rating_count = Column(Integer)
    google_maps_uri = Column(String(255))
    # Página da empresa no LinkedIn (linkedin.com/company/<slug>), localizada
    # por busca passiva durante o enriquecimento.
    company_linkedin_url = Column(String(255))
    # Perfil do Instagram do negócio (canonicalizado via domain_utils).
    # Sinal de presença/atividade digital — exibido no pitch e considerado
    # pelo scoring (item 4.26).
    instagram_url = Column(String(255))
    # Timestamps por fonte do enriquecimento (JSONB {"linkedin", "site",
    # "reviews"} em ISO) — alimenta o TTL e a indicação de dados antigos.
    enrichment_timestamps = Column(JSONB)
    # Campos de trabalho do consultor.
    notes = Column(Text)
    next_action_at = Column(DateTime(timezone=True))
    last_contacted_at = Column(DateTime(timezone=True))
    # Funil interno de negociação:
    # `negotiation_stage` (RD/ORÇAMENTO/RP) + `contract_outcome`
    # (APROVADO/REPROVADO/EM_ANÁLISE) + `outcome_date` (quando foi marcado).
    negotiation_stage = Column(Enum(NegotiationStage, name='negotiation_stage', create_type=True), nullable=True)
    contract_outcome = Column(Enum(ContractOutcome, name='contract_outcome', create_type=True), nullable=True)
    outcome_date = Column(DateTime(timezone=True), nullable=True)
    # Pós-venda: data do 1º contato pós-cliente e canal
    # (planilha Alphamec: "DATA CONTATO PÓS-VENDA" + "PÓS VENDA POR").
    post_sale_contacted_at = Column(DateTime(timezone=True), nullable=True)
    post_sale_channel = Column(Enum(PostSaleChannel, name='post_sale_channel', create_type=True), nullable=True)
    # Forecast e oportunidade: ticket estimado, data de fechamento e motivo de perda
    value = Column(Numeric(12, 2), nullable=True)
    expected_close_date = Column(DateTime(timezone=True), nullable=True)
    lost_reason = Column(Enum(LostReason, name='lost_reason', create_type=True), nullable=True)
    status = Column(Enum(LeadStatus, name='lead_status', create_type=True), default=LeadStatus.NOVO)

    qualification_score = Column(Integer, default=0) 
    qualification_reason = Column(Text) 
    primary_need = Column(String(255)) 
    pitch_angle = Column(Text)
    suggested_subject = Column(String(255))
    segment_opportunity = Column(String(100)) 

    # Problema 2 — Explicabilidade
    score_factors = Column(JSONB)           # [{label, impact: +/−, weight, evidence_ref}]
    evidence = Column(JSONB)               # [{type, severity, title, description, source}]
    priority = Column(Enum(LeadPriority, name='lead_priority', create_type=True), nullable=True)
    priority_reasoning = Column(Text)
    executive_summary = Column(Text)

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
    campaign = relationship("Campaign", back_populates="leads")

    # Modelo de 3 entidades (Company / Person / Lead-Oportunidade)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    primary_person_id = Column(UUID(as_uuid=True), ForeignKey("persons.id"), nullable=True)
    company = relationship("Company", back_populates="leads")
    primary_person = relationship("Person", foreign_keys=[primary_person_id])

    # Atribuição a consultor de vendas (desempenho por consultor).
    assigned_to_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])

    # Opt-out: lead pediu para não receber mais mensagens.
    # Cadências pendentes são canceladas/puladas e nenhum envio automático ocorre.
    opt_out = Column(Boolean, default=False, nullable=False, server_default="false")

    enrichments = relationship("Enrichment", back_populates="lead")
    messages = relationship("Message", back_populates="lead")
    follow_ups = relationship("FollowUp", back_populates="lead", cascade="all, delete-orphan")
    conversions = relationship("Conversion", back_populates="lead")
    activities = relationship("LeadActivity", back_populates="lead", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="lead", cascade="all, delete-orphan")
    company_record = relationship("CompanyRecord", back_populates="lead", uselist=False, cascade="all, delete-orphan")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Lead(id='{self.id}', company_name='{self.company_name}', status='{self.status.value}')>"

class Enrichment(Base):
    __tablename__ = "enrichments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    
    website_exists = Column(Boolean, default=False)
    ssl_ok = Column(Boolean, default=False)
    https_redirect_ok = Column(Boolean, default=False) 
    responsive_design = Column(Boolean, default=False)
    cms = Column(String(100)) 
    lighthouse_score = Column(Integer) 
    seo_errors = Column(JSONB) 
    load_time_ms = Column(Integer) 
    security_issues = Column(ARRAY(String)) 
    raw_technical_data = Column(JSONB)
    # DTO do enriquecimento cadastral (Receita Federal via CNPJ): porte, CNAE,
    # idade da empresa, capital social e sócios. Usado no scoring e no pitch.
    raw_business_data = Column(JSONB)

    lead = relationship("Lead", back_populates="enrichments")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Enrichment(id='{self.id}', lead_id='{self.lead_id}', ssl_ok={self.ssl_ok})>"

class Message(Base):
    __tablename__ = "messages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    channel = Column(Enum(MessageChannel, name='message_channel', create_type=True), nullable=False)
    content = Column(Text, nullable=False) 
    ai_generated_draft = Column(Text) 
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    responded_at = Column(DateTime(timezone=True))
    is_response = Column(Boolean, default=False) 
    # Tracking de abertura/clique — pixel + redirect.
    tracking_token = Column(String(64), unique=True, nullable=True)
    opened_at = Column(DateTime(timezone=True))
    clicked_at = Column(DateTime(timezone=True))
    # Rótulo da variante A/B (espelha `follow_ups.variant` no envio). Quando o
    # lead responde, o inbound cria uma `Message` espelho (`is_response=True`)
    # com o variant da última mensagem enviada antes da resposta.
    variant = Column(String(32))

    lead = relationship("Lead", back_populates="messages")

    def __repr__(self):
        return f"<Message(id='{self.id}', lead_id='{self.lead_id}', channel='{self.channel.value}')>"

class FollowUp(Base):
    """Etapa da cadência de follow-up de um lead.

    Sequência dia 0/3/7/14 (`FollowUpStep`): abertura + 2 follow-ups +
    encerramento, conforme `docs/business-rules.md`. O conteúdo é a mensagem
    gerada pelo `OutreachService` (ou editada pelo humano) pronta para envio.

    - `scheduled_at` = momento em que a etapa deve ser enviada.
    - Se a org optou por **envio automático** (`Organization.auto_send_email`),
      o scheduler envia quando `scheduled_at` vence. Senão (humano-no-loop
      default), o consultor envia manualmente pela UI.
    - Leads com `opt_out` têm etapas pendentes marcadas como `SKIPPED`.
    """
    __tablename__ = "follow_ups"
    __table_args__ = (
        Index("ix_follow_ups_lead_id", "lead_id"),
        Index("ix_follow_ups_scheduled_at", "scheduled_at"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    step = Column(Enum(FollowUpStep, name='follow_up_step', create_type=True), nullable=False)
    channel = Column(Enum(MessageChannel, name='message_channel', create_type=False), default=MessageChannel.EMAIL)
    subject = Column(String(255))
    content = Column(Text)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True))
    status = Column(Enum(FollowUpStatus, name='follow_up_status', create_type=True), default=FollowUpStatus.PENDING)
    # Contagem de tentativas (transitórias) e Message-ID do último
    # envio (para threading dos follow-ups seguintes).
    attempts = Column(Integer, default=0, nullable=False, server_default="0")
    message_id = Column(String(255))
    # Token de tracking: mesma chave usada em `messages.tracking_token` para
    # expor abertura/clique no painel de cadência.
    tracking_token = Column(String(64))
    # Rótulo da variante A/B escolhida para esta etapa (ex.: "A"/"B"). Permite
    # medir resposta por variante via `GET /api/analytics/message-variants`.
    variant = Column(String(32))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lead = relationship("Lead", back_populates="follow_ups")

    def __repr__(self):
        return f"<FollowUp(lead='{self.lead_id}', step='{self.step.value}', status='{self.status.value}')>"


class FollowUpVersion(Base):
    """Snapshot de uma versão de mensagem antes de edição.

    Cada vez que o consultor edita o conteúdo/assunto de uma etapa da
    cadência (via PATCH /cadence/step/{step}), o sistema salva o estado
    anterior como versão. Permite comparar, reverter e auditar mudanças
    no copywriting — essencial para tuning de mensagens IA.
    """
    __tablename__ = "follow_up_versions"
    __table_args__ = (
        Index("ix_follow_up_versions_follow_up_id", "follow_up_id"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    follow_up_id = Column(UUID(as_uuid=True), ForeignKey("follow_ups.id"), nullable=False)
    version_number = Column(Integer, nullable=False, default=1)
    subject = Column(String(255))
    content = Column(Text)
    variant = Column(String(32))
    edited_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    edit_reason = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    follow_up = relationship("FollowUp")

    def __repr__(self):
        return f"<FollowUpVersion(follow_up='{self.follow_up_id}', v{self.version_number})>"


class EmailSuppression(Base):
    """Endereços de e-mail com bounce permanente (5xx).

    Um endereço que queimou uma vez não é re-tentado em nenhuma cadência até
    ser removido manualmente — protege a reputação do domínio remetente.
    A organização é anotada para que os alertas de entregabilidade sejam
    calculados por workspace, sem misturar bounces de organizações diferentes.
    """
    __tablename__ = "email_suppressions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    email = Column(String(255), nullable=False, unique=True)
    reason = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<EmailSuppression(email='{self.email}')>"

class ContactRole(enum.Enum):
    """Papel do decisor na empresa. Derivado da Receita Federal (sócios
    aparecem como SOCIO) ou inferido a partir do cargo (CEO/DIRETOR)."""
    SOCIO = "SOCIO"
    ADMINISTRADOR = "ADMINISTRADOR"
    CEO = "CEO"
    DIRETOR = "DIRETOR"
    OUTRO = "OUTRO"


class Contact(Base):
    """Decisor relevante de um lead. Um lead pode ter múltiplos contatos
    (p/ex.: dois sócios), mas o sistema destaca um `is_primary=True`.

    Hoje populada via CNPJ (sócios/administradores listados na Receita).
    Futuro: Hunter.io refina/valida email por cargo.
    """
    __tablename__ = "contacts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(Enum(ContactRole, name='contact_role', create_type=True), nullable=True)
    role_label = Column(String(100))
    email = Column(String(255))
    phone = Column(String(50))
    document_cpf = Column(String(20))
    confidence = Column(Integer, default=0)
    # Verificação passiva de entregabilidade do e-mail (MX + blocklist).
    # `email_verified=True` só após MX presente; e-mail heurístico/descartável
    # ou sem MX fica False e nunca cruza o gate de envio automático.
    email_verified = Column(Boolean, nullable=False, server_default="false", default=False)
    email_verified_at = Column(DateTime(timezone=True))
    # Canal LinkedIn do decisor (busca passiva + validação HEAD).
    linkedin_url = Column(String(255))
    linkedin_confidence = Column(Integer, default=0)
    is_primary = Column(Boolean, default=False)
    source = Column(String(60), default="cnpj_receita")
    raw_data = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    lead = relationship("Lead", back_populates="contacts")

    def __repr__(self):
        return f"<Contact(id='{self.id}', name='{self.name}', role='{self.role}')>"


class CompanyRecord(Base):
    """Snapshot cadastral de um lead — razão social, CNAE, porte, sócios.
    Fonte: Receita Federal (BrasilAPI / CNPJá). Independente de `Lead` para
    permitir re-análise sem re-bater a API."""
    __tablename__ = "company_records"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, unique=True)
    cnpj = Column(String(20))
    razao_social = Column(String(255))
    nome_fantasia = Column(String(255))
    porte = Column(String(50))
    porte_label = Column(String(100))
    natureza_juridica = Column(String(255))
    capital_social = Column(Numeric(14, 2))
    situacao_cadastral = Column(String(50))
    data_abertura = Column(String(20))
    idade_anos = Column(Integer)
    cnae_principal = Column(String(20))
    cnae_principal_label = Column(String(255))
    cnae_secundarios = Column(JSONB)
    endereco = Column(JSONB)
    municipios_ativos = Column(JSONB)
    raw_data = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    lead = relationship("Lead", back_populates="company_record")

    def __repr__(self):
        return f"<CompanyRecord(lead_id='{self.lead_id}', cnpj='{self.cnpj}')>"


class Company(Base):
    """Entidade independente de Empresa para o modelo de 3 Entidades (Company, Person, Lead/Oportunidade).
    
    Permite consolidar informações de uma mesma empresa entre diferentes campanhas
    e oportunidades na mesma organização.
    """
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("organization_id", "cnpj", name="uq_companies_org_cnpj"),
        UniqueConstraint("organization_id", "normalized_domain", name="uq_companies_org_domain"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    company_name = Column(String(255), nullable=False)
    name = Column(String(255))
    cnpj = Column(String(20))
    website = Column(String(255))
    normalized_domain = Column(String(255))
    phone = Column(String(50))
    address = Column(String(500))
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100))
    category = Column(String(100))
    google_rating = Column(Float)
    google_rating_count = Column(Integer)
    google_maps_uri = Column(String(255))
    company_linkedin_url = Column(String(255))
    instagram_url = Column(String(255))
    raw_data = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    leads = relationship("Lead", back_populates="company")
    persons = relationship("Person", back_populates="company")

    def __repr__(self):
        return f"<Company(id='{self.id}', name='{self.company_name}')>"


class Person(Base):
    """Entidade de Pessoa/Decisor para o modelo de 3 Entidades.
    
    Persiste contatos/decisores de forma independente, associados a uma Empresa.
    """
    __tablename__ = "persons"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    name = Column(String(255), nullable=False)
    role = Column(Enum(ContactRole, name='contact_role', create_type=False, values_callable=lambda e: [m.value for m in e]), nullable=True)
    role_label = Column(String(100))
    email = Column(String(255))
    phone = Column(String(50))
    document_cpf = Column(String(20))
    confidence = Column(Integer, default=0)
    email_verified = Column(Boolean, nullable=False, server_default="false", default=False)
    email_verified_at = Column(DateTime(timezone=True))
    linkedin_url = Column(String(255))
    linkedin_confidence = Column(Integer, default=0)
    source = Column(String(60), default="cnpj_receita")
    raw_data = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    company = relationship("Company", back_populates="persons")

    def __repr__(self):
        return f"<Person(id='{self.id}', name='{self.name}')>"


class WebhookLog(Base):
    """Histórico de disparos de webhooks de saída por organização."""
    __tablename__ = "webhook_logs"
    __table_args__ = (
        Index("ix_webhook_logs_org_created", "organization_id", "created_at"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    target_url = Column(String(500), nullable=False)
    status_code = Column(Integer)
    success = Column(Boolean, default=False, nullable=False)
    payload = Column(JSONB)
    response_body = Column(Text)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization")

    def __repr__(self):
        return f"<WebhookLog(id='{self.id}', event='{self.event_type}', success={self.success})>"


class Conversion(Base):
    __tablename__ = "conversions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    converted_at = Column(DateTime(timezone=True), server_default=func.now())
    service_sold = Column(String(255))
    contract_value = Column(Numeric(10, 2))
    outreach_message_used = Column(Text)
    time_to_close_days = Column(Integer)
    notes = Column(Text)
    # Quem vendeu/fechou e quem trabalhava o lead no momento.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    assigned_to_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    lead = relationship("Lead", back_populates="conversions")

    def __repr__(self):
        return f"<Conversion(id='{self.id}', lead_id='{self.lead_id}', service='{self.service_sold}')>"


class LeadActivityAction(enum.Enum):
    """Ações registradas na trilha do lead.

    Além da `STATUS_CHANGED` genérica, o endpoint de status grava uma action
    semântica quando o destino tem significado comercial:
    `CONTACTED`, `RESPONDED`, `MEETING_SCHEDULED`, `PROPOSAL_SENT`, `LOST`.
    Conversão fecha o ciclo com `CONVERTED`.
    """
    CREATED = "CREATED"
    ASSIGNED = "ASSIGNED"
    UNASSIGNED = "UNASSIGNED"
    STATUS_CHANGED = "STATUS_CHANGED"
    MESSAGE_GENERATED = "MESSAGE_GENERATED"
    CONTACTED = "CONTACTED"
    RESPONDED = "RESPONDED"
    MEETING_SCHEDULED = "MEETING_SCHEDULED"
    PROPOSAL_SENT = "PROPOSAL_SENT"
    LOST = "LOST"
    CONVERTED = "CONVERTED"
    CONTACT_ENRICHED = "CONTACT_ENRICHED"
    NEGOTIATION_UPDATED = "NEGOTIATION_UPDATED"
    POST_SALE = "POST_SALE"
    WHATSAPP_SENT = "WHATSAPP_SENT"
    LINKEDIN_ASSOCIATED = "LINKEDIN_ASSOCIATED"


class LeadActivity(Base):
    """Trilha de atividades do lead — quem fez o quê e quando.

    Base das métricas por consultor (BI) e da auditoria. Registrada a cada
    mudança relevante: atribuição, status, mensagem, contato, reunião,
    conversão.
    """
    __tablename__ = "lead_activities"
    __table_args__ = (
        Index("ix_lead_activities_lead_id", "lead_id"),
        Index("ix_lead_activities_user_id", "user_id"),
        Index("ix_lead_activities_created_at", "created_at"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(Enum(LeadActivityAction, name='lead_activity_action', create_type=True), nullable=False)
    status_from = Column(Enum(LeadStatus, name='lead_status', create_type=False), nullable=True)
    status_to = Column(Enum(LeadStatus, name='lead_status', create_type=False), nullable=True)
    detail = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lead = relationship("Lead", back_populates="activities")
    user = relationship("User")

    def __repr__(self):
        return f"<LeadActivity(lead='{self.lead_id}', action='{self.action.value}', at={self.created_at})>"

class Job(Base):
    __tablename__ = "jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    job_type = Column(Enum(JobType, name='job_type', create_type=True), nullable=False)
    status = Column(Enum(JobStatus, name='job_status', create_type=True), default=JobStatus.PENDING)
    payload = Column(JSONB) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    error_message = Column(Text) 

    campaign = relationship("Campaign", back_populates="jobs")

    def __repr__(self):
        return f"<Job(id='{self.id}', type='{self.job_type.value}', status='{self.status.value}')>"


class NotificationType(enum.Enum):
    """Tipos de notificação in-app."""
    LEAD_RESPONDED = "LEAD_RESPONDED"
    LEAD_ASSIGNED = "LEAD_ASSIGNED"
    SLA_ALERT = "SLA_ALERT"
    CADENCE_DUE = "CADENCE_DUE"


class Notification(Base):
    """Notificações in-app do consultor.

    Criadas em background quando eventos relevantes acontecem
    (lead responde, lead atribuído, alerta SLA, cadência pendente).
    O frontend consulta via polling (useNotifications) e exibe badge.
    """
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id_read", "user_id", "is_read"),
        Index("ix_notifications_created_at", "created_at"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    notification_type = Column(Enum(NotificationType, name='notification_type', create_type=True), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    organization = relationship("Organization")
    lead = relationship("Lead")

    def __repr__(self):
        return f"<Notification(id='{self.id}', type='{self.notification_type.value}', user='{self.user_id}', read={self.is_read})>"