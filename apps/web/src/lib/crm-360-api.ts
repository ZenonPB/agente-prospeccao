import { request } from '@/lib/api';
import type { Company360, Person360 } from '@/types/crm-360';

export type Company360Patch = {
  expected_updated_at: string;
  company_name?: string | null;
  name?: string | null;
  website?: string | null;
  phone?: string | null;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  category?: string | null;
  company_linkedin_url?: string | null;
  instagram_url?: string | null;
};

export type Person360Patch = {
  expected_updated_at: string;
  name?: string | null;
  role?: string | null;
  role_label?: string | null;
  email?: string | null;
  phone?: string | null;
  linkedin_url?: string | null;
  verification_status?: string | null;
  routability_type?: string | null;
  routable?: boolean;
  routability_reason?: string | null;
};

export const crm360Api = {
  company: (companyId: string) => request<Company360>(`/api/companies/${companyId}/360`),
  updateCompany: (companyId: string, body: Company360Patch) => request<Company360>(`/api/companies/${companyId}/360`, { method: 'PATCH', body: JSON.stringify(body) }),
  person: (personId: string) => request<Person360>(`/api/people/${personId}/360`),
  updatePerson: (personId: string, body: Person360Patch) => request<Person360>(`/api/people/${personId}/360`, { method: 'PATCH', body: JSON.stringify(body) }),
  verifyPerson: (personId: string, expectedUpdatedAt: string) => request<Person360>(`/api/people/${personId}/verify`, { method: 'POST', body: JSON.stringify({ expected_updated_at: expectedUpdatedAt }) }),
};
