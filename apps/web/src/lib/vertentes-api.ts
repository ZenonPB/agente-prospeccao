'use client';

import { request } from '@/lib/api';

export type VertenteSignal = {
  key: string;
  label: string;
  description: string;
  weight?: number | null;
};

export type VertenteMaturity = {
  score: number;
  level: 'madura' | 'em_evolucao' | 'incompleta';
  missing: string[];
  checks: Array<{ key: string; label: string; passed: boolean; detail?: string }>;
};

export type Vertente = {
  key: string;
  name: string;
  tagline: string;
  version: string;
  origin: 'factory' | 'organization';
  vertical: string;
  archetype: string;
  analysis_profile: 'web_presence' | 'business_opportunity';
  maturity: VertenteMaturity;
  capabilities: {
    company_discovery: boolean;
    event_discovery: boolean;
    website_analysis: boolean;
    people_discovery: boolean;
    intent_detection: boolean;
  };
  simple: {
    segments: string[];
    company_sizes: string[];
    exclusions: string[];
    discovery_sources: string[];
    positive_signals: VertenteSignal[];
    negative_signals: VertenteSignal[];
    decision_makers: string[];
    channels: string[];
    qualification_questions: string[];
    analysis_flow: string[];
  };
  advanced: Record<string, unknown>;
};

export const vertentesApi = {
  list: () => request<{ items: Vertente[]; total: number }>('/api/vertentes'),
  get: (key: string) => request<Vertente>(`/api/vertentes/${encodeURIComponent(key)}`),
};
