'use client';

import { useMutation } from '@tanstack/react-query';
import { searchApi, type CompanySearchFilters, type PeopleSearchFilters, type SearchTarget } from '@/lib/search-api';

export function useCompanySearch() {
  return useMutation({ mutationFn: (filters: CompanySearchFilters) => searchApi.companies(filters) });
}

export function usePeopleSearch() {
  return useMutation({ mutationFn: (filters: PeopleSearchFilters) => searchApi.people(filters) });
}

export function useInterpretSearch() {
  return useMutation({
    mutationFn: ({ query, target }: { query: string; target?: SearchTarget | 'auto' }) =>
      searchApi.interpret(query, target ?? 'auto'),
  });
}
