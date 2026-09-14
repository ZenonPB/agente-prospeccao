import { request } from '@/lib/api';
import type { CommercialFilterSnapshot } from '@/lib/api';

export type OperatingQueueItem = {
  lead_id: string;
  company_name: string;
  status: string;
  priority: number;
  qualification_score?: number | null;
  offer_key?: string | null;
  opportunity_score?: number | null;
  reasons: string[];
  recommended_action?: string | null;
  recommended_why?: string | null;
  due_at?: string | null;
  owner_user_id?: string | null;
};

export type OperatingSearchItem = { id: string; title: string; subtitle?: string | null; href: string };
export type OperatingSearchResponse = {
  query: string;
  groups: {
    companies: OperatingSearchItem[];
    persons: OperatingSearchItem[];
    leads: OperatingSearchItem[];
    opportunities: OperatingSearchItem[];
    campaigns: OperatingSearchItem[];
  };
};

export type CrmOperatingFilters = {
  search?: string;
  status?: string;
  priority?: string;
  campaign_id?: string;
  assigned?: string;
  min_score?: string | number;
  archived?: 'active' | 'archived' | 'all';
  tag?: string;
};

export type SavedCommercialView = {
  id: string;
  name: string;
  view_kind: 'crm' | 'analytics';
  filters: CommercialFilterSnapshot & CrmOperatingFilters;
  shared: boolean;
  owner_user_id: string;
  editable: boolean;
  created_at: string;
  updated_at?: string | null;
};

export type OperatingLead = {
  id: string;
  company_name: string;
  city?: string | null;
  state?: string | null;
  status?: string | null;
  priority?: string | null;
  negotiation_stage?: string | null;
  qualification_score?: number | null;
  value?: number | null;
  campaign_id?: string | null;
  assigned_to_id?: string | null;
  next_action_at?: string | null;
  updated_at: string;
  tags: string[];
  archived_at?: string | null;
};

export type OperatingBulkPayload = {
  operation: 'negotiation_stage' | 'campaign' | 'add_tag' | 'remove_tag' | 'archive' | 'unarchive' | 'start_sequence';
  lead_ids: string[];
  expected_updated_at: Record<string, string>;
  negotiation_stage?: string | null;
  campaign_id?: string;
  tag?: string;
  sequence_id?: string;
};

export type OperatingBulkResult = {
  operation: string;
  items: Array<{ id: string; status: 'accepted' | 'duplicate' | 'rejected' | 'failed'; reason?: string | null }>;
  summary: { accepted: number; duplicate: number; rejected: number; failed: number };
  replayed: boolean;
};

export const salesOperatingApi = {
  queue: (limit = 20) => request<{ items: OperatingQueueItem[]; total: number; as_of: string }>('/api/crm/operating/queue', { params: { limit } }),
  search: (q: string, limit = 8) => request<OperatingSearchResponse>('/api/crm/operating/search', { params: { q, limit } }),
  leads: (params: CrmOperatingFilters & { limit?: number; offset?: number }) => request<{ items: OperatingLead[]; total: number; limit: number; offset: number }>(
    '/api/crm/operating/leads', { params: params as Record<string, string | number | boolean | undefined> },
  ),
  savedViews: (viewKind?: 'crm' | 'analytics') => request<{ items: SavedCommercialView[] }>('/api/crm/operating/saved-views', { params: { view_kind: viewKind } }),
  createSavedView: (body: { name: string; view_kind: 'crm' | 'analytics'; filters: CommercialFilterSnapshot | CrmOperatingFilters; shared?: boolean }) => request<SavedCommercialView>('/api/crm/operating/saved-views', { method: 'POST', body: JSON.stringify(body) }),
  deleteSavedView: (id: string) => request<void>(`/api/crm/operating/saved-views/${id}`, { method: 'DELETE' }),
  previewBulk: (body: OperatingBulkPayload) => request<{ operation: string; total_selected: number; accepted_ids: string[]; rejected: Array<{ id: string; reason: string }>; max_items: number }>('/api/crm/operating/bulk/preview', { method: 'POST', body: JSON.stringify(body) }),
  executeBulk: (body: OperatingBulkPayload & { idempotency_key: string }) => request<OperatingBulkResult>('/api/crm/operating/bulk/execute', { method: 'POST', body: JSON.stringify(body) }),
  createBulkTask: (body: { lead_ids: string[]; expected_updated_at: Record<string, string>; title: string; description?: string; due_at?: string | null; task_type?: string; idempotency_key: string }) => request<OperatingBulkResult>('/api/crm/operating/bulk-task/execute', { method: 'POST', body: JSON.stringify(body) }),
  exportSelection: (leadIds: string[]) => request<Blob>('/api/crm/operating/export', { method: 'POST', body: JSON.stringify({ lead_ids: leadIds }), responseType: 'blob' }),
};
