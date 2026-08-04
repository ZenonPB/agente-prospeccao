import { getSession } from "next-auth/react";
import type { Lead, Campaign, Enrichment, PitchOnePager, CsvImportResult } from "@/types";
import type { OutreachMessages } from "@/types";
import type { OrgMembership, OrganizationMember, SalesRole } from "@/types";

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

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
  responseType?: "json" | "blob";
}


async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, responseType = "json", ...fetchOptions } = options;

  const url = new URL(`${API_BASE_URL}${endpoint}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    });
  }

  const headers: Record<string, string> = {
    ...((fetchOptions.headers as Record<string, string>) || {}),
  };

  if (!(fetchOptions.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

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

  if (responseType === "blob") {
    return response.blob() as Promise<T>;
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

  assign: (id: string, assignedToId: string | null) =>
    request<{ id: string; company_name: string; assigned_to_id: string | null; assigned_at: string | null; assigned_to_name: string | null; previous_assignee_id: string | null }>(`/api/leads/${id}/assign`, {
      method: "PATCH",
      body: JSON.stringify({ assigned_to_id: assignedToId }),
    }),

  generateMessages: (id: string, channel: "EMAIL" | "WHATSAPP" = "EMAIL") =>
    request<OutreachMessages>(`/api/leads/${id}/generate-messages`, {
      method: "POST",
      body: JSON.stringify({ channel }),
    }),

  getPitch: (id: string) =>
    request<PitchOnePager>(`/api/leads/${id}/pitch`),

  enrichContacts: (id: string, cnpj?: string) =>
    request<{ contacts: import("@/types").ContactItem[] }>(`/api/leads/${id}/enrich-contacts`, {
      method: "POST",
      body: JSON.stringify({ cnpj: cnpj || "" }),
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

  patch: (id: string, data: {
    name?: string;
    analysis_profile?: 'web_presence' | 'business_opportunity';
    target_service?: string;
    target_segment?: string;
    target_city?: string;
    target_state?: string;
    target_country?: string;
    places_query?: string;
    scoring_template_id?: string | null;
  }) =>
    request<{ id: string; name: string; scoring_template_id: string | null }>(`/api/campaigns/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  create: (data: {
    name: string;
    analysis_profile?: 'web_presence' | 'business_opportunity';
    target_service?: string;
    target_segment?: string;
    target_city?: string;
    target_state?: string;
    target_country?: string;
    places_query?: string;
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

  fromBrief: (brief: string) =>
    request<{
      name: string;
      target_service: string;
      target_segment: string;
      target_city: string;
      target_state: string;
      analysis_profile: 'web_presence' | 'business_opportunity';
      places_query: string;
      scoring_template_label: string;
      scoring_template_id: string | null;
      template_route: string;
      rationale: string;
    }>("/api/campaigns/from-brief", {
      method: "POST",
      body: JSON.stringify({ brief }),
    }),

  importCsv: (campaignId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<CsvImportResult>(`/api/campaigns/${campaignId}/import`, {
      method: "POST",
      body: formData,
    });
  },

  collectCnae: (campaignId: string, data: { cnae_code?: string; cnpjs?: string[]; max_leads?: number }) =>
    request<{ job_id: string; status: string; cnae_code?: string }>(`/api/campaigns/${campaignId}/collect-cnae`, {
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

export interface OrgSecretStatus {
  key_name: string;
  configured: boolean;
}

export const orgsApi = {
  me: () =>
    request<OrgMembership>("/api/orgs/me"),

  listMyOrganizations: () =>
    request<{ organizations: import("@/types").OrganizationListItem[] }>("/api/orgs/my-organizations"),

  listMembers: (orgId: string) =>
    request<{ members: OrganizationMember[] }>(`/api/orgs/${orgId}/members`),

  patchMemberSalesRole: (orgId: string, userId: string, salesRole: SalesRole) =>
    request<OrganizationMember>(`/api/orgs/${orgId}/members/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ sales_role: salesRole }),
    }),

  listSecrets: (orgId: string) =>
    request<{ secrets: OrgSecretStatus[] }>(`/api/orgs/${orgId}/secrets`),

  putSecret: (orgId: string, keyName: string, value: string) =>
    request<OrgSecretStatus>(`/api/orgs/${orgId}/secrets/${keyName}`, {
      method: "PUT",
      body: JSON.stringify({ value }),
    }),

  deleteSecret: (orgId: string, keyName: string) =>
    request<OrgSecretStatus>(`/api/orgs/${orgId}/secrets/${keyName}`, {
      method: "DELETE",
    }),
};

export interface AnalyticsOverview {
  total_leads: number;
  qualified_leads: number;
  contacted_leads: number;
  responded_leads: number;
  meetings_scheduled: number;
  proposals_sent: number;
  converted_leads: number;
  total_revenue: number;
  conversion_rate: number;
  response_rate: number;
  meeting_rate: number;
  funnel: { stage: string; count: number }[];
  leads_by_score_band: { band: string; count: number }[];
}

export interface AnalyticsConsultant {
  user_id: string;
  name: string;
  email: string;
  assigned_leads: number;
  contacted_leads: number;
  meetings: number;
  proposals_sent: number;
  converted_leads: number;
  conversion_rate: number;
}

export interface AnalyticsRankingItem {
  id: string;
  company_name: string;
  city: string;
  state: string;
  status: string;
  qualification_score: number;
  campaign_id: string | null;
  assigned_to_name: string | null;
  created_at: string;
  converted: boolean;
}

export interface AnalyticsGeoCity {
  city: string;
  state: string;
  count: number;
  avg_score: number;
  converted: number;
}

export interface AnalyticsGeoState {
  state: string;
  count: number;
  avg_score: number;
  converted: number;
}

export interface AnalyticsCampaign {
  id: string;
  name: string;
  leads: number;
  qualified_leads: number;
  contacted_leads: number;
  meetings: number;
  converted_leads: number;
  conversion_rate: number;
  revenue: number;
}

export interface AnalyticsTimelineItem {
  date: string;
  new_leads: number;
  meetings: number;
  closed: number;
}

export const analyticsApi = {
  overview: (params?: { from?: string; to?: string }) =>
    request<AnalyticsOverview>("/api/analytics/overview", {
      params: params as Record<string, string | number | boolean | undefined>,
    }),

  consultants: (params?: { from?: string; to?: string }) =>
    request<{ consultants: AnalyticsConsultant[] }>("/api/analytics/consultants", {
      params: params as Record<string, string | number | boolean | undefined>,
    }),

  leadsRanking: (params?: { sort_by?: "score" | "converted" | "created"; campaign_id?: string; from?: string; to?: string; limit?: number }) =>
    request<{ sort_by: string; items: AnalyticsRankingItem[] }>("/api/analytics/leads-ranking", {
      params: params as Record<string, string | number | boolean | undefined>,
    }),

  geo: (params?: { from?: string; to?: string }) =>
    request<{ cities: AnalyticsGeoCity[]; states: AnalyticsGeoState[] }>("/api/analytics/geo", {
      params: params as Record<string, string | number | boolean | undefined>,
    }),

  campaigns: (params?: { from?: string; to?: string }) =>
    request<{ campaigns: AnalyticsCampaign[] }>("/api/analytics/campaigns", {
      params: params as Record<string, string | number | boolean | undefined>,
    }),

  timeline: (params?: { group_by?: "day" | "week"; from?: string; to?: string }) =>
    request<{ timeline: AnalyticsTimelineItem[] }>("/api/analytics/timeline", {
      params: params as Record<string, string | number | boolean | undefined>,
    }),

  exportPdf: (params?: { from?: string; to?: string }) => {
    const qs = new URLSearchParams();
    if (params?.from) qs.set("from", params.from);
    if (params?.to) qs.set("to", params.to);
    const q = qs.toString();
    return request<Blob>(`/api/analytics/export/pdf${q ? `?${q}` : ""}`, {
      responseType: "blob",
    });
  },
};

export interface ScoringTemplate {
  id: string;
  service_label: string;
  positive_signals: { label: string; description?: string; weight_hint: string }[];
  negative_signals: { label: string; description?: string; weight_hint: string }[];
  context_signals: { label: string; description?: string; weight_hint: string }[];
  requires_technical_report: boolean;
  requires_business_data: boolean;
  extra_instructions?: string;
  is_generated: boolean;
  is_active: boolean;
  organization_id: string | null;
}

export interface ScoringTemplateInput {
  service_label: string;
  positive_signals?: { label: string; description?: string; weight_hint: string }[];
  negative_signals?: { label: string; description?: string; weight_hint: string }[];
  context_signals?: { label: string; description?: string; weight_hint: string }[];
  requires_technical_report?: boolean;
  requires_business_data?: boolean;
  extra_instructions?: string;
  is_active?: boolean;
}

export const scoringTemplatesApi = {
  list: (params?: { scope?: 'all' | 'global' | 'org'; include_inactive?: boolean; search?: string }) =>
    request<{ total: number; templates: ScoringTemplate[] }>("/api/scoring-templates", {
      params: params as Record<string, string | number | boolean | undefined>,
    }),
  get: (id: string) => request<ScoringTemplate>(`/api/scoring-templates/${id}`),
  create: (data: ScoringTemplateInput) =>
    request<ScoringTemplate>("/api/scoring-templates", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  patch: (id: string, data: Partial<ScoringTemplateInput>) =>
    request<ScoringTemplate>(`/api/scoring-templates/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
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

export const invitesApi = {
  create: (orgId: string, data: { email: string; role: import("@/types").OrgRole; sales_role: import("@/types").SalesRole }) =>
    request<import("@/types").Invite>(`/api/orgs/${orgId}/invites`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  
  list: (orgId: string) =>
    request<{ invites: import("@/types").Invite[] }>(`/api/orgs/${orgId}/invites`),
  
  accept: (token: string) =>
    request<{
      message: string;
      organization: { id: string; name: string; slug: string };
      membership: { role: import("@/types").OrgRole; sales_role: import("@/types").SalesRole };
    }>("/api/invites/accept", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  
  revoke: (orgId: string, inviteId: string) =>
    request<{ message: string }>(`/api/orgs/${orgId}/invites/${inviteId}`, {
      method: "DELETE",
    }),
};

// Helper de conexão WebSocket — passa token JWT como query param para autenticação
export function createPipelineWs(jobId: string): WebSocket {
  const token = getCachedToken();
  const baseUrl = API_BASE_URL.replace(/^http/, "ws") + `/api/pipeline/ws/${jobId}`;
  const wsUrl = token ? `${baseUrl}?token=${encodeURIComponent(token)}` : baseUrl;
  return new WebSocket(wsUrl);
}
