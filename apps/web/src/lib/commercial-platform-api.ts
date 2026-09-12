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

export interface CommercialIntelligenceDashboard {
  attribution: {
    total_outcomes: number;
    attributed_outcomes: number;
    unattributed_outcomes: number;
    attribution_rate: number | null;
  };
  signal_effectiveness: Array<{
    signal: string;
    sample_size: number;
    reply_rate: number;
    meeting_rate: number;
    win_rate: number;
    revenue_per_signal: number;
  }>;
  provider_effectiveness: Array<{
    provider: string;
    requests: number;
    candidates: number;
    replies: number;
    meetings: number;
    wins: number;
    cost: number;
    revenue: number;
    roi: number | null;
  }>;
  precision: {
    reply_top_10: number | null;
    meeting_top_10: number | null;
    won_top_25: number | null;
    ranked_opportunities: number;
  };
  coverage: {
    known_companies: number;
    leads: number;
    icp_matches: number;
    contactable_people: number;
    prospected_leads: number;
    won_leads: number;
    penetration_rate: number | null;
    market_universe: number | null;
    market_universe_status: string;
  };
  niche_priors: Array<{
    offer_key: string;
    segment: string;
    sample_size: number;
    win_rate: number;
    revenue: number;
  }>;
}

export const commercialPlatformApi = {
  connections: () => request<{ items: CRMConnection[] }>('/api/crm/crm-sync/connections'),
  saveConnection: (body: {
    provider: CRMProvider;
    sync_mode: CRMSyncMode;
    token?: string;
    base_url?: string;
    enabled: boolean;
  }) => request<CRMConnection>('/api/crm/crm-sync/connections', {
    method: 'PUT',
    body: JSON.stringify(body),
  }),
  health: (connectionId: string) => request<{ provider: string; status: string; detail?: string }>(`/api/crm/crm-sync/connections/${connectionId}/health`, { method: 'POST' }),
  pull: (connectionId: string) => request<{ status: string; processed: number; succeeded: number; conflicts: number }>(`/api/crm/crm-sync/connections/${connectionId}/pull`, {
    method: 'POST',
    body: JSON.stringify({ idempotency_key: `ui-pull:${connectionId}:${Date.now()}` }),
  }),
  syncRuns: () => request<{ items: CRMSyncRun[] }>('/api/crm/crm-sync/runs'),
  intelligence: () => request<CommercialIntelligenceDashboard>('/api/crm/commercial-intelligence/dashboard'),
};
