import { request } from '@/lib/api';

export interface SavedSearchFilters {
  q?: string;
  city?: string;
  state?: string;
  min_score?: number;
  has_email?: boolean;
  has_phone?: boolean;
  has_website?: boolean;
  status?: string;
  offer_key?: string;
}

export interface SavedProspectingSearch {
  id: string;
  name: string;
  offer_key?: string | null;
  filters: SavedSearchFilters;
  schedule: string;
  notification_policy: Record<string, unknown>;
  enabled: boolean;
  last_run_at?: string | null;
  next_run_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SavedSearchMatch {
  lead_id: string;
  company_name: string;
  city?: string | null;
  state?: string | null;
  status: string;
  score: number;
  offer_key?: string | null;
  email?: string | null;
  phone?: string | null;
}

export interface ProspectingAlert {
  id: string;
  saved_search_id?: string | null;
  lead_id?: string | null;
  event_id?: string | null;
  kind: 'saved_search_match' | 'event_rebuy' | string;
  title: string;
  reason?: string | null;
  score?: number | null;
  evidence?: Record<string, unknown> | null;
  status: 'new' | 'read' | 'dismissed' | 'actioned';
  created_at?: string | null;
}

export interface EventSeriesItem {
  id: string;
  series_key: string;
  name: string;
  family?: string | null;
  recurrence_confidence: number;
  expected_next_window?: {
    start?: string;
    end?: string;
    interval_days?: number;
    computed_at?: string;
  } | null;
  latest_event_id?: string | null;
  metadata?: Record<string, unknown> | null;
}

export type AgentState =
  | 'DISCOVERED'
  | 'NEEDS_ENRICHMENT'
  | 'READY_TO_SCORE'
  | 'READY_FOR_CONTACT'
  | 'AWAITING_ACTION'
  | 'IN_SEQUENCE'
  | 'WAITING'
  | 'REENGAGE'
  | 'CLOSED';

export interface AgentStateItem {
  id: string;
  lead_id: string;
  state: AgentState;
  reason?: string | null;
  evidence?: Record<string, unknown> | null;
  changed_at?: string | null;
}

export interface CaseStudyItem {
  id: string;
  offer_key: string;
  title: string;
  segments: string[];
  problem: string;
  solution: string;
  proof?: string | null;
  assets?: Record<string, unknown> | null;
  scope: 'workspace' | 'global';
}

export const prospectingAutomationApi = {
  savedSearches: () =>
    request<{ items: SavedProspectingSearch[] }>('/api/data-intelligence/saved-searches'),

  createSavedSearch: (body: {
    name: string;
    offer_key?: string | null;
    filters: SavedSearchFilters;
    schedule?: string;
    notification_policy?: Record<string, unknown>;
  }) =>
    request<SavedProspectingSearch>('/api/data-intelligence/saved-searches', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  patchSavedSearch: (id: string, body: Partial<Omit<SavedProspectingSearch, 'id'>>) =>
    request<SavedProspectingSearch>(`/api/data-intelligence/saved-searches/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteSavedSearch: (id: string) =>
    request<void>(`/api/data-intelligence/saved-searches/${id}`, { method: 'DELETE' }),

  runSavedSearch: (id: string, limit = 100) =>
    request<{ matches: SavedSearchMatch[]; created_alerts: number; ran_at: string }>(
      `/api/data-intelligence/saved-searches/${id}/run`,
      { method: 'POST', params: { limit } },
    ),

  alerts: (status?: ProspectingAlert['status']) =>
    request<{ items: ProspectingAlert[] }>('/api/data-intelligence/alerts', {
      params: status ? { status } : undefined,
    }),

  patchAlert: (id: string, status: ProspectingAlert['status']) =>
    request<ProspectingAlert>(`/api/data-intelligence/alerts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  eventSeries: () =>
    request<{ items: EventSeriesItem[] }>('/api/data-intelligence/event-series'),

  refreshEventSeries: () =>
    request<{ series: number; rebuy_alerts_created: number }>('/api/data-intelligence/event-series/refresh', {
      method: 'POST',
    }),

  agentStates: (state?: AgentState) =>
    request<{ items: AgentStateItem[] }>('/api/data-intelligence/agent-states', {
      params: state ? { state } : undefined,
    }),

  refreshAgentStates: () =>
    request<{ states: Record<string, number> }>('/api/data-intelligence/agent-states/refresh', {
      method: 'POST',
    }),

  runWatch: () =>
    request<{ organization_id: string; status: string; processed: number; changed: number }>(
      '/api/data-intelligence/watch/run-once',
      { method: 'POST' },
    ),

  caseStudies: (offerKey?: string) =>
    request<{ items: CaseStudyItem[] }>('/api/data-intelligence/case-studies', {
      params: offerKey ? { offer_key: offerKey } : undefined,
    }),
};
