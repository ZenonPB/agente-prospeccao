import { request } from '@/lib/api';

export type FreshnessState = 'fresh' | 'stale' | 'unknown';

export interface FreshnessCheck {
  key: string;
  state: FreshnessState;
  observed_at: string | null;
  expires_at: string | null;
  age_days: number | null;
  ttl_days: number;
  priority: number;
}

export interface DataHealthItem {
  lead_id: string;
  company_name: string;
  company_id?: string | null;
  person_id?: string | null;
  freshness: FreshnessCheck[];
  stale_keys: string[];
  unknown_keys: string[];
  phone_verification: { state: string; normalized?: string | null; confidence: number; reason: string };
  email_invalid: boolean;
  missing_email: boolean;
  missing_phone: boolean;
  missing_decision_maker: boolean;
  identity_risk: boolean;
  opportunity_count: number;
  refresh_priority: number;
}

export interface ProviderHealth {
  provider: string;
  statuses: Record<string, number>;
  total: number;
  failures: number;
  failure_rate: number;
  health: 'healthy' | 'degraded' | 'disabled' | 'quota_exceeded';
  last_seen_at?: string | null;
}

export interface DataHealthOverview {
  total: number;
  healthy: number;
  health_rate: number;
  issues: Record<string, number>;
  provider_health: ProviderHealth[];
  items: DataHealthItem[];
  generated_at: string;
}

export interface RefreshPlanResponse {
  candidates: DataHealthItem[];
  jobs: Array<{ job_id: string; campaign_id: string; status: string }>;
}

export const dataIntelligenceApi = {
  health: (limit = 100) => request<DataHealthOverview>(`/api/data-intelligence/health?limit=${limit}`),
  refreshPlan: (limit = 25, enqueue = false) =>
    request<RefreshPlanResponse>('/api/data-intelligence/refresh-plan', {
      method: 'POST',
      body: JSON.stringify({ limit, enqueue }),
    }),
};
