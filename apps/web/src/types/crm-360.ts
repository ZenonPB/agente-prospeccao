export type Crm360TimelineItem = {
  type: 'ACTIVITY' | 'TASK' | 'OUTCOME';
  occurred_at: string | null;
  actor: string | null;
  title: string;
  description: string | null;
  source_entity: string;
  metadata: Record<string, unknown>;
};

export type Crm360Company = {
  id: string;
  company_name: string;
  name: string | null;
  cnpj: string | null;
  website: string | null;
  domain: string | null;
  phone: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  category: string | null;
  google_rating: number | null;
  google_rating_count: number | null;
  google_maps_uri: string | null;
  linkedin_url: string | null;
  instagram_url: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type Crm360Person = {
  id: string;
  company_id: string | null;
  name: string;
  role: string | null;
  role_label: string | null;
  email: string | null;
  phone: string | null;
  email_verified: boolean;
  linkedin_url: string | null;
  identity_confidence: number;
  contact_confidence: number;
  source_reliability: number;
  verification_status: string;
  last_verified_at: string | null;
  routability_type: string;
  routable: boolean;
  routability_reason: string | null;
  source: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type Crm360Lead = {
  id: string;
  company_id: string | null;
  primary_person_id: string | null;
  campaign_id: string | null;
  company_name: string;
  status: string | null;
  priority: string | null;
  qualification_score: number | null;
  value: number | null;
  expected_close_date: string | null;
  assigned_to_id: string | null;
  next_action_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type Crm360Opportunity = {
  id: string;
  lead_id: string;
  offer_key: string;
  offer_version: string | null;
  score: number;
  signals_matched: string[];
  created_at: string | null;
  updated_at: string | null;
};

export type Crm360Task = {
  id: string;
  lead_id: string;
  owner_user_id: string | null;
  task_type: string;
  title: string;
  description: string | null;
  due_at: string | null;
  status: string;
  source: string;
  created_at: string | null;
  completed_at: string | null;
};

export type Crm360Outcome = {
  id: string;
  lead_id: string;
  lead_opportunity_id: string | null;
  offer_key: string;
  offer_version: string | null;
  outcome: string;
  value: number;
  recorded_at: string | null;
};

export type Company360 = {
  company: Crm360Company;
  summary: {
    lead_count: number;
    person_count: number;
    opportunity_count: number;
    open_task_count: number;
    won_value: number;
    best_opportunity_score: number | null;
  };
  persons: Crm360Person[];
  leads: Crm360Lead[];
  opportunities: Crm360Opportunity[];
  tasks: Crm360Task[];
  outcomes: Crm360Outcome[];
  aliases: Array<{ kind: string; value: string; source: string | null; created_at: string | null }>;
  timeline: Crm360TimelineItem[];
  capabilities: { read_only: true; canonical_company: true };
};

export type Person360 = {
  person: Crm360Person;
  company: Crm360Company | null;
  summary: {
    primary_on_lead_count: number;
    related_lead_count: number;
    opportunity_count: number;
    open_task_count: number;
    best_opportunity_score: number | null;
  };
  leads: Crm360Lead[];
  opportunities: Crm360Opportunity[];
  tasks: Crm360Task[];
  outcomes: Crm360Outcome[];
  timeline: Crm360TimelineItem[];
  capabilities: { read_only: true; canonical_person: true };
};
