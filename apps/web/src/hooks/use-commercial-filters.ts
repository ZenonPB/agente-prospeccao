'use client';

import { useCallback, useMemo } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import type {
  CommercialFilterKey,
  CommercialFilterArrayKey,
  CommercialFilterSnapshot,
  CommercialFilterValue,
} from '@/lib/api';

const ARRAY_KEYS = new Set<CommercialFilterKey>([
  'channel',
  'status',
  'score_bucket',
  'outcome',
]);

const URL_KEYS: ReadonlyArray<{ key: CommercialFilterKey; query: string }> = [
  { key: 'campaign_id', query: 'campaign' },
  { key: 'consultant_id', query: 'consultant' },
  { key: 'offer_key', query: 'offer' },
  { key: 'offer_version', query: 'offer_version' },
  { key: 'channel', query: 'channel' },
  { key: 'status', query: 'status' },
  { key: 'score_bucket', query: 'score_bucket' },
  { key: 'outcome', query: 'outcome' },
  { key: 'attribution', query: 'attribution' },
  { key: 'search', query: 'search' },
  { key: 'cursor', query: 'cursor' },
];

function cleanText(value: string | null | undefined): string | undefined {
  const cleaned = value?.trim();
  return cleaned || undefined;
}

function readArray(searchParams: URLSearchParams, query: string): string[] | undefined {
  const values = searchParams
    .getAll(query)
    .flatMap((value) => value.split(','))
    .map((value) => value.trim())
    .filter(Boolean);
  return values.length > 0 ? [...new Set(values)].sort() : undefined;
}

function readPeriod(searchParams: URLSearchParams): Pick<CommercialFilterSnapshot, 'from' | 'to'> {
  const encoded = searchParams.get('period');
  if (encoded) {
    const separator = encoded.includes('..') ? '..' : ',';
    const [from, to] = encoded.split(separator, 2);
    return { from: cleanText(from), to: cleanText(to) };
  }
  return {
    from: cleanText(searchParams.get('from')),
    to: cleanText(searchParams.get('to')),
  };
}

function snapshotFromUrl(searchParams: URLSearchParams): CommercialFilterSnapshot {
  const period = readPeriod(searchParams);
  const snapshot: CommercialFilterSnapshot = {
    from: period.from,
    to: period.to,
  };

  for (const { key, query } of URL_KEYS) {
    if (ARRAY_KEYS.has(key)) {
      const arrayKey = key as CommercialFilterArrayKey;
      snapshot[arrayKey] = readArray(searchParams, query);
    } else if (key === 'attribution') {
      const value = cleanText(searchParams.get(query));
      snapshot.attribution = value === 'attributed' || value === 'unattributed' ? value : undefined;
    } else {
      const scalarKey = key as Exclude<CommercialFilterKey, CommercialFilterArrayKey | 'attribution'>;
      snapshot[scalarKey] = cleanText(searchParams.get(query));
    }
  }

  return normalizeCommercialFilters(snapshot);
}

export function normalizeCommercialFilters(
  input: CommercialFilterSnapshot,
): CommercialFilterSnapshot {
  const normalized: CommercialFilterSnapshot = {};
  const scalarKeys: ReadonlyArray<Exclude<CommercialFilterKey, CommercialFilterArrayKey | 'attribution'>> = [
    'from',
    'to',
    'campaign_id',
    'consultant_id',
    'offer_key',
    'offer_version',
    'search',
    'cursor',
  ];

  for (const key of scalarKeys) {
    const value = input[key];
    if (value) normalized[key] = value.trim();
  }
  if (input.attribution === 'attributed' || input.attribution === 'unattributed') {
    normalized.attribution = input.attribution;
  }
  for (const key of ['channel', 'status', 'score_bucket', 'outcome'] as const) {
    const values = input[key];
    if (values && values.length > 0) {
      normalized[key] = [...new Set(values.map((value) => value.trim()).filter(Boolean))].sort();
    }
  }
  return normalized;
}

function serializeUrlValue(value: CommercialFilterValue): string | undefined {
  if (Array.isArray(value)) return value.length > 0 ? [...value].sort().join(',') : undefined;
  return value?.trim() || undefined;
}

export function useCommercialFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const filters = useMemo(
    () => snapshotFromUrl(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );

  const updateFilters = useCallback(
    (patch: Partial<CommercialFilterSnapshot>) => {
      const next = normalizeCommercialFilters({ ...filters, ...patch });
      const params = new URLSearchParams(searchParams.toString());
      params.delete('period');
      params.delete('from');
      params.delete('to');
      for (const { query } of URL_KEYS) params.delete(query);

      if (next.from || next.to) {
        params.set('period', `${next.from ?? ''},${next.to ?? ''}`);
      }
      for (const { key, query } of URL_KEYS) {
        const value = serializeUrlValue(next[key]);
        if (value) params.set(query, value);
      }

      const query = params.toString();
      router.replace(`${pathname}${query ? `?${query}` : ''}`, { scroll: false });
    },
    [filters, pathname, router, searchParams],
  );

  const setFilter = useCallback(
    <K extends CommercialFilterKey>(key: K, value: CommercialFilterSnapshot[K]) => {
      updateFilters({ [key]: value } as Partial<CommercialFilterSnapshot>);
    },
    [updateFilters],
  );

  const clearFilters = useCallback(() => {
    updateFilters({
      from: undefined,
      to: undefined,
      campaign_id: undefined,
      consultant_id: undefined,
      offer_key: undefined,
      offer_version: undefined,
      channel: undefined,
      status: undefined,
      score_bucket: undefined,
      outcome: undefined,
      attribution: undefined,
      search: undefined,
      cursor: undefined,
    });
  }, [updateFilters]);

  return {
    filters,
    normalizedFilters: filters,
    setFilter,
    updateFilters,
    clearFilters,
    hasFilters: Object.keys(filters).length > 0,
  };
}
