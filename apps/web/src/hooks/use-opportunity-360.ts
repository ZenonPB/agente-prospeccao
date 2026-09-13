'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { request } from '@/lib/api';
import type {
  Opportunity360CommandResult,
  Opportunity360Payload,
  Opportunity360Patch,
  Opportunity360Task,
  OpportunityTaskCreate,
  OpportunityTaskPatch,
} from '@/types/opportunity-360';

const opportunityKey = (opportunityId: string) => ['opportunities', opportunityId, '360'] as const;

export function useOpportunity360(opportunityId: string) {
  return useQuery({
    queryKey: opportunityKey(opportunityId),
    queryFn: () => request<Opportunity360Payload>(`/api/opportunities/${opportunityId}/360`),
    enabled: Boolean(opportunityId),
    staleTime: 30_000,
  });
}

export function useUpdateOpportunity360(opportunityId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Opportunity360Patch) =>
      request<Opportunity360CommandResult>(`/api/opportunities/${opportunityId}/360`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: opportunityKey(opportunityId) }),
        queryClient.invalidateQueries({ queryKey: ['leads'] }),
        queryClient.invalidateQueries({ queryKey: ['opportunities'] }),
      ]);
    },
  });
}

export function useCreateOpportunityTask(opportunityId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: OpportunityTaskCreate) =>
      request<Opportunity360Task & { created: boolean }>(`/api/opportunities/${opportunityId}/tasks`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: opportunityKey(opportunityId) });
    },
  });
}

export function useUpdateOpportunityTask(opportunityId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, payload }: { taskId: string; payload: OpportunityTaskPatch }) =>
      request<Opportunity360Task>(`/api/opportunities/${opportunityId}/tasks/${taskId}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      }),
    onMutate: async ({ taskId, payload }) => {
      await queryClient.cancelQueries({ queryKey: opportunityKey(opportunityId) });
      const previous = queryClient.getQueryData<Opportunity360Payload>(opportunityKey(opportunityId));
      if (previous) {
        queryClient.setQueryData<Opportunity360Payload>(opportunityKey(opportunityId), {
          ...previous,
          tasks: previous.tasks.map((task) =>
            task.id === taskId ? { ...task, ...payload } : task,
          ),
        });
      }
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(opportunityKey(opportunityId), context.previous);
      }
    },
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: opportunityKey(opportunityId) });
    },
  });
}
