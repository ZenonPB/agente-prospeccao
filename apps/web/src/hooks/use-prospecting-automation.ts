'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  prospectingAutomationApi,
  type ProspectingAlert,
  type SavedSearchFilters,
} from '@/lib/prospecting-automation-api';

const keys = {
  savedSearches: ['prospecting-automation', 'saved-searches'] as const,
  alerts: ['prospecting-automation', 'alerts'] as const,
  eventSeries: ['prospecting-automation', 'event-series'] as const,
  agentStates: ['prospecting-automation', 'agent-states'] as const,
};

export function useSavedSearches() {
  return useQuery({
    queryKey: keys.savedSearches,
    queryFn: prospectingAutomationApi.savedSearches,
    staleTime: 30_000,
  });
}

export function useCreateSavedSearch() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      name: string;
      offer_key?: string | null;
      filters: SavedSearchFilters;
      schedule?: string;
      notification_policy?: Record<string, unknown>;
    }) => prospectingAutomationApi.createSavedSearch(body),
    onSuccess: async () => client.invalidateQueries({ queryKey: keys.savedSearches }),
  });
}

export function useRunSavedSearch() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => prospectingAutomationApi.runSavedSearch(id),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: keys.savedSearches }),
        client.invalidateQueries({ queryKey: keys.alerts }),
      ]);
    },
  });
}

export function useToggleSavedSearch() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      prospectingAutomationApi.patchSavedSearch(id, { enabled }),
    onSuccess: async () => client.invalidateQueries({ queryKey: keys.savedSearches }),
  });
}

export function useAlerts(status?: ProspectingAlert['status']) {
  return useQuery({
    queryKey: [...keys.alerts, status ?? 'all'],
    queryFn: () => prospectingAutomationApi.alerts(status),
    staleTime: 20_000,
  });
}

export function usePatchAlert() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: ProspectingAlert['status'] }) =>
      prospectingAutomationApi.patchAlert(id, status),
    onSuccess: async () => client.invalidateQueries({ queryKey: keys.alerts }),
  });
}

export function useEventSeries() {
  return useQuery({ queryKey: keys.eventSeries, queryFn: prospectingAutomationApi.eventSeries, staleTime: 60_000 });
}

export function useRefreshEventSeries() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: prospectingAutomationApi.refreshEventSeries,
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: keys.eventSeries }),
        client.invalidateQueries({ queryKey: keys.alerts }),
      ]);
    },
  });
}

export function useAgentStates() {
  return useQuery({ queryKey: keys.agentStates, queryFn: () => prospectingAutomationApi.agentStates(), staleTime: 30_000 });
}

export function useRefreshAgentStates() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: prospectingAutomationApi.refreshAgentStates,
    onSuccess: async () => client.invalidateQueries({ queryKey: keys.agentStates }),
  });
}

export function useRunContinuousWatch() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: prospectingAutomationApi.runWatch,
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: keys.alerts }),
        client.invalidateQueries({ queryKey: keys.agentStates }),
        client.invalidateQueries({ queryKey: ['data-health'] }),
      ]);
    },
  });
}
