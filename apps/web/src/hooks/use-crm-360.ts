'use client';

import { useQuery } from '@tanstack/react-query';
import { crm360Api } from '@/lib/crm-360-api';

export function useCompany360(companyId: string) {
  return useQuery({
    queryKey: ['crm-360', 'company', companyId],
    queryFn: () => crm360Api.company(companyId),
    enabled: Boolean(companyId),
    staleTime: 30_000,
  });
}

export function usePerson360(personId: string) {
  return useQuery({
    queryKey: ['crm-360', 'person', personId],
    queryFn: () => crm360Api.person(personId),
    enabled: Boolean(personId),
    staleTime: 30_000,
  });
}
