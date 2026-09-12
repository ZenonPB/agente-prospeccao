import { request } from '@/lib/api';

export type SearchTarget = 'companies' | 'people';
export type MatchState = 'MATCH' | 'UNKNOWN';

export interface CompanySearchFilters {
  query?: string;
  locations?: string[];
  industries?: string[];
  cnaes?: string[];
  sizes?: string[];
  employee_min?: number;
  employee_max?: number;
  revenue_min?: number;
  revenue_max?: number;
  age_min?: number;
  age_max?: number;
  technologies?: string[];
  signals?: string[];
  intent?: string[];
  keywords?: string[];
  exclusions?: string[];
  include_unknown?: boolean;
  limit?: number;
  offset?: number;
}

export interface PeopleSearchFilters {
  query?: string;
  company?: string;
  domain?: string;
  titles?: string[];
  functions?: string[];
  seniorities?: string[];
  buyer_roles?: string[];
  locations?: string[];
  email_status?: 'any' | 'present' | 'verified' | 'missing';
  phone_status?: 'any' | 'present' | 'missing';
  linkedin_status?: 'any' | 'present' | 'missing';
  min_actionable_score?: number;
  limit?: number;
  offset?: number;
}

export interface CompanySearchResult {
  id: string;
  company_name: string;
  name?: string | null;
  cnpj?: string | null;
  website?: string | null;
  normalized_domain?: string | null;
  phone?: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  location?: string | null;
  category?: string | null;
  cnae: string[];
  size: string[];
  employees?: number | null;
  revenue?: number | null;
  age?: number | null;
  technologies: string[];
  signals: string[];
  intent: string[];
  linkedin_url?: string | null;
  instagram_url?: string | null;
  google_rating?: number | null;
  google_rating_count?: number | null;
  lead_count: number;
  match_state: MatchState;
}

export interface ActionableDimension {
  score: number;
  state: 'known' | 'unknown';
  source: string;
  age_days?: number;
}

export interface ActionableContactScore {
  score: number;
  status: 'actionable' | 'review' | 'low';
  breakdown: Record<string, ActionableDimension>;
  unknown_dimensions: string[];
  coverage: number;
}

export interface PeopleSearchResult {
  id: string;
  name: string;
  role?: string | null;
  company: { id?: string | null; name?: string | null; domain?: string | null; location?: string | null };
  email?: string | null;
  email_verified: boolean;
  phone?: string | null;
  linkedin_url?: string | null;
  identity_confidence: number;
  contact_confidence: number;
  verification_status: string;
  routability_type: string;
  buyer_role: string;
  buyer_role_source: string;
  persona?: string | null;
  seniority?: string | null;
  department?: string | null;
  source?: string | null;
  actionable_contact: ActionableContactScore;
}

export interface CompanySearchResponse {
  companies: CompanySearchResult[];
  total: number;
  unknown_count: number;
  limit: number;
  offset: number;
  candidate_scan_truncated: boolean;
}

export interface PeopleSearchResponse {
  people: PeopleSearchResult[];
  total: number;
  limit: number;
  offset: number;
  candidate_scan_truncated: boolean;
}

export interface SearchIntent {
  target: SearchTarget;
  company_filters?: CompanySearchFilters | null;
  people_filters?: PeopleSearchFilters | null;
  summary: string;
  assumptions: string[];
  unresolved: string[];
}

export const searchApi = {
  companies: (filters: CompanySearchFilters) =>
    request<CompanySearchResponse>('/api/search/companies', {
      method: 'POST',
      body: JSON.stringify(filters),
    }),
  people: (filters: PeopleSearchFilters) =>
    request<PeopleSearchResponse>('/api/search/people', {
      method: 'POST',
      body: JSON.stringify(filters),
    }),
  interpret: (query: string, target: SearchTarget | 'auto' = 'auto') =>
    request<SearchIntent>('/api/search/interpret', {
      method: 'POST',
      body: JSON.stringify({ query, target }),
    }),
};
