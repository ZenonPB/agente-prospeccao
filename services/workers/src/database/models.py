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
    PERDIDO = "PERDIDO"

class CampaignStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"

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
    target_state = Column(String(2))
    target_country = Column(String(100))
    status = Column(Enum(CampaignStatus, name='campaign_status', create_type=True), default=CampaignStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    created_by_user = relationship("User", back_populates="campaigns")
    leads = relationship("Lead", back_populates="campaign")
    jobs = relationship("Job", back_populates="campaign")

    def __repr__(self):
        return f"<Campaign(id='{self.id}', name='{self.name}')>"

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
    primary_need = Column(String(50)) 
    segment_opportunity = Column(String(100)) 

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
    campaign = relationship("Campaign", back_populates="leads")
    enrichments = relationship("Enrichment", back_populates="lead")
    messages = relationship("Message", back_populates="lead")
    conversions = relationship("Conversion", back_populates="lead")

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