"use client";

import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { leadsApi, campaignsApi, metricsApi, pipelineApi, scoringTemplatesApi, orgsApi, analyticsApi, invitesApi, authApi, type ScoringTemplateInput } from "@/lib/api";
import type { SalesRole, OrgRole, OnboardingStatus } from "@/types";

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
  assigned?: string;
  consultant_id?: string;
  next_action_before?: string;
}) {
  return useInfiniteQuery({
    queryKey: ["leads", "infinite", params],
    queryFn: ({ pageParam }) =>
      leadsApi.list({ ...params, limit: LIST_PAGE_SIZE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((n, p) => n + p.leads.length, 0);
      return loaded < lastPage.total ? loaded : undefined;
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

export function useCampaigns(params?: { status?: string }) {
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
    },
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

export interface AnalyticsPeriod {
  from?: string;
  to?: string;
}

export function useAnalyticsOverview(period?: AnalyticsPeriod) {
  return useQuery({
    queryKey: ["analytics", "overview", period],
    queryFn: () => analyticsApi.overview(period),
  });
}

export function useAnalyticsFunnel(period?: AnalyticsPeriod) {
  return useQuery({
    queryKey: ["analytics", "funnel", period],
    queryFn: () => analyticsApi.funnel(period),
  });
}

export function useAnalyticsConsultants(period?: AnalyticsPeriod) {
  return useQuery({
    queryKey: ["analytics", "consultants", period],
    queryFn: () => analyticsApi.consultants(period),
  });
}

export function useAnalyticsConsultantDetail(userId: string, period?: AnalyticsPeriod) {
  return useQuery({
    queryKey: ["analytics", "consultants", userId, period],
    queryFn: () => analyticsApi.consultantDetail(userId, period),
    enabled: !!userId,
  });
}

export function useAnalyticsConsultantActivity(userId: string, period?: AnalyticsPeriod, limit = 50) {
  return useQuery({
    queryKey: ["analytics", "consultants", userId, "activity", period, limit],
    queryFn: () => analyticsApi.consultantActivity(userId, { limit, ...(period || {}) }),
    enabled: !!userId,
  });
}

export function useAnalyticsRanking(period?: AnalyticsPeriod) {
  return useQuery({
    queryKey: ["analytics", "ranking", period],
    queryFn: () => analyticsApi.leadsRanking({ ...period, limit: 10 }),
  });
}

export function useAnalyticsGeo(period?: AnalyticsPeriod) {
  return useQuery({
    queryKey: ["analytics", "geo", period],
    queryFn: () => analyticsApi.geo(period),
  });
}

export function useAnalyticsCampaigns(period?: AnalyticsPeriod) {
  return useQuery({
    queryKey: ["analytics", "campaigns", period],
    queryFn: () => analyticsApi.campaigns(period),
  });
}

export function useAnalyticsTimeline(period?: AnalyticsPeriod) {
  return useQuery({
    queryKey: ["analytics", "timeline", period],
    queryFn: () => analyticsApi.timeline({ group_by: "day", ...period }),
  });
}

export function useAnalyticsForecast(period?: AnalyticsPeriod) {
  return useQuery({
    queryKey: ["analytics", "forecast", period],
    queryFn: () => analyticsApi.forecast(period),
  });
}

export function useAnalyticsThresholdSuggestion(period?: AnalyticsPeriod) {
  return useQuery({
    queryKey: ["analytics", "threshold-suggestion", period],
    queryFn: () => analyticsApi.thresholdSuggestion(period),
  });
}

export function useAnalyticsMessageVariants(period?: AnalyticsPeriod) {
  return useQuery({
    queryKey: ["analytics", "message-variants", period],
    queryFn: () => analyticsApi.messageVariants(period),
  });
}

export function useExportAnalyticsPdf() {
  return useMutation({
    mutationFn: (period?: AnalyticsPeriod) => analyticsApi.exportPdf(period),
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
    mutationFn: ({ campaignId, cnaeCode, cnpjs, maxLeads }: { campaignId: string; cnaeCode?: string; cnpjs?: string[]; maxLeads?: number }) =>
      campaignsApi.collectCnae(campaignId, { cnae_code: cnaeCode, cnpjs, max_leads: maxLeads }),
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
    mutationFn: ({ id, data }: { id: string; data: { service_sold?: string; contract_value?: number; notes?: string } }) =>
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
