'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { engagementApi, type SequenceStep } from '@/lib/engagement-api';

const keys = {
  sequences: ['engagement', 'sequences'] as const,
  enrollments: ['engagement', 'enrollments'] as const,
  tasks: ['engagement', 'tasks'] as const,
  workflows: ['engagement', 'workflows'] as const,
  workflowRuns: ['engagement', 'workflow-runs'] as const,
};

export function useSequences() {
  return useQuery({ queryKey: keys.sequences, queryFn: engagementApi.sequences, staleTime: 30_000 });
}

export function useCreateSequence() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string; offer_key?: string | null; persona_key?: string | null; steps: SequenceStep[] }) => engagementApi.createSequence(body),
    onSuccess: async () => client.invalidateQueries({ queryKey: keys.sequences }),
  });
}

export function useEnrollments() {
  return useQuery({ queryKey: keys.enrollments, queryFn: engagementApi.enrollments, staleTime: 20_000 });
}

export function useCommercialTasks() {
  return useQuery({ queryKey: keys.tasks, queryFn: engagementApi.tasks, staleTime: 15_000 });
}

export function usePatchCommercialTask() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'OPEN' | 'COMPLETED' | 'DISMISSED' }) => engagementApi.patchTask(id, status),
    onSuccess: async () => Promise.all([
      client.invalidateQueries({ queryKey: keys.tasks }),
      client.invalidateQueries({ queryKey: keys.enrollments }),
    ]),
  });
}

export function useProcessSequences() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: engagementApi.processDue,
    onSuccess: async () => Promise.all([
      client.invalidateQueries({ queryKey: keys.tasks }),
      client.invalidateQueries({ queryKey: keys.enrollments }),
    ]),
  });
}

export function useWorkflows() {
  return useQuery({ queryKey: keys.workflows, queryFn: engagementApi.workflows, staleTime: 30_000 });
}

export function useCreateWorkflow() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: engagementApi.createWorkflow,
    onSuccess: async () => client.invalidateQueries({ queryKey: keys.workflows }),
  });
}

export function useDisableWorkflow() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: engagementApi.disableWorkflow,
    onSuccess: async () => client.invalidateQueries({ queryKey: keys.workflows }),
  });
}

export function useWorkflowRuns() {
  return useQuery({ queryKey: keys.workflowRuns, queryFn: engagementApi.workflowRuns, staleTime: 15_000 });
}
