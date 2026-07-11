import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Enum, ForeignKey, ARRAY, Numeric, Boolean
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

class MessageChannel(enum.Enum):
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    LINKEDIN = "LINKEDIN"

# Modelos
class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(50), default="SALES")
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    campaigns = relationship("Campaign", back_populates="created_by_user")

    def __repr__(self):
        return f"<User(id='{self.id}', email='{self.email}')>"

class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    target_service = Column(String(255))
    target_segment = Column(String(100))
    target_city = Column(String(100))
    analysis_profile = Column(Enum(AnalysisProfile, name='analysis_profile', create_type=False, values_callable=lambda e: [m.value for m in e]), nullable=False, default=AnalysisProfile.WEB_PRESENCE)
    scoring_template_id = Column(UUID(as_uuid=True), ForeignKey("campaign_scoring_templates.id"), nullable=True)
    target_state = Column(String(2))
    target_country = Column(String(100))
    status = Column(Enum(CampaignStatus, name='campaign_status', create_type=True), default=CampaignStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    created_by_user = relationship("User", back_populates="campaigns")
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
    # Instruções extras, free-text, injetadas no prompt.
    extra_instructions = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    campaigns = relationship("Campaign", back_populates="scoring_template")

    def __repr__(self):
        return f"<CampaignScoringTemplate(id='{self.id}', service='{self.service_label}')>"

class Lead(Base):
    __tablename__ = "leads"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    place_id = Column(String(255), unique=True, nullable=True) 
    company_name = Column(String(255), nullable=False)
    website = Column(String(255))
    phone = Column(String(50))
    email = Column(String(255)) 
    category = Column(String(100)) 
    city = Column(String(100), nullable=False)
    state = Column(String(100))
    country = Column(String(100))
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
    enrichments = relationship("Enrichment", back_populates="lead")
    messages = relationship("Message", back_populates="lead")
    conversions = relationship("Conversion", back_populates="lead")
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
    
    lead = relationship("Lead", back_populates="messages")

    def __repr__(self):
        return f"<Message(id='{self.id}', lead_id='{self.lead_id}', channel='{self.channel.value}')>"

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

    lead = relationship("Lead", back_populates="conversions")

    def __repr__(self):
        return f"<Conversion(id='{self.id}', lead_id='{self.lead_id}', service='{self.service_sold}')>"

class Job(Base):
    __tablename__ = "jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True) 
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