export type LeadStatus = 
  | 'NOVO'
  | 'ANALISADO'
  | 'QUALIFICADO'
  | 'DESQUALIFICADO'
  | 'CONTATADO'
  | 'RESPONDIDO'
  | 'REUNIAO_MARCADA'
  | 'PERDIDO';

export type CampaignStatus = 'ACTIVE' | 'PAUSED' | 'COMPLETED' | 'ARCHIVED';

export type LeadPriority = 'HOT' | 'WARM' | 'COLD';

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
  created_at: string;
  updated_at: string;
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
