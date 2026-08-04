# Re-exporta modelos dos workers (fonte única para o modelo de dados)
import sys
import os

# Adiciona workers src ao path para importar modelos
workers_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'workers', 'src')
sys.path.insert(0, workers_path)

from database.models import (
    Lead,
    Campaign,
    Enrichment,
    Message,
    FollowUp,
    MessageChannel,
    Job,
    User,
    Contact,
    CompanyRecord,
    Conversion,
    Organization,
    OrganizationMember,
    Invite,
    LeadActivity,
    LeadActivityAction,
    LeadStatus,
    CampaignStatus,
    JobStatus,
    JobType,
    AnalysisProfile,
    LeadPriority,
    ContactRole,
    OrganizationRole,
    SalesRole,
    CampaignScoringTemplate,
    OrganizationSecret,
    FollowUpStep,
    FollowUpStatus,
)
