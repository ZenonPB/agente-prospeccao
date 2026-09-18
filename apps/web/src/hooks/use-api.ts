"use client";

import { useEffect } from "react";
import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { leadsApi, campaignsApi, importsApi, metricsApi, pipelineApi, scoringTemplatesApi, orgsApi, analyticsApi, invitesApi, authApi, notificationsApi, crmApi, intelligenceApi, registryApi, type ScoringTemplateInput, type CommercialFilterParams, type CommercialFilterSnapshot } from "@/lib/api";
import type { BulkLeadCommand, ImportJobStatus, ImportMapping, ImportRowStatus, OnboardingStatus, SalesRole, OrgRole } from "@/types";
import { isImportJobTerminal } from "@/types";

export type SegmentSuggestion = {
  segment: string;
  rationale: string;
  subniches: string[];
  hook: string;
  cities_hint: string[];
};

export function useLeads(params?: {
  status?: string;
  campaign_id?: string;
  search?: string;
  min_score?: number;
  priority?: string;
  assigned?: string;
  consultant_id?: string;
  next_action_before?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: ["leads", params],
    queryFn: () => leadsApi.list(params),
  });
}

const PAGE_SIZE = 100;

export function useAllLeads(params?: {
  status?: string;
  campaign_id?: string;
  search?: string;
  min_score?: number;
  priority?: string;
  assigned?: string;
  consultant_id?: string;
}) {
  return useQuery({
    queryKey: ["leads", "all", params],
    queryFn: async () => {
      // Paginação server-side (item 4.16): busca todas as páginas de 100 até
      // esgotar o `total` devolvido pela API, em vez de trazer tudo em memória
      // ou limitar a primeira página.
      let all: Awaited<ReturnType<typeof leadsApi.list>>["leads"] = [];
      let total = Infinity;
      for (let offset = 0; offset < total; offset += PAGE_SIZE) {
        const page = await leadsApi.list({ ...params, limit: PAGE_SIZE, offset });
        total = page.total;
        all = all.concat(page.leads);
        if (page.leads.length === 0 || page.leads.length < PAGE_SIZE) break;
      }
      return { leads: all, total: all.length };
    },
  });
}

const LIST_PAGE_SIZE = 50;

export function useInfiniteLeads(params?: {
  status?: string;
  campaign_id?: string;
  search?: string;
  min_score?: number;
  priority?: string;
  assigned?: string;
  consultant_id?: string;
  next_action_before?: string;
}) {
  return useInfiniteQuery({
    queryKey: ["leads", "infinite", params],
    queryFn: ({ pageParam }) => leadsApi.list({
      ...params,
      limit: LIST_PAGE_SIZE,
      ...(pageParam ? { cursor: pageParam } : {}),
    }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });
}

export function usePreviewBulkLeads() {
  return useMutation({
    mutationFn: (body: BulkLeadCommand) => leadsApi.previewBulk(body),
  });
}

export function useExecuteBulkLeads() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: BulkLeadCommand & { idempotency_key: string }) => leadsApi.executeBulk(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

export function useLead(id: string) {
  return useQuery({
    queryKey: ["leads", id],
    queryFn: () => leadsApi.get(id),
    enabled: !!id,
  });
}

export function useLeadOpportunities(id: string) {
  return useQuery({
    queryKey: ["leads", id, "opportunities"],
    queryFn: () => leadsApi.opportunities(id),
    enabled: !!id,
  });
}

export function useLeadOpportunitiesHistory(id: string, enabled = true) {
  return useQuery({
    queryKey: ["leads", id, "opportunities-history"],
    queryFn: () => leadsApi.opportunitiesHistory(id),
    enabled: !!id && enabled,
  });
}

export function useIntelligenceEvents(limit = 100, enabled = true) {
  return useQuery({
    queryKey: ["intelligence", "events", limit],
    queryFn: () => intelligenceApi.events(limit),
    enabled,
  });
}

export function useCommercialOutcomes(params?: { offer_key?: string; offer_version?: string; from?: string; to?: string }, enabled = true) {
  return useQuery({
    queryKey: ["intelligence", "outcomes", params],
    queryFn: () => intelligenceApi.outcomes(params),
    enabled,
  });
}

export function useIntelligence(period?: { from?: string; to?: string }, enabled = true) {
  const events = useIntelligenceEvents(100, enabled);
  const outcomes = useCommercialOutcomes(period, enabled);
  return { events, outcomes };
}

export function useCommercialComparison(params: { offer_key: string; version_a: string; version_b: string; min_samples?: number }, enabled = true) {
  return useQuery({
    queryKey: ["intelligence", "comparison", params],
    queryFn: () => intelligenceApi.compare(params),
    enabled: enabled && !!params.offer_key && !!params.version_a && !!params.version_b,
  });
}

export function useApproveCommercialComparison() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; approved_version: string; evidence: string }) => intelligenceApi.approveComparison(id, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["intelligence", "comparison"] }),
  });
}

export function useLeadStats() {
  return useQuery({
    queryKey: ["leads", "stats"],
    queryFn: () => leadsApi.stats(),
  });
}

export function useSlaAlerts(limit?: number) {
  return useQuery({
    queryKey: ["leads", "sla-alerts", limit],
    queryFn: () => leadsApi.slaAlerts({ limit }),
  });
}

export function useCampaigns(params?: { status?: string; limit?: number }) {
  return useQuery({
    queryKey: ["campaigns", params],
    queryFn: () => campaignsApi.list(params),
  });
}

export function useCampaign(id: string) {
  return useQuery({
    queryKey: ["campaigns", id],
    queryFn: () => campaignsApi.get(id),
    enabled: !!id,
  });
}

export function useScoringTemplates(params?: { scope?: 'all' | 'global' | 'org'; include_inactive?: boolean; search?: string }) {
  return useQuery({
    queryKey: ["scoring-templates", params],
    queryFn: () => scoringTemplatesApi.list(params),
  });
}

export function useUpdateCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof campaignsApi.patch>[1] }) =>
      campaignsApi.patch(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      queryClient.invalidateQueries({ queryKey: ["scoring-templates"] });
    },
  });
}

export function useCreateScoringTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ScoringTemplateInput) => scoringTemplatesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scoring-templates"] });
    },
  });
}

export function useGenerateScoringTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof scoringTemplatesApi.generate>[0]) =>
      scoringTemplatesApi.generate(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scoring-templates"] });
    },
  });
}

export function useDeleteScoringTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => scoringTemplatesApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scoring-templates"] });
    },
  });
}

export function usePatchScoringTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<ScoringTemplateInput> }) =>
      scoringTemplatesApi.patch(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scoring-templates"] });
    },
  });
}

export function useCreateCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: campaignsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
    },
  });
}

export function useSuggestSegment() {
  return useMutation({
    mutationFn: campaignsApi.suggestSegment,
  });
}

export function useCampaignFromBrief() {
  return useMutation({
    mutationFn: (brief: string) => campaignsApi.fromBrief(brief),
  });
}

export type CampaignBrief = Awaited<ReturnType<typeof campaignsApi.fromBrief>>;

export function useMetrics() {
  return useQuery({
    queryKey: ["metrics"],
    queryFn: () => metricsApi.get(),
  });
}

export function useRegistryHealth() {
  return useQuery({
    queryKey: ["registry", "health"],
    queryFn: () => registryApi.health(),
  });
}

export function useUpdateLeadStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      leadsApi.updateStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useUpdateLead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { notes?: string; whatsapp?: string; next_action_at?: string | null; value?: number; expected_close_date?: string | null; lost_reason?: string } }) =>
      leadsApi.update(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["leads", variables.id] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

// Feedback de score: o consultor discorda do score da IA; vira insumo de
// calibração da IA (docs/ai-feedback-loop.md).
export function useScoreFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; suggested_score: number; reason: string; apply_to_lead?: boolean }) =>
      leadsApi.scoreFeedback(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
      queryClient.invalidateQueries({ queryKey: ["learning"] });
      queryClient.invalidateQueries({ queryKey: ["score-feedback-metrics"] });
    },
  });
}

// Painel "Aprendizados da IA": regras de calibração ativas da campanha +
// métrica de convergência IA × time.
export function useCampaignLearning(campaignId: string) {
  return useQuery({
    queryKey: ["learning", campaignId],
    queryFn: () => campaignsApi.getLearning(campaignId),
  });
}

export function useSynthesizeLearning() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (campaignId: string) => campaignsApi.synthesizeLearning(campaignId),
    onSuccess: (_data, campaignId) => {
      queryClient.invalidateQueries({ queryKey: ["learning", campaignId] });
    },
  });
}

export function useDiscardLearningRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (args: { campaignId: string; ruleIndex: number }) =>
      campaignsApi.discardLearningRule(args.campaignId, args.ruleIndex),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["learning", variables.campaignId] });
    },
  });
}

// Feedback simples de utilidade do lead: util / nao util com motivo fechado.
export function useLeadUsefulnessFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; useful: boolean; reason?: string | null; detail?: string | null }) =>
      leadsApi.usefulnessFeedback(id, body),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["leads", variables.id] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

// Convergência IA × time no BI (desvio médio semanal, org inteira).
export function useScoreFeedbackMetrics() {
  return useQuery({
    queryKey: ["score-feedback-metrics"],
    queryFn: () => leadsApi.scoreFeedbackMetrics(),
  });
}

export function useStartPipeline() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: pipelineApi.start,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["metrics"] });
    },
  });
}

export function useDiscoverEvents() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ campaignId, maxLeads }: { campaignId: string; maxLeads?: number }) =>
      pipelineApi.discoverEvents(campaignId, maxLeads),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["intelligence", "events"] });
      queryClient.invalidateQueries({ queryKey: ["pipeline"] });
    },
  });
}

export function useReanalyzeCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (args: { campaign_id: string; unscored_only?: boolean }) => {
      const { campaign_id } = args;
      return pipelineApi.reanalyzeCampaign(campaign_id, args.unscored_only ?? false);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      queryClient.invalidateQueries({ queryKey: ["metrics"] });
    },
  });
}

export function usePipelineJobs(campaignId?: string, limit = 5) {
  return useQuery({
    queryKey: ["pipeline", "jobs", campaignId ?? "all"],
    queryFn: () => pipelineApi.jobs({ campaign_id: campaignId, limit }),
    refetchInterval: 8000, // re-checks job status while the user stays on the page
  });
}

export function useInvalidateJobs() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["pipeline", "jobs"] });
}

export function useGenerateMessages() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      channel,
      variants,
      forceRegenerate,
    }: {
      id: string;
      channel?: "EMAIL" | "WHATSAPP";
      variants?: boolean;
      forceRegenerate?: boolean;
    }) =>
      leadsApi.generateMessages(id, channel, { variants, force_regenerate: forceRegenerate }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["leads", variables.id, "cadence"] });
    },
  });
}

export function useUpdateCadenceStep() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      step,
      data,
    }: {
      id: string;
      step: "OPENING" | "FOLLOWUP_1" | "FOLLOWUP_2" | "CLOSING" | "POST_SALE";
      data: { variant?: string; subject?: string; content?: string };
    }) => leadsApi.updateCadenceStep(id, step, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["leads", variables.id, "cadence"] });
      queryClient.invalidateQueries({ queryKey: ["analytics", "message-variants"] });
      queryClient.invalidateQueries({ queryKey: ["leads", variables.id, "cadence-versions", variables.step] });
    },
  });
}

export function useCadenceStepVersions(leadId: string | null, step: string | null) {
  return useQuery({
    queryKey: ["leads", leadId, "cadence-versions", step],
    queryFn: () => leadsApi.getCadenceStepVersions(leadId!, step as "OPENING" | "FOLLOWUP_1" | "FOLLOWUP_2" | "CLOSING" | "POST_SALE"),
    enabled: !!leadId && !!step,
  });
}

export function usePlaybooks(params?: { vertical?: string; author_id?: string; limit?: number }) {
  return useQuery({
    queryKey: ["playbooks", params],
    queryFn: () => leadsApi.listPlaybooks(params),
  });
}

export function useCreatePlaybook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { vertical?: string; subject: string; body: string; tags?: string[] }) =>
      leadsApi.createPlaybook(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["playbooks"] });
    },
  });
}

export function useDeletePlaybook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => leadsApi.deletePlaybook(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["playbooks"] });
    },
  });
}

export function useLeadDuplicates(id: string) {
  return useQuery({
    queryKey: ["lead-duplicates", id],
    queryFn: () => leadsApi.getDuplicates(id),
    enabled: !!id,
    staleTime: 60_000,
  });
}

export function useOrgMembership() {
  return useQuery({
    queryKey: ["org", "me"],
    queryFn: () => orgsApi.me(),
  });
}

export function useOrgMembers(orgId?: string) {
  return useQuery({
    queryKey: ["org", orgId, "members"],
    queryFn: () => orgsApi.listMembers(orgId as string),
    enabled: !!orgId,
  });
}

export function usePatchMemberSalesRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, userId, salesRole }: { orgId: string; userId: string; salesRole: SalesRole }) =>
      orgsApi.patchMemberSalesRole(orgId, userId, salesRole),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org", "me"] });
      queryClient.invalidateQueries({ queryKey: ["org"] });
    },
  });
}

export function useRemoveMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, userId }: { orgId: string; userId: string }) =>
      orgsApi.removeMember(orgId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useTransferOwnership() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, newOwnerUserId }: { orgId: string; newOwnerUserId: string }) =>
      orgsApi.transferOwnership(orgId, newOwnerUserId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org"] });
      queryClient.invalidateQueries({ queryKey: ["my-organizations"] });
    },
  });
}

export function useLeaveOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId }: { orgId: string }) =>
      orgsApi.leaveOrganization(orgId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org"] });
      queryClient.invalidateQueries({ queryKey: ["my-organizations"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useSalesTargets(orgId?: string, month?: string) {
  return useQuery({
    queryKey: ["org", orgId, "sales-targets", month],
    queryFn: () => orgsApi.listSalesTargets(orgId as string, month),
    enabled: !!orgId,
  });
}

export function useUpsertSalesTarget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, data }: { orgId: string; data: { user_id: string; month: string; meetings_target: number; revenue_target: number } }) =>
      orgsApi.upsertSalesTarget(orgId, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["org", variables.orgId, "sales-targets"] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

export function useDeleteSalesTarget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, targetId }: { orgId: string; targetId: string }) =>
      orgsApi.deleteSalesTarget(orgId, targetId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["org", variables.orgId, "sales-targets"] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

export function useAssignLead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, assignedToId }: { id: string; assignedToId: string | null }) =>
      leadsApi.assign(id, assignedToId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useLeadPitch(id: string) {
  return useQuery({
    queryKey: ["leads", id, "pitch"],
    queryFn: () => leadsApi.getPitch(id),
    enabled: !!id,
  });
}

export type AnalyticsPeriod = Pick<CommercialFilterSnapshot, "from" | "to">;

const EMPTY_COMMERCIAL_FILTERS: CommercialFilterSnapshot = {};

type AnalyticsFilters = CommercialFilterParams | AnalyticsPeriod;

export function useAnalyticsOverview(filters?: AnalyticsFilters) {
  const snapshot = filters ?? EMPTY_COMMERCIAL_FILTERS;
  return useQuery({
    queryKey: ["analytics", "overview", snapshot],
    queryFn: () => analyticsApi.overview(snapshot),
  });
}

export function useAnalyticsFunnel(filters?: AnalyticsFilters) {
  const snapshot = filters ?? EMPTY_COMMERCIAL_FILTERS;
  return useQuery({
    queryKey: ["analytics", "funnel", snapshot],
    queryFn: () => analyticsApi.funnel(snapshot),
  });
}

export function useAnalyticsExecutiveMetrics(filters?: AnalyticsFilters, k = 10) {
  const snapshot = filters ?? EMPTY_COMMERCIAL_FILTERS;
  return useQuery({
    queryKey: ["analytics", "executive-metrics", snapshot, k],
    queryFn: () => analyticsApi.executiveMetrics({ ...snapshot, k }),
  });
}

export function useAnalyticsConsultants(filters?: AnalyticsFilters) {
  const snapshot = filters ?? EMPTY_COMMERCIAL_FILTERS;
  return useQuery({
    queryKey: ["analytics", "consultants", snapshot],
    queryFn: () => analyticsApi.consultants(snapshot),
  });
}

export function useAnalyticsConsultantDetail(userId: string, filters?: AnalyticsFilters) {
  const snapshot = filters ?? EMPTY_COMMERCIAL_FILTERS;
  return useQuery({
    queryKey: ["analytics", "consultants", userId, snapshot],
    queryFn: () => analyticsApi.consultantDetail(userId, snapshot),
    enabled: !!userId,
  });
}

export function useAnalyticsConsultantActivity(userId: string, filters?: AnalyticsFilters, limit = 50) {
  const snapshot = filters ?? EMPTY_COMMERCIAL_FILTERS;
  return useQuery({
    queryKey: ["analytics", "consultants", userId, "activity", snapshot, limit],
    queryFn: () => analyticsApi.consultantActivity(userId, { ...snapshot, limit }),
    enabled: !!userId,
  });
}

export function useAnalyticsRanking(filters?: AnalyticsFilters) {
  const snapshot = filters ?? EMPTY_COMMERCIAL_FILTERS;
  return useQuery({
    queryKey: ["analytics", "ranking", snapshot],
    queryFn: () => analyticsApi.leadsRanking({ ...snapshot, limit: 10 }),
  });
}

export function useAnalyticsGeo(filters?: AnalyticsFilters) {
  const snapshot = filters ?? EMPTY_COMMERCIAL_FILTERS;
  return useQuery({
    queryKey: ["analytics", "geo", snapshot],
    queryFn: () => analyticsApi.geo(snapshot),
  });
}

export function useAnalyticsCampaigns(filters?: AnalyticsFilters) {
  const snapshot = filters ?? EMPTY_COMMERCIAL_FILTERS;
  return useQuery({
    queryKey: ["analytics", "campaigns", snapshot],
    queryFn: () => analyticsApi.campaigns(snapshot),
  });
}

export function useAnalyticsTimeline(filters?: AnalyticsFilters) {
  const snapshot = filters ?? EMPTY_COMMERCIAL_FILTERS;
  return useQuery({
    queryKey: ["analytics", "timeline", snapshot],
    queryFn: () => analyticsApi.timeline({ ...snapshot, group_by: "day" }),
  });
}

export function useAnalyticsForecast(filters?: AnalyticsFilters) {
  const snapshot = filters ?? EMPTY_COMMERCIAL_FILTERS;
  return useQuery({
    queryKey: ["analytics", "forecast", snapshot],
    queryFn: () => analyticsApi.forecast(snapshot),
  });
}

export function useAnalyticsThresholdSuggestion(filters?: AnalyticsFilters) {
  const snapshot = filters ?? EMPTY_COMMERCIAL_FILTERS;
  return useQuery({
    queryKey: ["analytics", "threshold-suggestion", snapshot],
    queryFn: () => analyticsApi.thresholdSuggestion(snapshot),
  });
}

export function useAnalyticsMessageVariants(filters?: AnalyticsFilters) {
  const snapshot = filters ?? EMPTY_COMMERCIAL_FILTERS;
  return useQuery({
    queryKey: ["analytics", "message-variants", snapshot],
    queryFn: () => analyticsApi.messageVariants(snapshot),
  });
}

export function useAnalyticsTemplateInsights(filters?: AnalyticsFilters) {
  const snapshot = filters ?? EMPTY_COMMERCIAL_FILTERS;
  return useQuery({
    queryKey: ["analytics", "template-insights", snapshot],
    queryFn: () => analyticsApi.templateInsights(snapshot),
  });
}

export function useExportAnalyticsPdf() {
  return useMutation({
    mutationFn: (filters?: CommercialFilterSnapshot) => analyticsApi.exportPdf(filters),
  });
}

export function useMyOrganization() {
  // Mesmo cache de `useOrgMembership` (chave ["org","me"]) — evita fetch
  // duplicado do GET /orgs/me com chaves divergentes.
  return useOrgMembership();
}

export function useMyOrganizations() {
  return useQuery({
    queryKey: ["orgs", "list"],
    queryFn: () => orgsApi.listMyOrganizations(),
  });
}

export function useCreateInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, email, role, salesRole }: { orgId: string; email: string; role: OrgRole; salesRole: SalesRole }) =>
      invitesApi.create(orgId, { email, role, sales_role: salesRole }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["invites", variables.orgId] });
    },
  });
}

export function useInvites(orgId: string) {
  return useQuery({
    queryKey: ["invites", orgId],
    queryFn: () => invitesApi.list(orgId),
    enabled: !!orgId,
  });
}

export function useAcceptInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (token: string) => invitesApi.accept(token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orgs"] });
    },
  });
}

export function useCheckInvite(token: string) {
  return useQuery({
    queryKey: ["invites", "check", token],
    queryFn: () => invitesApi.check(token),
    enabled: !!token,
    retry: false,
  });
}

export function useAcceptRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ token, name, password }: { token: string; name: string; password: string }) =>
      invitesApi.acceptRegister(token, name, password),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orgs"] });
    },
  });
}

export function useCreateOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, emailFrom }: { name: string; emailFrom?: string }) =>
      orgsApi.createOrganization(name, emailFrom),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orgs", "list"] });
      queryClient.invalidateQueries({ queryKey: ["org", "me"] });
    },
  });
}

export function useRenameOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, name }: { orgId: string; name: string }) =>
      orgsApi.renameOrganization(orgId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orgs", "list"] });
      queryClient.invalidateQueries({ queryKey: ["org", "me"] });
    },
  });
}

export function useRevokeInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, inviteId }: { orgId: string; inviteId: string }) =>
      invitesApi.revoke(orgId, inviteId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["invites", variables.orgId] });
    },
  });
}

export function useOrgSecrets(orgId?: string) {
  return useQuery({
    queryKey: ["org", orgId, "secrets"],
    queryFn: () => orgsApi.listSecrets(orgId as string),
    enabled: !!orgId,
  });
}

export function usePutOrgSecret() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, keyName, value }: { orgId: string; keyName: string; value: string }) =>
      orgsApi.putSecret(orgId, keyName, value),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["org", variables.orgId, "secrets"] });
    },
  });
}

export function useDeleteOrgSecret() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, keyName }: { orgId: string; keyName: string }) =>
      orgsApi.deleteSecret(orgId, keyName),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["org", variables.orgId, "secrets"] });
    },
  });
}

export function useOrgAuditLog(orgId?: string, event?: string) {
  return useQuery({
    queryKey: ["org", orgId, "audit-log", event ?? "all"],
    queryFn: () => orgsApi.listAuditLog(orgId as string, event),
    enabled: !!orgId,
  });
}

export function useWebhookLogs(orgId?: string, limit?: number) {
  return useQuery({
    queryKey: ["org", orgId, "webhook-logs", limit],
    queryFn: () => orgsApi.listWebhookLogs(orgId as string, limit),
    enabled: !!orgId,
    refetchInterval: 15000,
  });
}

export function useJobLogs(orgId?: string, limit?: number) {
  return useQuery({
    queryKey: ["org", orgId, "job-logs", limit],
    queryFn: () => orgsApi.listJobLogs(orgId as string, limit),
    enabled: !!orgId,
    refetchInterval: 15000,
  });
}

export function useImportCsv() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ campaignId, file }: { campaignId: string; file: File }) =>
      campaignsApi.importCsv(campaignId, file),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["campaigns", variables.campaignId] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useCollectCnae() {
  return useMutation({
    mutationFn: ({ campaignId, cnaeCode, cnpjs, maxLeads, porteCategory }: { campaignId: string; cnaeCode?: string; cnpjs?: string[]; maxLeads?: number; porteCategory?: string }) =>
      campaignsApi.collectCnae(campaignId, { cnae_code: cnaeCode, cnpjs, max_leads: maxLeads, porte_category: porteCategory }),
  });
}

export function useCollectPncp() {
  return useMutation({
    mutationFn: ({ campaignId, daysBack, uf, keyword, maxLeads }: { campaignId: string; daysBack?: number; uf?: string; keyword?: string; maxLeads?: number }) =>
      campaignsApi.collectPncp(campaignId, { days_back: daysBack, uf, keyword, max_leads: maxLeads }),
  });
}

export function useEnrichContacts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ leadId, cnpj }: { leadId: string; cnpj?: string }) =>
      leadsApi.enrichContacts(leadId, cnpj),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["leads", variables.leadId] });
    },
  });
}

export function useLinkedinQueries(leadId?: string) {
  return useQuery({
    queryKey: ["leads", leadId, "linkedin-query"],
    queryFn: () => leadsApi.linkedinQueries(leadId as string),
    enabled: !!leadId,
  });
}

export function useAssociateLinkedIn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ leadId, contactId, url }: { leadId: string; contactId: string; url: string }) =>
      leadsApi.associateLinkedIn(leadId, contactId, url),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["leads", variables.leadId] });
    },
  });
}

export function useRecordWhatsAppClick() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ leadId, messageText }: { leadId: string; messageText?: string }) =>
      leadsApi.recordWhatsAppClick(leadId, messageText),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["leads", variables.leadId] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useRegisterConversion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { offer_key: string; offer_version?: string; lead_opportunity_id?: string; service_sold?: string; contract_value?: number; notes?: string } }) =>
      leadsApi.registerConversion(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["leads", variables.id] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
      queryClient.invalidateQueries({ queryKey: ["metrics"] });
    },
  });
}

export function useLeadCadence(id: string) {
  return useQuery({
    queryKey: ["leads", id, "cadence"],
    queryFn: () => leadsApi.getCadence(id),
    enabled: !!id,
  });
}

export function useStartCadence() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => leadsApi.startCadence(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["leads", id, "cadence"] });
      queryClient.invalidateQueries({ queryKey: ["leads", id] });
    },
  });
}

export function useSendCadenceStep() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, step }: { id: string; step: string }) =>
      leadsApi.sendCadenceStep(id, step),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["leads", variables.id, "cadence"] });
      queryClient.invalidateQueries({ queryKey: ["leads", variables.id] });
    },
  });
}

export function useOptOutLead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => leadsApi.optOutLead(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["leads", id, "cadence"] });
      queryClient.invalidateQueries({ queryKey: ["leads", id] });
    },
  });
}

export function useMarkResponded() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => leadsApi.markResponded(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["leads", id, "cadence"] });
      queryClient.invalidateQueries({ queryKey: ["leads", id] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export const LOST_REASON_OPTIONS = ["PRECO", "PRAZO", "NAO_RESPONDEU", "CONCORRENTE", "OUTRO"] as const;
export type LostReasonOption = (typeof LOST_REASON_OPTIONS)[number];

export function useMarkLost() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, lost_reason }: { id: string; lost_reason: LostReasonOption }) =>
      leadsApi.markLost(id, lost_reason),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["leads", variables.id] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useMarkDisqualified() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      leadsApi.markDisqualified(id, reason),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["leads", variables.id] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function usePatchNegotiation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: {
      negotiation_stage?: import("@/types").NegotiationStage | null;
      contract_outcome?: import("@/types").ContractOutcome | null;
    } }) => leadsApi.patchNegotiation(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["leads", variables.id] });
    },
  });
}

export function useRegisterPostSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { channel: "WHATSAPP" | "EMAIL"; subject?: string; content?: string } }) =>
      leadsApi.registerPostSale(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["leads", variables.id] });
      queryClient.invalidateQueries({ queryKey: ["leads", variables.id, "cadence"] });
    },
  });
}

export function usePatchOrgSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, data }: { orgId: string; data: {
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
    } }) =>
      orgsApi.patchSettings(orgId, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["org", "me"] });
      queryClient.invalidateQueries({ queryKey: ["orgs", "me"] });
      queryClient.invalidateQueries({ queryKey: ["orgs", variables.orgId, "usage"] });
      queryClient.invalidateQueries({ queryKey: ["analytics", "threshold-suggestion"] });
    },
  });
}

export function useOrgUsage(orgId?: string) {
  return useQuery({
    queryKey: ["orgs", orgId, "usage"],
    queryFn: () => orgsApi.getUsage(orgId as string),
    enabled: !!orgId,
  });
}

export function useUserMe() {
  return useQuery({
    queryKey: ["user", "me"],
    queryFn: () => authApi.getMe(),
    staleTime: 1000 * 60 * 5,
  });
}

export function useUpdateOnboardingStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (status: OnboardingStatus) => authApi.updateOnboardingStatus(status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user", "me"] });
    },
  });
}

export function useNotifications(params?: { limit?: number; unread_only?: boolean }) {
  return useQuery({
    queryKey: ["notifications", params],
    queryFn: () => notificationsApi.list(params),
    refetchInterval: 15000, // Poll a cada 15s
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

// CRM — envia a planilha e recebe a versão atualizada com os leads do consultor.
export function useAtualizarPlanilha() {
  return useMutation({
    mutationFn: ({ file, abaName, criarAba }: { file: File; abaName: string; criarAba: boolean }) =>
      crmApi.atualizarPlanilha(file, abaName, criarAba),
  });
}


export function useImportJob(importId?: string, enabled = true) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["imports", importId],
    queryFn: () => importsApi.get(importId as string),
    enabled: Boolean(importId) && enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status as ImportJobStatus | undefined;
      return status && !isImportJobTerminal(status) ? 2000 : false;
    },
  });

  useEffect(() => {
    const job = query.data;
    if (!job || !["SUCCEEDED", "PARTIAL", "CANCELLED"].includes(job.status)) return;
    queryClient.invalidateQueries({ queryKey: ["leads"] });
    if (job.campaign_id) queryClient.invalidateQueries({ queryKey: ["campaigns", job.campaign_id] });
  }, [query.data, queryClient]);

  return query;
}

export function useImportRows(
  importId?: string,
  status?: ImportRowStatus,
  offset = 0,
  enabled = true,
) {
  return useQuery({
    queryKey: ["imports", importId, "rows", status ?? "all", offset],
    queryFn: () => importsApi.rows(importId as string, { status, offset, limit: 25 }),
    enabled: Boolean(importId) && enabled,
    placeholderData: (previous) => previous,
  });
}

export function useUploadImport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ campaignId, file }: { campaignId: string; file: File }) =>
      importsApi.upload(campaignId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["imports"] });
    },
  });
}

export function useImportDryRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ importId, mapping, expectedVersion }: { importId: string; mapping: ImportMapping; expectedVersion: number }) =>
      importsApi.dryRun(importId, { mapping, expected_version: expectedVersion }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["imports", variables.importId] });
    },
  });
}

function invalidateImportEffects(queryClient: ReturnType<typeof useQueryClient>, importId: string, campaignId?: string | null) {
  queryClient.invalidateQueries({ queryKey: ["imports", importId] });
  queryClient.invalidateQueries({ queryKey: ["imports", importId, "rows"] });
  queryClient.invalidateQueries({ queryKey: ["leads"] });
  if (campaignId) queryClient.invalidateQueries({ queryKey: ["campaigns", campaignId] });
}

export function useConfirmImport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ importId, mapping, mappingVersion, expectedVersion, idempotencyKey }: {
      importId: string;
      campaignId?: string | null;
      mapping: ImportMapping;
      mappingVersion: string;
      expectedVersion: number;
      idempotencyKey: string;
    }) => importsApi.confirm(importId, {
      mapping,
      mapping_version: mappingVersion,
      expected_version: expectedVersion,
      idempotency_key: idempotencyKey,
    }),
    onSuccess: (job, variables) => invalidateImportEffects(queryClient, job.id, variables.campaignId),
  });
}

export function useCancelImport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ importId, expectedVersion }: { importId: string; campaignId?: string | null; expectedVersion?: number }) =>
      importsApi.cancel(importId, expectedVersion),
    onSuccess: (job, variables) => invalidateImportEffects(queryClient, job.id, variables.campaignId),
  });
}

export function useRecoverImport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ importId, expectedVersion }: { importId: string; campaignId?: string | null; expectedVersion: number }) =>
      importsApi.recover(importId, expectedVersion),
    onSuccess: (job, variables) => invalidateImportEffects(queryClient, job.id, variables.campaignId),
  });
}
