'use client';

import { useQuery } from '@tanstack/react-query';

import { request } from '@/lib/api';
import type { Opportunity360Payload } from '@/types/opportunity-360';

export function useOpportunity360(opportunityId: string) {
  return useQuery({
    queryKey: ['opportunities', opportunityId, '360'],
    queryFn: () => request<Opportunity360Payload>(`/api/opportunities/${opportunityId}/360`),
    enabled: Boolean(opportunityId),
    staleTime: 30_000,
  });
}
