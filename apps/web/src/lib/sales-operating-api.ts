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

export type OperatingSearchItem = {
  id: string;
  title: string;
  subtitle?: string | null;
  href: string;
};

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

export type SavedCommercialView = {
  id: string;
  name: string;
  view_kind: 'crm' | 'analytics';
  filters: CommercialFilterSnapshot & Record<string, unknown>;
  shared: boolean;
  owner_user_id: string;
  editable: boolean;
  created_at: string;
  updated_at?: string | null;
};

export const salesOperatingApi = {
  queue: (limit = 20) => request<{ items: OperatingQueueItem[]; total: number; as_of: string }>(
    '/api/crm/operating/queue', { params: { limit } },
  ),
  search: (q: string, limit = 8) => request<OperatingSearchResponse>(
    '/api/crm/operating/search', { params: { q, limit } },
  ),
  savedViews: (viewKind?: 'crm' | 'analytics') => request<{ items: SavedCommercialView[] }>(
    '/api/crm/operating/saved-views', { params: { view_kind: viewKind } },
  ),
  createSavedView: (body: {
    name: string;
    view_kind: 'crm' | 'analytics';
    filters: Record<string, unknown>;
    shared?: boolean;
  }) => request<SavedCommercialView>('/api/crm/operating/saved-views', {
    method: 'POST', body: JSON.stringify(body),
  }),
  deleteSavedView: (id: string) => request<void>(`/api/crm/operating/saved-views/${id}`, { method: 'DELETE' }),
};
