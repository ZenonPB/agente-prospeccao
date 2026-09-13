import { request } from '@/lib/api';
import type { Company360, Person360 } from '@/types/crm-360';

export const crm360Api = {
  company: (companyId: string) => request<Company360>(`/api/companies/${companyId}/360`),
  person: (personId: string) => request<Person360>(`/api/people/${personId}/360`),
};
