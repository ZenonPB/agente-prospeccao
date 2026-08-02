"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { leadsApi, campaignsApi, metricsApi, pipelineApi } from "@/lib/api";

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
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: ["leads", params],
    queryFn: () => leadsApi.list(params),
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
    mutationFn: (campaign_id: string) => pipelineApi.reanalyzeCampaign(campaign_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      queryClient.invalidateQueries({ queryKey: ["metrics"] });
    },
  });
}

export function useGenerateMessages() {
  return useMutation({
    mutationFn: ({ id, channel }: { id: string; channel?: "EMAIL" | "WHATSAPP" }) =>
      leadsApi.generateMessages(id, channel),
  });
}
