'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { dataIntelligenceApi } from '@/lib/data-intelligence-api';

export function useDataHealth(limit = 100) {
  return useQuery({
    queryKey: ['data-health', limit],
    queryFn: () => dataIntelligenceApi.health(limit),
    staleTime: 60_000,
  });
}

export function useRefreshPlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ limit, enqueue }: { limit?: number; enqueue?: boolean }) =>
      dataIntelligenceApi.refreshPlan(limit ?? 25, enqueue ?? false),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['data-health'] });
    },
  });
}
