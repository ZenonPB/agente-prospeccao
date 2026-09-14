'use client';

import { useQuery } from '@tanstack/react-query';
import { vertentesApi } from '@/lib/vertentes-api';

export function useVertentes() {
  return useQuery({
    queryKey: ['vertentes'],
    queryFn: vertentesApi.list,
  });
}

export function useVertente(key?: string | null) {
  return useQuery({
    queryKey: ['vertentes', key],
    queryFn: () => vertentesApi.get(key as string),
    enabled: Boolean(key),
  });
}
