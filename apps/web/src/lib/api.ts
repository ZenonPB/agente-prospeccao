import type { Lead, Campaign, Enrichment } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, ...fetchOptions } = options;

  // Build URL with query params
  const url = new URL(`${API_BASE_URL}${endpoint}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    });
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((fetchOptions.headers as Record<string, string>) || {}),
  };

  const response = await fetch(url.toString(), {
    ...fetchOptions,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: "Erro desconhecido" }));
    throw new Error(error.message || `Erro ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

// Leads API
export const leadsApi = {
  list: (params?: {
    status?: string;
    campaign_id?: string;
    search?: string;
    min_score?: number;
    limit?: number;
    offset?: number;
  }) => request<{ leads: Lead[]; total: number }>("/api/leads", { params: params as Record<string, string | number | boolean | undefined> }),

  get: (id: string) => request<Lead & { enrichment?: Enrichment }>(`/api/leads/${id}`),

  stats: () => request<{
    total: number;
    by_status: Record<string, number>;
    avg_score: number;
    qualified_count: number;
    qualified_pct: number;
    contacted_count: number;
    meetings_count: number;
  }>("/api/leads/stats"),
};

// Campaigns API
export const campaignsApi = {
  list: (params?: { status?: string; limit?: number; offset?: number }) =>
    request<{ campaigns: Campaign[]; total: number }>("/api/campaigns", { params: params as Record<string, string | number | boolean | undefined> }),

  get: (id: string) => request<Campaign>(`/api/campaigns/${id}`),

  create: (data: {
    name: string;
    target_service?: string;
    target_segment?: string;
    target_city?: string;
    target_state?: string;
    target_country?: string;
  }) =>
    request<Campaign>("/api/campaigns", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// Metrics API
export const metricsApi = {
  get: () =>
    request<{
      total_leads: number;
      qualified_leads: number;
      contacted_leads: number;
      meetings_scheduled: number;
      response_rate: number;
      funnel: { stage: string; count: number }[];
    }>("/api/metrics"),
};

// Pipeline API
export const pipelineApi = {
  start: (data: { query: string; max_leads?: number; campaign_id?: string }) =>
    request<{ job_id: string; status: string }>("/api/pipeline/start", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// WebSocket connection helper
export function createPipelineWs(jobId: string): WebSocket {
  const wsUrl = API_BASE_URL.replace(/^http/, "ws") + `/api/pipeline/ws/${jobId}`;
  return new WebSocket(wsUrl);
}
