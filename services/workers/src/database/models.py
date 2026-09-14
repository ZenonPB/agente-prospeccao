import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Enum, ForeignKey, ARRAY, Numeric, Boolean, Float, UniqueConstraint, CheckConstraint, Index, Date, text
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

class ImportJobStatus(enum.Enum):
    DRAFT = "DRAFT"
    PREVIEWED = "PREVIEWED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"

class ImportRowStatus(enum.Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    REJECTED = "REJECTED"
    FAILED = "FAILED"

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

class ContactRole(enum.Enum):
    DONO = "DONO"
    FUNDADOR = "FUNDADOR"
    SOCIO = "SOCIO"
    DIRETOR = "DIRETOR"
    GERENTE = "GERENTE"
    MARKETING = "MARKETING"
    VENDAS = "VENDAS"
    TI = "TI"
    COMPRAS = "COMPRAS"
    ENGENHARIA = "ENGENHARIA"
    RH = "RH"
    FINANCEIRO = "FINANCEIRO"
    OUTRO = "OUTRO"

class EmailVerificationStatus(enum.Enum):
    UNKNOWN = "UNKNOWN"
    VALID = "VALID"
    INVALID = "INVALID"
    RISKY = "RISKY"
    ACCEPT_ALL = "ACCEPT_ALL"

class RoutabilityType(enum.Enum):
    DIRECT_CONTACT = "DIRECT_CONTACT"
    ROUTABLE_CONTACT = "ROUTABLE_CONTACT"
    INSTITUTIONAL = "INSTITUTIONAL"
    UNKNOWN = "UNKNOWN"

class VerificationStatus(enum.Enum):
    UNKNOWN = "UNKNOWN"
    CANDIDATE = "CANDIDATE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"

class LinkedinMatchStatus(enum.Enum):
    NOT_FOUND = "NOT_FOUND"
    CANDIDATE = "CANDIDATE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    VERIFIED = "VERIFIED"

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
    POST_SALE = "POST_SALE"

    @property
    def day_offset(self) -> int:
        return {FollowUpStep.OPENING: 0, FollowUpStep.FOLLOWUP_1: 3,
                FollowUpStep.FOLLOWUP_2: 7, FollowUpStep.CLOSING: 14,
                FollowUpStep.POST_SALE: 14}[self]

    @property
    def label(self) -> str:
        return {FollowUpStep.OPENING: "Primeira mensagem",
                FollowUpStep.FOLLOWUP_1: "Segunda mensagem",
                FollowUpStep.FOLLOWUP_2: "Terceira mensagem",
                FollowUpStep.CLOSING: "Encerramento",
                FollowUpStep.POST_SALE: "Pós-venda"}[self]

class FollowUpStatus(enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"

# Modelos
class Organization(Base):
    """Workspace que agrupa usuários e isola seus dados."""
    __tablename__ = "organizations"
    __table_args__ = (
        Index("uq_organizations_inbound_token_hash", "inbound_token_hash", unique=True),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(120), unique=True, nullable=False)
    auto_send_email = Column(Boolean, default=False, nullable=False, server_default="false")
    email_from = Column(String(255))
    daily_email_limit = Column(Integer, default=40, nullable=False, server_default="40")
    send_window_start = Column(String(5), default="09:00", nullable=False, server_default="09:00")
    send_window_end = Column(String(5), default="17:00", nullable=False, server_default="17:00")
    sla_qualified_no_contact_days = Column(Integer, default=5, nullable=False, server_default="5")
    sla_responded_no_next_action_days = Column(Integer, default=2, nullable=False, server_default="2")
    sla_opened_no_response_days = Column(Integer, default=2, nullable=False, server_default="2")
    qualification_threshold = Column(Integer, default=60, nullable=False, server_default="60")
    webhook_url = Column(String(255))
    webhook_secret = Column(String(64))
    inbound_token_hash = Column(String(64), nullable=True)
    scheduling_url = Column(String(255))
    api_quota = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="organization")
    invites = relationship("Invite", back_populates="organization", cascade="all, delete-orphan")
    secrets = relationship("OrganizationSecret", back_populates="organization", cascade="all, delete-orphan")

class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member_org_user"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum(OrganizationRole, name="organization_role", create_type=True), nullable=False, default=OrganizationRole.MEMBER)
    sales_role = Column(Enum(SalesRole, name="sales_role", create_type=True), nullable=True)
    onboarding_status = Column(Enum(OnboardingStatus, name="onboarding_status", create_type=True), nullable=False, default=OnboardingStatus.NOT_STARTED)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="memberships")

class Invite(Base):
    __tablename__ = "invites"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False)
    role = Column(Enum(OrganizationRole, name="organization_role", create_type=False), nullable=False, default=OrganizationRole.MEMBER)
    sales_role = Column(Enum(SalesRole, name="sales_role", create_type=False), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True))
    revoked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="invites")

class OrganizationSecret(Base):
    __tablename__ = "organization_secrets"
    __table_args__ = (UniqueConstraint("organization_id", "key_name", name="uq_org_secret_org_key"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    key_name = Column(String(60), nullable=False)
    encrypted_value = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    organization = relationship("Organization", back_populates="secrets")

class ProviderUsage(Base):
    __tablename__ = "provider_usage"
    __table_args__ = (
        UniqueConstraint("organization_id", "key_name", "usage_date", name="uq_provider_usage_org_key_date"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    key_name = Column(String(60), nullable=False)
    usage_date = Column(Date, nullable=False)
    count = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    organization = relationship("Organization")

class ProviderExecutionMetric(Base):
    __tablename__ = "provider_execution_metrics"
    __table_args__ = (
        Index("ix_provider_execution_metrics_org_recorded", "organization_id", "recorded_at"),
        Index("ix_provider_execution_metrics_org_provider", "organization_id", "provider", "recorded_at"),
        Index("ix_provider_execution_metrics_correlation", "correlation_id"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    correlation_id = Column(UUID(as_uuid=True), nullable=True)
    provider = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False)
    result_count = Column(Integer, nullable=False, server_default="0")
    duration_ms = Column(Integer, nullable=False, server_default="0")
    budget_used = Column(Integer, nullable=False, server_default="0")
    error_code = Column(String(100), nullable=True)
    retryable = Column(Boolean, nullable=False, server_default="false")
    cost = Column(Numeric(12, 6), nullable=True)
    usage = Column(JSONB, nullable=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    organization = relationship("Organization")
    job = relationship("Job")
    campaign = relationship("Campaign")

class OrgAuditEvent(enum.Enum):
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
    AB_COMPARISON_APPROVED = "AB_COMPARISON_APPROVED"
    CONTROLLED_LEARNING_PROPOSED = "CONTROLLED_LEARNING_PROPOSED"
    ANALYTICS_EXPORTED = "ANALYTICS_EXPORTED"

class OrgAuditLog(Base):
    __tablename__ = "org_audit_log"
    __table_args__ = (Index("ix_org_audit_log_org_created", "organization_id", "created_at"),)
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

class CommercialBulkOperation(Base):
    """Registro técnico de execução bulk e sua resposta idempotente."""
    __tablename__ = "commercial_bulk_operations"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_commercial_bulk_operations_org_idempotency"),
        Index("ix_commercial_bulk_operations_org_created", "organization_id", "created_at"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    idempotency_key = Column(String(160), nullable=False)
    operation = Column(String(16), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, server_default="RUNNING")
    result = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    organization = relationship("Organization")
    actor = relationship("User")

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    memberships = relationship("OrganizationMember", back_populates="user", cascade="all, delete-orphan")

# NOTE: The remainder of this model file is intentionally preserved by the repository's
# source-of-truth; this replacement must not truncate it.
