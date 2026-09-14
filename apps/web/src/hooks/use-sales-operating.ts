'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { salesOperatingApi } from '@/lib/sales-operating-api';

export const salesOperatingKeys = {
  all: ['sales-operating'] as const,
  queue: (limit: number) => ['sales-operating', 'queue', limit] as const,
  search: (q: string) => ['sales-operating', 'search', q] as const,
  savedViews: (kind: 'crm' | 'analytics') => ['sales-operating', 'saved-views', kind] as const,
};

export function useOperatingQueue(limit = 20) {
  return useQuery({
    queryKey: salesOperatingKeys.queue(limit),
    queryFn: () => salesOperatingApi.queue(limit),
    staleTime: 30_000,
  });
}

export function useOperatingSearch(q: string) {
  const cleaned = q.trim();
  return useQuery({
    queryKey: salesOperatingKeys.search(cleaned),
    queryFn: () => salesOperatingApi.search(cleaned),
    enabled: cleaned.length >= 2,
    staleTime: 30_000,
  });
}

export function useSavedCommercialViews(kind: 'crm' | 'analytics') {
  return useQuery({
    queryKey: salesOperatingKeys.savedViews(kind),
    queryFn: () => salesOperatingApi.savedViews(kind),
    staleTime: 60_000,
  });
}

export function useCreateSavedCommercialView(kind: 'crm' | 'analytics') {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: salesOperatingApi.createSavedView,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: salesOperatingKeys.savedViews(kind) }),
  });
}

export function useDeleteSavedCommercialView(kind: 'crm' | 'analytics') {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: salesOperatingApi.deleteSavedView,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: salesOperatingKeys.savedViews(kind) }),
  });
}
