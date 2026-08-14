export type LeadStatus = 
  | 'NOVO'
  | 'ANALISADO'
  | 'QUALIFICADO'
  | 'DESQUALIFICADO'
  | 'CONTATADO'
  | 'RESPONDIDO'
  | 'REUNIAO_MARCADA'
  | 'REUNIAO_FEITA'
  | 'PROPOSTA_ENVIADA'
  | 'PERDIDO';

export type CampaignStatus = 'ACTIVE' | 'PAUSED' | 'COMPLETED' | 'ARCHIVED';

export type LeadPriority = 'HOT' | 'WARM' | 'COLD';

export type SalesRole = 'CONSULTOR' | 'ANALYST' | 'MANAGER';

export type OrgRole = 'OWNER' | 'ADMIN' | 'MEMBER';

export interface ScoreFactor {
  label: string;
  impact: '+' | '-';
  weight: 'high' | 'medium' | 'low';
  rationale: string;
  evidence_ref?: string;
}

export interface EvidenceItem {
  type: string;
  severity: 'CRITICO' | 'ALTO' | 'MEDIO' | 'BAIXO' | 'INFO';
  title: string;
  description: string;
  source?: string;
}

export interface LeadActivityItem {
  id: string;
  action: string;
  user_id?: string;
  user_name?: string;
  status_from?: string;
  status_to?: string;
  detail?: string;
  created_at: string;
}

export interface ContactItem {
  id: string;
  name: string;
  role?: string;
  role_label?: string;
  email?: string;
  phone?: string;
  document_cpf?: string;
  confidence?: number;
  email_verified?: boolean;
  email_verified_at?: string;
  linkedin_url?: string;
  linkedin_confidence?: number;
  is_primary?: boolean;
  source?: string;
  raw_data?: unknown;
  created_at?: string;
}

// Consulta sugerida para achar o decisor no LinkedIn.
export interface LinkedinQuery {
  label: string;
  query: string;
}

// Medidor de cotas diárias por provedor/org.
export interface ProviderUsageItem {
  key_name: string;
  used: number;
  limit: number;
  remaining: number;
  pct: number;
}

// Funil interno de negociação (RD → Orçamento → RP).
export type NegotiationStage = 'RD' | 'ORCAMENTO' | 'RP';
export type ContractOutcome = 'APROVADO' | 'REPROVADO' | 'EM_ANALISE';

export interface Lead {
  id: string;
  place_id?: string;
  company_name: string;
  website?: string;
  phone?: string;
  email?: string;
  category?: string;
  city: string;
  state?: string;
  country: string;
  status: LeadStatus;
  qualification_score: number;
  qualification_reason?: string;
  primary_need?: string;
  segment_opportunity?: string;
  pitch_angle?: string;
  suggested_subject?: string;
  priority?: LeadPriority;
  priority_reasoning?: string;
  executive_summary?: string;
  score_factors?: ScoreFactor[];
  evidence?: EvidenceItem[];
  campaign_id?: string;
  assigned_to_id?: string;
  assigned_to_name?: string;
  assigned_at?: string;
  notes?: string;
  whatsapp?: string;
  next_action_at?: string;
  last_contacted_at?: string;
  negotiation_stage?: NegotiationStage | null;
  contract_outcome?: ContractOutcome | null;
  outcome_date?: string | null;
  post_sale_contacted_at?: string | null;
  post_sale_channel?: 'WHATSAPP' | 'EMAIL' | null;
  value?: number | null;
  expected_close_date?: string | null;
  lost_reason?: 'PRECO' | 'PRAZO' | 'NAO_RESPONDEU' | 'CONCORRENTE' | 'OUTRO' | null;
  activities?: LeadActivityItem[];
  contacts?: ContactItem[];
  created_at: string;
  updated_at: string;
}

export interface SlaAlertItem {
  id: string;
  company_name: string;
  city?: string;
  state?: string;
  status?: string | null;
  qualification_score: number;
  assigned_to_name?: string | null;
  alert_type: 'QUALIFICADO_NO_CONTACT' | 'RESPONDIDO_NO_NEXT_ACTION' | 'OPENED_NO_RESPONSE';
  alert_label: string;
  days_since: number;
  last_contacted_at?: string | null;
  next_action_at?: string | null;
  opened_at?: string | null;
}

export interface OrganizationMember {
  organization_id: string;
  user_id: string;
  name?: string;
  email?: string;
  role: OrgRole;
  sales_role: SalesRole;
  created_at?: string;
}

// Auditoria de membros e acessos (org_audit_log).
export type OrgAuditEvent =
  | 'ORG_CREATED'
  | 'ORG_RENAMED'
  | 'ORG_SETTINGS_UPDATED'
  | 'MEMBER_ROLE_CHANGED'
  | 'MEMBER_REMOVED'
  | 'MEMBER_LEFT'
  | 'OWNER_TRANSFERRED'
  | 'INVITE_CREATED'
  | 'INVITE_ACCEPTED'
  | 'INVITE_REVOKED'
  | 'SECRET_SET'
  | 'SECRET_DELETED'
  | 'SALES_TARGET_UPSERTED'
  | 'SALES_TARGET_DELETED';

export interface OrgAuditEntry {
  id: string;
  event: OrgAuditEvent;
  actor_id?: string | null;
  actor_name?: string | null;
  actor_email?: string | null;
  target_type?: string | null;
  target_id?: string | null;
  detail?: string | null;
  created_at: string;
}

export interface OrgMembership {
  organization: {
    id: string;
    name?: string;
    slug?: string;
    auto_send_email?: boolean;
    // Throttling & remetente dedicado.
    daily_email_limit?: number;
    send_window_start?: string;
    send_window_end?: string;
    sends_today?: number;
    email_from?: string;
    // SLA de leads parados (dias).
    sla_qualified_no_contact_days?: number;
    sla_responded_no_next_action_days?: number;
    sla_opened_no_response_days?: number;
  };
  membership: {
    role: OrgRole;
    sales_role: SalesRole;
    user_id: string;
  };
}

export interface FollowUpItem {
  id: string;
  step: 'OPENING' | 'FOLLOWUP_1' | 'FOLLOWUP_2' | 'CLOSING';
  label: string;
  channel: string | null;
  subject: string | null;
  content: string | null;
  scheduled_at: string | null;
  sent_at: string | null;
  status: 'PENDING' | 'SENT' | 'SKIPPED' | 'CANCELLED' | null;
  opened_at?: string | null;
  clicked_at?: string | null;
}

export interface LeadCadence {
  lead_id: string;
  opt_out: boolean;
  organization_auto_send: boolean;
  follow_ups: FollowUpItem[];
}

export interface OrganizationListItem {
  id: string;
  name: string;
  slug: string;
  role: OrgRole;
  sales_role: SalesRole;
  created_at?: string;
}

export interface Invite {
  id: string;
  email: string;
  role: OrgRole;
  sales_role: SalesRole;
  invited_by_id: string;
  invited_by_name?: string;
  created_at: string;
  expires_at: string;
  accepted_at?: string;
}

export interface Campaign {
  id: string;
  user_id: string;
  name: string;
  target_service?: string;
  target_segment?: string;
  target_city?: string;
  target_state?: string;
  target_country?: string;
  analysis_profile?: 'web_presence' | 'business_opportunity';
  places_query?: string;
  status: CampaignStatus;
  lead_count?: number;
  avg_score?: number;
  created_at: string;
  updated_at: string;
}

export interface Enrichment {
  id: string;
  lead_id: string;
  website_exists: boolean;
  ssl_ok: boolean;
  https_redirect_ok: boolean;
  responsive_design?: boolean;
  cms?: string;
  lighthouse_score?: number;
  seo_errors?: Record<string, unknown>;
  load_time_ms?: number;
  security_issues?: string[];
  raw_technical_data?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  lead_id: string;
  channel: 'EMAIL' | 'WHATSAPP' | 'LINKEDIN';
  content: string;
  ai_generated_draft?: string;
  sent_at?: string;
  responded_at?: string;
  is_response: boolean;
}

export interface DashboardMetrics {
  total_leads: number;
  qualified_leads: number;
  contacted_leads: number;
  meetings_scheduled: number;
  response_rate: number;
}

export type PipelineStage = 
  | 'CONTATADO'
  | 'RESPONDIDO'
  | 'REUNIAO_MARCADA'
  | 'REUNIAO_FEITA'
  | 'PROPOSTA_ENVIADA';

export interface ScoringResult {
  qualification_score: number;
  primary_need: string;
  qualification_reason: string;
  priority: LeadPriority;
  priority_reasoning: string;
  executive_summary: string;
  pitch_angle: string;
  suggested_subject: string;
  score_factors: ScoreFactor[];
  evidence: EvidenceItem[];
}

export interface OutreachMessages {
  subject: string;
  body_opening: string;
  followup_1: string;
  followup_2: string;
  closing: string;
  whatsapp_short: string;
  rationale: string;
}

export interface Issue {
  severity: 'CRITICO' | 'ALTO' | 'MEDIO' | 'BAIXO';
  title: string;
  description: string;
  recommendation: string;
}

export interface SiteAuditSection {
  title: string;
  status: 'ok' | 'warning' | 'info';
  detail: string;
  items?: string[];
}

export interface SiteAudit {
  available: boolean;
  overall_status?: string;
  summary: string;
  sections: SiteAuditSection[];
  errors?: string[];
  warnings?: string[];
}

export interface PitchOnePager {
  identity: {
    company_name: string;
    category?: string;
    city?: string;
    state?: string;
    website?: string;
    phone?: string;
    email?: string;
    cnpj?: string;
    razao_social?: string;
    nome_fantasia?: string;
    porte?: string;
    cnae_principal?: string;
    data_abertura?: string;
    idade_anos?: number;
    situacao_cadastral?: string;
    capital_social?: number;
  };
  campaign?: {
    name: string;
    target_service?: string;
    target_segment?: string;
  } | null;
  qualification: {
    score: number;
    priority?: string;
    priority_reasoning?: string;
    status?: string;
    primary_need?: string;
    qualification_reason?: string;
  };
  executive_summary?: string;
  pitch: {
    pitch_angle?: string;
    suggested_subject?: string;
  };
  score_factors: {
    positive: ScoreFactor[];
    negative: ScoreFactor[];
  };
  evidence: EvidenceItem[];
  primary_contact?: {
    name: string;
    role?: string;
    email?: string;
    phone?: string;
    linkedin_url?: string;
  } | null;
  site_audit?: SiteAudit | null;
}

export interface CsvImportErrorItem {
  line: number;
  reason: string;
}

export interface CsvImportResult {
  total_rows: number;
  imported_count: number;
  duplicate_count: number;
  error_count: number;
  errors: CsvImportErrorItem[];
}

export interface ForecastStageItem {
  stage: string;
  count: number;
  probability: number;
  total_value: number;
  weighted_value: number;
}

export interface LostReasonItem {
  reason: string;
  count: number;
}

export interface ForecastData {
  pipeline_value: number;
  forecast_weighted: number;
  realized_revenue: number;
  open_leads_count: number;
  pipeline_by_stage: ForecastStageItem[];
  lost_reasons_breakdown: LostReasonItem[];
}
