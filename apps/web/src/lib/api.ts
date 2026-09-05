import { getSession } from "next-auth/react";
import type { Lead, Campaign, Enrichment, PitchOnePager, CsvImportResult, LeadOpportunity, EventOpportunity, CommercialOutcome, CommercialOutcomeMetric } from "@/types";
import type { OutreachMessages } from "@/types";
import type { OrgMembership, OrganizationMember, SalesRole, LeadCadence, FollowUpItem, FollowUpVersion, ConsultantPlaybook, LeadDuplicate } from "@/types";


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

// Organização ativa gravada pelo OrgSwitcher (chave em `org-switcher.tsx`).
// Quando presente, define o workspace multi-org nas chamadas à API.
function getActiveOrganizationId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("active_organization_id");
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

  // Workspace ativo (org switcher) em multi-org — o backend valida a membership.
  const activeOrgId = getActiveOrganizationId();
  if (activeOrgId) {
    headers["X-Organization-Id"] = activeOrgId;
  }

  const response = await fetch(url.toString(), {
    ...fetchOptions,
    headers,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    // FastAPI devolve {detail: "..."} (ou lista de erros de validação).
    let message: string;
    if (body && typeof body.detail === "string") {
      message = body.detail;
    } else if (Array.isArray(body?.detail) && body.detail.length > 0) {
      const first = body.detail[0];
      message = typeof first === "object" && first.msg ? first.msg : JSON.stringify(first);
    } else if (body && typeof body.message === "string") {
      message = body.message;
    } else {
      message = body?.detail || `Erro ${response.status}: ${response.statusText}`;
    }
    throw new Error(message);
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
    assigned?: string;
    consultant_id?: string;
    next_action_before?: string;
    limit?: number;
    offset?: number;
  }) => request<{ leads: Lead[]; total: number }>("/api/leads", { params: params as Record<string, string | number | boolean | undefined> }),

  get: (id: string) => request<Lead & { enrichment?: Enrichment }>(`/api/leads/${id}`),

  opportunities: (id: string) => request<{ oportunidades: LeadOpportunity[] }>(`/api/leads/${id}/oportunidades`),

  update: (id: string, data: { notes?: string; whatsapp?: string; next_action_at?: string | null; value?: number; expected_close_date?: string | null; lost_reason?: string }) =>
    request<Lead>(`/api/leads/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  stats: () => request<{
    total: number;
    by_status: Record<string, number>;
    avg_score: number;
    qualified_count: number;
    qualified_pct: number;
    contacted_count: number;
    meetings_count: number;
  }>("/api/leads/stats"),

  slaAlerts: (params?: { limit?: number }) =>
    request<{ alerts: import("@/types").SlaAlertItem[] }>("/api/leads/sla-alerts", {
      params: params as Record<string, string | number | boolean | undefined>,
    }),

  updateStatus: (id: string, status: string) =>
    request<{ id: string; company_name: string; status: string; suggested_next_action_at?: string | null }>(`/api/leads/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  scoreFeedback: (id: string, body: { suggested_score: number; reason: string; apply_to_lead?: boolean }) =>
    request<{ id: string; lead_id: string; original_score: number; suggested_score: number; direction: string; status: string; applied_to_lead: boolean; lead_status?: string | null }>(`/api/leads/${id}/score-feedback`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  scoreFeedbackMetrics: () =>
    request<ScoreFeedbackMetrics>("/api/leads/score-feedback-metrics"),

  assign: (id: string, assignedToId: string | null) =>
    request<{ id: string; company_name: string; assigned_to_id: string | null; assigned_at: string | null; assigned_to_name: string | null; previous_assignee_id: string | null }>(`/api/leads/${id}/assign`, {
      method: "PATCH",
      body: JSON.stringify({ assigned_to_id: assignedToId }),
    }),

  generateMessages: (
    id: string,
    channel: "EMAIL" | "WHATSAPP" = "EMAIL",
    options?: { variants?: boolean; force_regenerate?: boolean },
  ) =>
    request<OutreachMessages>(`/api/leads/${id}/generate-messages`, {
      method: "POST",
      body: JSON.stringify({ channel, variants: options?.variants, force_regenerate: options?.force_regenerate }),
    }),

  updateCadenceStep: (
    id: string,
    step: "OPENING" | "FOLLOWUP_1" | "FOLLOWUP_2" | "CLOSING" | "POST_SALE",
    data: { variant?: string; subject?: string; content?: string },
  ) =>
    request<FollowUpItem>(`/api/leads/${id}/cadence/step/${step}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  getCadenceStepVersions: (
    id: string,
    step: "OPENING" | "FOLLOWUP_1" | "FOLLOWUP_2" | "CLOSING" | "POST_SALE",
  ) =>
    request<{ versions: FollowUpVersion[]; current: { subject: string | null; content: string | null; variant: string | null } }>(
      `/api/leads/${id}/cadence/step/${step}/versions`,
    ),

  listPlaybooks: (params?: { vertical?: string; author_id?: string; limit?: number }) =>
    request<{ items: ConsultantPlaybook[] }>("/api/playbooks", {
      params: params as Record<string, string | number | undefined>,
    }),

  createPlaybook: (data: { vertical?: string; subject: string; body: string; tags?: string[] }) =>
    request<ConsultantPlaybook>("/api/playbooks", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updatePlaybook: (id: string, data: Partial<{ vertical: string; subject: string; body: string; tags: string[] }>) =>
    request<ConsultantPlaybook>(`/api/playbooks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deletePlaybook: (id: string) =>
    request<{ deleted: boolean; id: string }>(`/api/playbooks/${id}`, {
      method: "DELETE",
    }),

  getDuplicates: (id: string) =>
    request<{ matches: LeadDuplicate[]; count: number }>(`/api/leads/${id}/duplicates`),

  getPitch: (id: string) =>
    request<PitchOnePager>(`/api/leads/${id}/pitch`),

  enrichContacts: (id: string, cnpj?: string) =>
    request<{ contacts: import("@/types").ContactItem[] }>(`/api/leads/${id}/enrich-contacts`, {
      method: "POST",
      body: JSON.stringify({ cnpj: cnpj || "" }),
    }),

  linkedinQueries: (id: string) =>
    request<{ queries: import("@/types").LinkedinQuery[]; search_url: string }>(`/api/leads/${id}/linkedin-query`),

  associateLinkedIn: (id: string, contactId: string, url: string) =>
    request<import("@/types").ContactItem>(`/api/leads/${id}/contacts/${contactId}/linkedin`, {
      method: "PATCH",
      body: JSON.stringify({ url }),
    }),

  recordWhatsAppClick: (id: string, messageText?: string) =>
    request<{ whatsapp_url: string; phone: string; is_valid: boolean; last_contacted_at: string }>(`/api/leads/${id}/whatsapp-click`, {
      method: "POST",
      body: JSON.stringify({ message_text: messageText }),
    }),

  registerConversion: (id: string, data: { service_sold?: string; contract_value?: number; notes?: string }) =>
    request<{
      id: string;
      lead_id: string;
      service_sold: string | null;
      contract_value: number | null;
      time_to_close_days: number | null;
      converted_at: string;
    }>(`/api/leads/${id}/conversion`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  patchNegotiation: (id: string, data: {
    negotiation_stage?: import("@/types").NegotiationStage | null;
    contract_outcome?: import("@/types").ContractOutcome | null;
  }) =>
    request<{
      id: string;
      negotiation_stage: string | null;
      contract_outcome: string | null;
      outcome_date: string | null;
      status: string | null;
    }>(`/api/leads/${id}/negotiation`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  registerPostSale: (id: string, data: { channel: "WHATSAPP" | "EMAIL"; subject?: string; content?: string }) =>
    request<{
      id: string;
      post_sale_contacted_at: string | null;
      post_sale_channel: string | null;
      status: string | null;
    }>(`/api/leads/${id}/post-sale`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getCadence: (id: string) =>
    request<LeadCadence>(`/api/leads/${id}/cadence`),

  startCadence: (id: string) =>
    request<LeadCadence & { playbook_applied: boolean; auto_send: boolean }>(
      `/api/leads/${id}/cadence/start`,
      { method: "POST", body: JSON.stringify({}) },
    ),

  sendCadenceStep: (id: string, step: string) =>
    request<FollowUpItem>(`/api/leads/${id}/cadence/send/${step}`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  optOutLead: (id: string) =>
    request<{ lead_id: string; opt_out: boolean }>(`/api/leads/${id}/opt-out`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
};

export const authApi = {
  getMe: () =>
    request<{ id: string; name: string; email: string; role: string; onboarding_status: import("@/types").OnboardingStatus }>("/api/auth/me"),

  updateOnboardingStatus: (status: import("@/types").OnboardingStatus) =>
    request<{ id: string; onboarding_status: import("@/types").OnboardingStatus }>("/api/auth/onboarding", {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

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
    offer_profile_key?: string | null;
    status?: 'ACTIVE' | 'PAUSED' | 'COMPLETED' | 'ARCHIVED';
  }) =>
    request<Campaign>(`/api/campaigns/${id}`, {
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
    offer_profile_key?: string;
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

  collectCnae: (campaignId: string, data: { cnae_code?: string; cnpjs?: string[]; max_leads?: number; porte_category?: string }) =>
    request<{ job_id: string; status: string; cnae_code?: string }>(`/api/campaigns/${campaignId}/collect-cnae`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  collectPncp: (campaignId: string, data: { days_back?: number; uf?: string; keyword?: string; max_leads?: number }) =>
    request<{ job_id: string; status: string; pncp_start: string; pncp_end: string }>(`/api/campaigns/${campaignId}/collect-pncp`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  exportGoogleSheets: (campaignId: string) =>
    request<Blob>(`/api/campaigns/${campaignId}/export/google-sheets`, {
      responseType: "blob",
    }),

  // Loop de aprendizado da IA (docs/ai-feedback-loop.md)
  getLearning: (campaignId: string) =>
    request<CampaignLearning>(`/api/campaigns/${campaignId}/learning`),

  synthesizeLearning: (campaignId: string) =>
    request<{ compiled: number; rules: string[]; compacted: boolean }>(`/api/campaigns/${campaignId}/synthesize-learning`, {
      method: "POST",
    }),

  discardLearningRule: (campaignId: string, ruleIndex: number) =>
    request<{ rules: string[] }>(`/api/campaigns/${campaignId}/learning/${ruleIndex}`, {
      method: "DELETE",
    }),
};

export const intelligenceApi = {
  events: (limit = 100) => request<{ events: EventOpportunity[]; total: number }>("/api/intelligence/events", { params: { limit } }),
  outcomes: (params?: { offer_key?: string; offer_version?: string }) =>
    request<{ outcomes: CommercialOutcome[]; metrics: CommercialOutcomeMetric[]; total_outcomes: number }>("/api/intelligence/outcomes", { params }),
};

// Loop de aprendizado da IA: regras de calibração + convergência IA × time.
export type DeviationPoint = { week: string; avg_deviation: number; feedbacks: number };

export type CampaignLearning = {
  rules: string[];
  compiled_from: number;
  updated_at: string | null;
  pending_feedbacks: number;
  total_feedbacks: number;
  deviation: { overall_avg: number | null; weekly: DeviationPoint[] };
};

export type ScoreFeedbackMetrics = {
  overall_avg: number | null;
  total_feedbacks: number;
  weekly: DeviationPoint[];
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

  createOrganization: (name: string, emailFrom?: string) =>
    request<{ id: string; slug: string; role: import("@/types").OrgRole; sales_role: import("@/types").SalesRole; email_from?: string | null; }>(
      "/api/orgs",
      { method: "POST", body: JSON.stringify({ name, email_from: emailFrom || undefined }) },
    ),

  renameOrganization: (orgId: string, name: string) =>
    request<{ id: string; name: string; slug: string }>(`/api/orgs/${orgId}/name`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),

  listMyOrganizations: () =>
    request<{ organizations: import("@/types").OrganizationListItem[] }>("/api/orgs/my-organizations"),

  listMembers: (orgId: string) =>
    request<{ members: OrganizationMember[] }>(`/api/orgs/${orgId}/members`),

  patchMemberSalesRole: (orgId: string, userId: string, salesRole: SalesRole) =>
    request<OrganizationMember>(`/api/orgs/${orgId}/members/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ sales_role: salesRole }),
    }),

  removeMember: (orgId: string, userId: string) =>
    request<{ removed: boolean; user_id: string; org_id: string }>(`/api/orgs/${orgId}/members/${userId}`, {
      method: "DELETE",
    }),

  transferOwnership: (orgId: string, newOwnerUserId: string) =>
    request<{ transferred: boolean; previous_owner_id: string; new_owner_id: string }>(`/api/orgs/${orgId}/transfer-owner`, {
      method: "POST",
      body: JSON.stringify({ new_owner_user_id: newOwnerUserId }),
    }),

  leaveOrganization: (orgId: string) =>
    request<{ left: boolean; org_id: string; user_id: string }>(`/api/orgs/${orgId}/leave`, {
      method: "POST",
    }),

  listSalesTargets: (orgId: string, month?: string) =>
    request<{ month: string; targets: SalesTarget[] }>(`/api/orgs/${orgId}/sales-targets`, {
      params: month ? { month } : undefined,
    }),

  upsertSalesTarget: (orgId: string, data: { user_id: string; month: string; meetings_target: number; revenue_target: number }) =>
    request<SalesTarget>(`/api/orgs/${orgId}/sales-targets`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteSalesTarget: (orgId: string, targetId: string) =>
    request<{ deleted: boolean; target_id: string }>(`/api/orgs/${orgId}/sales-targets/${targetId}`, {
      method: "DELETE",
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

  patchSettings: (orgId: string, data: {
    auto_send_email?: boolean;
    daily_email_limit?: number;
    send_window_start?: string;
    send_window_end?: string;
    email_from?: string;
    sla_qualified_no_contact_days?: number;
    sla_responded_no_next_action_days?: number;
    sla_opened_no_response_days?: number;
    qualification_threshold?: number;
    webhook_url?: string | null;
    webhook_secret?: string | null;
    scheduling_url?: string | null;
    api_quota?: Record<string, number>;
  }) =>
    request<{
      id: string;
      name: string;
      auto_send_email: boolean;
      daily_email_limit: number;
      send_window_start: string;
      send_window_end: string;
      email_from?: string | null;
      sends_today: number;
      sla_qualified_no_contact_days?: number;
      sla_responded_no_next_action_days?: number;
      sla_opened_no_response_days?: number;
      qualification_threshold?: number;
      webhook_url?: string | null;
      webhook_configured?: boolean;
      scheduling_url?: string | null;
    }>(
      `/api/orgs/${orgId}`,
      { method: "PATCH", body: JSON.stringify(data) },
    ),

  getUsage: (orgId: string) =>
    request<{ usage: import("@/types").ProviderUsageItem[]; alert: boolean }>(`/api/orgs/${orgId}/usage`),

  listAuditLog: (orgId: string, event?: string, limit?: number) =>
    request<{ entries: import("@/types").OrgAuditEntry[] }>(`/api/orgs/${orgId}/audit-log`, {
      params: {
        ...(event ? { event } : {}),
        ...(limit !== undefined ? { limit: String(limit) } : {}),
      },
    }),

  listWebhookLogs: (orgId: string, limit?: number) =>
    request<import("@/types").WebhookLogEntry[]>(`/api/orgs/${orgId}/webhook-logs`, {
      params: limit !== undefined ? { limit: String(limit) } : undefined,
    }),

  listJobLogs: (orgId: string, limit?: number) =>
    request<import("@/types").JobLogEntry[]>(`/api/orgs/${orgId}/job-logs`, {
      params: limit !== undefined ? { limit: String(limit) } : undefined,
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
  leads_by_score_band: { band: string; count: number; converted: number; conversion_rate: number }[];
  negotiation_distribution: { stage: string; count: number }[];
  contracts_by_outcome: { outcome: string; count: number }[];
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
  revenue_realized: number;
  meetings_target: number;
  revenue_target: number;
  meetings_attainment: number | null;
  revenue_attainment: number | null;
  // KPIs da planilha Alphamec.
  pitch_sent: number;
  responded_leads: number;
  pitch_rate: number;
  response_rate: number;
  contracts_approved: number;
  contracts_total: number;
  contract_approval_rate: number;
  ticket_medio: number;
  ticket_count: number;
  avg_cadence_days: number;
  cadence_days_n: number;
  avg_close_days: number;
  close_days_n: number;
  negotiation_distribution: { stage: string; count: number }[];
  contracts_by_outcome: { outcome: string; count: number }[];
  channel_distribution: { channel: string; count: number }[];
}

export interface ConsultantActivity {
  id: string;
  action: string;
  detail?: string | null;
  status_from?: string | null;
  status_to?: string | null;
  user_id?: string | null;
  created_at: string | null;
  lead_id: string;
  company_name: string;
}

export interface AnalyticsConsultantDetail {
  user_id: string;
  name: string;
  email: string;
  sales_role: string | null;
  assigned_leads: number;
  pitch_sent: number;
  responded_leads: number;
  pitch_rate: number;
  response_rate: number;
  contracts_approved: number;
  contracts_total: number;
  contract_approval_rate: number;
  ticket_medio: number;
  ticket_count: number;
  avg_cadence_days: number;
  cadence_days_n: number;
  avg_close_days: number;
  close_days_n: number;
  negotiation_distribution: { stage: string; count: number }[];
  contracts_by_outcome: { outcome: string; count: number }[];
  channel_distribution: { channel: string; count: number }[];
  funnel: AnalyticsFunnel;
}

export interface SalesTarget {
  id: string;
  user_id: string;
  name?: string | null;
  email?: string | null;
  month: string;
  meetings_target: number;
  revenue_target: number;
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

export interface AnalyticsFunnelStage {
  key: string;
  label: string;
  count: number;
  conversion_rate: number | null;
  share_of_total: number;
}

export interface AnalyticsFunnel {
  total_leads: number;
  funnel: AnalyticsFunnelStage[];
}

export const analyticsApi = {
  overview: (params?: { from?: string; to?: string }) =>
    request<AnalyticsOverview>("/api/analytics/overview", {
      params: params as Record<string, string | number | boolean | undefined>,
    }),

  funnel: (params?: { from?: string; to?: string; campaign_id?: string; consultant_id?: string }) =>
    request<AnalyticsFunnel>("/api/analytics/funnel", {
      params: params as Record<string, string | number | boolean | undefined>,
    }),

  consultants: (params?: { from?: string; to?: string }) =>
    request<{ consultants: AnalyticsConsultant[] }>("/api/analytics/consultants", {
      params: params as Record<string, string | number | boolean | undefined>,
    }),

  consultantDetail: (userId: string, params?: { from?: string; to?: string }) =>
    request<AnalyticsConsultantDetail>(`/api/analytics/consultants/${userId}`, {
      params: params as Record<string, string | number | boolean | undefined>,
    }),

  consultantActivity: (userId: string, params?: { limit?: number; from?: string; to?: string }) =>
    request<{ activities: ConsultantActivity[] }>(
      `/api/analytics/consultants/${userId}/activity`,
      {
        params: params as Record<string, string | number | boolean | undefined>,
      },
    ),

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

  forecast: (params?: { from?: string; to?: string }) =>
    request<import("@/types").ForecastData>("/api/analytics/forecast", {
      params: params as Record<string, string | number | boolean | undefined>,
    }),

  thresholdSuggestion: (params?: { from?: string; to?: string }) =>
    request<import("@/types").ThresholdSuggestion>("/api/analytics/threshold-suggestion", {
      params: params as Record<string, string | number | boolean | undefined>,
    }),

  messageVariants: (params?: { from?: string; to?: string }) =>
    request<import("@/types").MessageVariants>("/api/analytics/message-variants", {
      params: params as Record<string, string | number | boolean | undefined>,
    }),

  templateInsights: (params?: { from?: string; to?: string; campaign_id?: string }) =>
    request<import("@/types").TemplateInsights>("/api/analytics/template-insights", {
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

export interface Playbook {
  hooks?: string[];
  subject_ideas?: string[];
  objections?: { objection?: string; approach?: string }[];
  // Eixo de conteúdo por etapa da cadência (educativo → caso → proposta).
  stage_angles?: Partial<Record<"body_opening" | "followup_1" | "followup_2" | "closing", string>>;
}

export type EnrichmentStep = "technical_site" | "cnpj_receita" | "business_social";

export interface ScoringTemplate {
  id: string;
  service_label: string;
  positive_signals: { label: string; description?: string; weight_hint: string }[];
  negative_signals: { label: string; description?: string; weight_hint: string }[];
  context_signals: { label: string; description?: string; weight_hint: string }[];
  requires_technical_report: boolean;
  requires_business_data: boolean;
  enrichment_steps?: EnrichmentStep[] | null;
  cadence_schedule?: number[] | null;
  extra_instructions?: string;
  playbook?: Playbook;
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
  enrichment_steps?: EnrichmentStep[] | null;
  cadence_schedule?: number[] | null;
  extra_instructions?: string;
  playbook?: Playbook;
  is_active?: boolean;
  source_template_id?: string;
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
  generate: (data: { service: string; segment?: string; description?: string }) =>
    request<ScoringTemplate>("/api/scoring-templates/generate", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  remove: (id: string) =>
    request<{ deleted: boolean; id: string }>(`/api/scoring-templates/${id}`, {
      method: "DELETE",
    }),
};

export const pipelineApi = {
  start: (data: {
    query?: string;
    max_leads?: number;
    campaign_id?: string;
    reanalyze_only?: boolean;
    source?: 'places' | 'cnae' | 'pncp' | 'events';
  }) =>
    request<{ job_id: string; status: string }>("/api/pipeline/start", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  discoverEvents: (campaign_id: string, max_leads = 100) =>
    request<{ job_id: string; status: string }>("/api/pipeline/start", {
      method: "POST",
      body: JSON.stringify({ campaign_id, max_leads, source: "events" }),
    }),
  reanalyzeCampaign: (campaign_id: string, unscored_only = false) =>
    request<{ job_id: string; status: string; leads_to_reanalyze: number }>(
      `/api/campaigns/${campaign_id}/reanalyze${unscored_only ? "?unscored_only=true" : ""}`,
      { method: "POST", body: JSON.stringify({}) },
    ),
  jobs: (params: { campaign_id?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.campaign_id) qs.set("campaign_id", params.campaign_id);
    if (params.limit) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return request<{ jobs: PipelineJob[] }>(`/api/pipeline/jobs${q ? `?${q}` : ""}`);
  },
};

export interface PipelineJob {
  id: string;
  job_type: string;
  status: "PENDING" | "IN_PROGRESS" | "COMPLETED" | "FAILED" | "CANCELLED";
  campaign_id: string | null;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  summary?: {
    collected: number;
    qualified: number;
    scored: number;
    failed: number;
    total_processed: number;
    queue_remaining?: number;
  } | null;
}

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

  check: (token: string) =>
    request<{
      email: string;
      organization: { id: string; name: string | null; slug: string | null };
      has_account: boolean;
      accepted: boolean;
      expired: boolean;
    }>(`/api/invites/check?${new URLSearchParams({ token })}`),

  acceptRegister: (token: string, name: string, password: string) =>
    request<{
      message: string;
      user: { id: string; name: string; email: string; role: string };
      token: string;
      organization: { id: string; name: string; slug: string };
      membership: { role: import("@/types").OrgRole; sales_role: import("@/types").SalesRole };
    }>("/api/invites/accept-register", {
      method: "POST",
      body: JSON.stringify({ token, name, password }),
    }),
  
  revoke: (orgId: string, inviteId: string) =>
    request<{ message: string }>(`/api/orgs/${orgId}/invites/${inviteId}`, {
      method: "DELETE",
    }),
};

// Helper de conexão WebSocket — token JWT enviado na primeira mensagem,
// nunca na URL (evita vazamento em logs de proxy/acesso). O payload de auth
// vai junto da URL para o caller passar ao hook de reconexão (que reenvia
// auth a cada reconexão).
export function createPipelineWsUrl(jobId: string): string {
  return API_BASE_URL.replace(/^http/, "ws") + `/api/pipeline/ws/${jobId}`;
}

export function getPipelineAuthPayload(): Record<string, unknown> {
  return {
    type: "auth",
    token: getCachedToken(),
    // Org ativa do switcher — validação de workspace no WS (multi-org).
    organization_id: getActiveOrganizationId() ?? undefined,
  };
}

export interface NotificationItem {
  id: string;
  notification_type: string;
  title: string;
  message?: string;
  lead_id?: string;
  is_read: boolean;
  created_at: string;
}

export const notificationsApi = {
  list: (params?: { limit?: number; unread_only?: boolean }) =>
    request<{ notifications: NotificationItem[]; unread_count: number; total: number }>(
      "/api/notifications",
      { params: params as Record<string, string | number | boolean | undefined> },
    ),

  markRead: (id: string) =>
    request<{ success: boolean; unread_count: number }>(
      `/api/notifications/${id}/read`,
      { method: "PATCH" },
    ),

  markAllRead: () =>
    request<{ success: boolean; unread_count: number }>(
      "/api/notifications/read-all",
      { method: "PATCH" },
    ),
};

// CRM — atualização da planilha a partir dos leads do consultor.
export const crmApi = {
  atualizarPlanilha: (file: File, abaName: string, criarAba: boolean) => {
    const form = new FormData();
    form.append("file", file);
    form.append("aba_name", abaName);
    form.append("criar_aba", criarAba ? "true" : "false");
    return request<Blob>("/api/crm/spreadsheet/atualizar", {
      method: "POST",
      body: form,
      responseType: "blob",
    });
  },
};
