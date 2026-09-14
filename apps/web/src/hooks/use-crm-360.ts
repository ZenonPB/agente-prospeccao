'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { crm360Api, type Company360Patch, type Person360Patch } from '@/lib/crm-360-api';

export function useCompany360(companyId: string) {
  return useQuery({
    queryKey: ['crm-360', 'company', companyId],
    queryFn: () => crm360Api.company(companyId),
    enabled: Boolean(companyId),
    staleTime: 30_000,
  });
}

export function useUpdateCompany360(companyId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Company360Patch) => crm360Api.updateCompany(companyId, body),
    onSuccess: (data) => client.setQueryData(['crm-360', 'company', companyId], data),
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

export function useUpdatePerson360(personId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Person360Patch) => crm360Api.updatePerson(personId, body),
    onSuccess: (data) => {
      client.setQueryData(['crm-360', 'person', personId], data);
      if (data.company?.id) void client.invalidateQueries({ queryKey: ['crm-360', 'company', data.company.id] });
    },
  });
}

export function useVerifyPerson360(personId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (expectedUpdatedAt: string) => crm360Api.verifyPerson(personId, expectedUpdatedAt),
    onSuccess: (data) => {
      client.setQueryData(['crm-360', 'person', personId], data);
      if (data.company?.id) void client.invalidateQueries({ queryKey: ['crm-360', 'company', data.company.id] });
    },
  });
}
