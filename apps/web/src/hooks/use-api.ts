"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { leadsApi, campaignsApi, metricsApi, pipelineApi } from "@/lib/api";

// Leads hooks
export function useLeads(params?: {
  status?: string;
  campaign_id?: string;
  search?: string;
  min_score?: number;
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

// Campaigns hooks
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

// Metrics hooks
export function useMetrics() {
  return useQuery({
    queryKey: ["metrics"],
    queryFn: () => metricsApi.get(),
  });
}

// Pipeline hooks
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
