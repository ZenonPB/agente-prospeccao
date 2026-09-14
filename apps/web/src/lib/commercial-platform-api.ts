import { request } from '@/lib/api';

export type CRMProvider = 'pipedrive' | 'hubspot' | 'salesforce';
export type CRMSyncMode = 'manual' | 'realtime' | 'scheduled';

export interface CRMConnection {
  id: string;
  provider: CRMProvider;
  sync_mode: CRMSyncMode;
  enabled: boolean;
  base_url?: string | null;
  has_secret_reference: boolean;
  last_health_status?: string | null;
  last_health_at?: string | null;
  last_sync_at?: string | null;
}

export interface CRMSyncRun {
  id: string;
  connection_id: string;
  direction: string;
  status: string;
  processed: number;
  succeeded: number;
  failed: number;
  conflicts: number;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface CRMCertificationRun {
  id: string;
  connection_id: string;
  provider: CRMProvider;
  status: 'PASSED' | 'FAILED' | string;
  checks: Array<{ name: string; status: string; sample_count?: number; note?: string; error?: string }>;
  adapter_version: string;
  tested_by_id?: string | null;
  created_at?: string | null;
}

export interface CommercialIntelligenceDashboard {
  attribution: { total_outcomes: number; attributed_outcomes: number; unattributed_outcomes: number; attribution_rate: number | null };
  signal_effectiveness: Array<{ signal: string; sample_size: number; reply_rate: number; meeting_rate: number; win_rate: number; revenue_per_signal: number }>;
  provider_effectiveness: Array<{ provider: string; requests: number; candidates: number; replies: number; meetings: number; wins: number; cost: number; revenue: number; roi: number | null }>;
  precision: { reply_top_10: number | null; meeting_top_10: number | null; won_top_25: number | null; ranked_opportunities: number };
  coverage: { known_companies: number; leads: number; icp_matches: number; contactable_people: number; prospected_leads: number; won_leads: number; penetration_rate: number | null; market_universe: number | null; market_universe_status: string };
  niche_priors: Array<{ offer_key: string; segment: string; sample_size: number; win_rate: number; revenue: number }>;
}

export interface CalibrationSignalAssociation {
  signal: string;
  sample_size: number;
  reply_rate: number | null;
  meeting_rate: number | null;
  win_rate: number | null;
  enough_sample: boolean;
  interpretation: string;
}

export interface CalibrationReport {
  offer_key: string;
  active_version: string;
  opportunities_total: number;
  outcomes_total: number;
  attributed_outcomes: number;
  sample_quality: {
    observed_opportunities: number;
    required_observed_opportunities: number;
    wins: number;
    required_wins: number;
    attribution_rate: number | null;
    required_attribution_rate: number;
    enough_sample: boolean;
    enough_wins: boolean;
    enough_attribution: boolean;
    eligible_for_proposal: boolean;
  };
  associations: CalibrationSignalAssociation[];
  human_feedback: {
    usefulness_total: number;
    useful: number;
    not_useful: number;
    useful_rate: number | null;
    score_feedback_total: number;
    mean_score_delta: number | null;
    note: string;
  };
}

export interface CalibrationComparison {
  id: string;
  offer_key: string;
  version_a: string;
  version_b: string;
  result: {
    verdict: 'v1' | 'v2' | 'inconclusive';
    recommendation: string;
    delta: Record<string, number | null>;
    v1: Record<string, number | null>;
    v2: Record<string, number | null>;
    sample_quality: CalibrationReport['sample_quality'];
    candidate_profile_snapshot?: Record<string, unknown>;
  };
  approved_version?: string | null;
  learning_proposal?: LearningProposal;
}

export interface LearningProposal {
  id: string;
  source_comparison_id: string;
  offer_key: string;
  proposal_version: number;
  approved_version: string;
  status: string;
  evidence_snapshot: Record<string, unknown>;
  requires_manual_publication: boolean;
  created_at?: string | null;
}

export interface OfferProfileVersion {
  id: string;
  offer_key: string;
  version: string;
  profile_snapshot: Record<string, unknown>;
  is_active: boolean;
  source_proposal_id?: string | null;
  activated_at?: string | null;
  created_at?: string | null;
}

export interface CoachingRecommendation {
  kind: string;
  title: string;
  recommendation: string;
  evidence: Record<string, number | string | null>;
  association_not_causation: boolean;
}

export interface CoachingDashboard {
  team: { consultants: number; assigned_leads: number; contacted: number; replies: number; meetings: number; proposals: number; wins: number; overdue_followups: number; reply_rate: number | null; meeting_rate: number | null; win_rate: number | null };
  consultants: Array<{
    user_id: string;
    name: string;
    assigned_leads: number;
    contacted: number;
    replies: number;
    meetings: number;
    proposals: number;
    wins: number;
    overdue_followups: number;
    reply_rate: number | null;
    meeting_rate: number | null;
    proposal_rate: number | null;
    win_rate: number | null;
    first_contact_under_24h_rate: number | null;
    timing_evidence: Record<string, number | null>;
    recommendations: CoachingRecommendation[];
  }>;
  methodology: Record<string, string>;
}

export const commercialPlatformApi = {
  connections: () => request<{ items: CRMConnection[] }>('/api/crm/crm-sync/connections'),
  saveConnection: (body: { provider: CRMProvider; sync_mode: CRMSyncMode; token?: string; base_url?: string; enabled: boolean }) => request<CRMConnection>('/api/crm/crm-sync/connections', { method: 'PUT', body: JSON.stringify(body) }),
  health: (connectionId: string) => request<{ provider: string; status: string; detail?: string }>(`/api/crm/crm-sync/connections/${connectionId}/health`, { method: 'POST' }),
  certify: (connectionId: string) => request<CRMCertificationRun>(`/api/crm/crm-sync/connections/${connectionId}/certify`, { method: 'POST' }),
  certifications: () => request<{ items: CRMCertificationRun[] }>('/api/crm/crm-sync/certifications'),
  pull: (connectionId: string) => request<{ status: string; processed: number; succeeded: number; conflicts: number }>(`/api/crm/crm-sync/connections/${connectionId}/pull`, { method: 'POST', body: JSON.stringify({ idempotency_key: `ui-pull:${connectionId}:${Date.now()}` }) }),
  syncRuns: () => request<{ items: CRMSyncRun[] }>('/api/crm/crm-sync/runs'),
  intelligence: () => request<CommercialIntelligenceDashboard>('/api/crm/commercial-intelligence/dashboard'),

  calibrationOverview: (minSamples = 20) => request<{ items: CalibrationReport[]; min_samples: number }>(`/api/intelligence/calibration/overview?min_samples=${minSamples}`),
  coaching: () => request<CoachingDashboard>('/api/intelligence/coaching'),
  createCalibrationComparison: (body: { offer_key: string; min_samples?: number; top_k?: number; candidate_profile_snapshot?: Record<string, unknown> }) => request<CalibrationComparison>('/api/intelligence/calibration/comparisons', { method: 'POST', body: JSON.stringify(body) }),
  approveComparison: (comparisonId: string, body: { approved_version: string; evidence: string }) => request<CalibrationComparison>(`/api/intelligence/comparisons/${comparisonId}/approval`, { method: 'POST', body: JSON.stringify(body) }),
  learningProposals: () => request<{ proposals: LearningProposal[] }>('/api/intelligence/learning-proposals'),
  publishLearningProposal: (proposalId: string) => request<OfferProfileVersion>(`/api/intelligence/learning-proposals/${proposalId}/publish`, { method: 'POST', body: JSON.stringify({}) }),
  offerProfileVersions: () => request<{ items: OfferProfileVersion[] }>('/api/intelligence/offer-profile-versions'),
  rollbackOfferProfile: (offerKey: string, targetVersion: string) => request<OfferProfileVersion>(`/api/intelligence/offer-profile-versions/${encodeURIComponent(offerKey)}/rollback`, { method: 'POST', body: JSON.stringify({ target_version: targetVersion }) }),
};
