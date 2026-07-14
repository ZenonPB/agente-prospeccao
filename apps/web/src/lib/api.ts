import { getSession } from "next-auth/react";
import type { Lead, Campaign, Enrichment } from "@/types";
import type { OutreachMessages } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Cache de token em memória — evita chamada HTTP getSession() em toda requisição
let _cachedToken: string | null = null;

export function setAccessToken(token: string | null) {
  _cachedToken = token;
}

export function getCachedToken(): string | null {
  return _cachedToken;
}

interface SessionWithToken {
  accessToken?: string;
}

async function resolveToken(): Promise<string | null> {
  if (_cachedToken) return _cachedToken;
  const session = await getSession();
  const token = (session as SessionWithToken | null)?.accessToken;
  if (token) _cachedToken = token;
  return token ?? null;
}

interface OutreachMessages {
  subject: string;
  body_opening: string;
  followup_1: string;
  followup_2: string;
  closing: string;
  whatsapp_short: string;
  rationale: string;
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}


async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, ...fetchOptions } = options;

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

  // Adiciona token de autenticação do cache ou da sessão NextAuth
  const token = await resolveToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

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

  updateStatus: (id: string, status: string) =>
    request<{ id: string; company_name: string; status: string }>(`/api/leads/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  generateMessages: (id: string, channel: "EMAIL" | "WHATSAPP" = "EMAIL") =>
    request<OutreachMessages>(`/api/leads/${id}/generate-messages`, {
      method: "POST",
      body: JSON.stringify({ channel }),
    }),
};

export const authApi = {
  changePassword: (current_password: string, new_password: string) =>
    request<{ message: string }>("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),

  updateProfile: (name: string) =>
    request<{ id: string; name: string; email: string; role: string }>("/api/auth/profile", {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),

  forgotPassword: (email: string) =>
    request<{ message: string }>("/api/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token: string, password: string) =>
    request<{ message: string }>("/api/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),
};

export const campaignsApi = {
  list: (params?: { status?: string; limit?: number; offset?: number }) =>
    request<{ campaigns: Campaign[]; total: number }>("/api/campaigns", { params: params as Record<string, string | number | boolean | undefined> }),

  get: (id: string) => request<Campaign>(`/api/campaigns/${id}`),

  create: (data: {
    name: string;
    analysis_profile?: 'web_presence' | 'business_opportunity';
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

  suggestSegment: (data: {
    profile: 'web_presence' | 'business_opportunity';
    current_segment?: string;
    exclude?: string[];
  }) =>
    request<{
      segment: string;
      rationale: string;
      subniches: string[];
      hook: string;
      cities_hint: string[];
    }>("/api/campaigns/suggest-segment", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

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

export const pipelineApi = {
  start: (data: {
    query?: string;
    max_leads?: number;
    campaign_id?: string;
    reanalyze_only?: boolean;
  }) =>
    request<{ job_id: string; status: string }>("/api/pipeline/start", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  reanalyzeCampaign: (campaign_id: string) =>
    request<{ job_id: string; status: string; leads_to_reanalyze: number }>(
      `/api/campaigns/${campaign_id}/reanalyze`,
      { method: "POST", body: JSON.stringify({}) },
    ),
};

// Helper de conexão WebSocket — passa token JWT como query param para autenticação
export function createPipelineWs(jobId: string): WebSocket {
  const token = getCachedToken();
  const baseUrl = API_BASE_URL.replace(/^http/, "ws") + `/api/pipeline/ws/${jobId}`;
  const wsUrl = token ? `${baseUrl}?token=${encodeURIComponent(token)}` : baseUrl;
  return new WebSocket(wsUrl);
}
