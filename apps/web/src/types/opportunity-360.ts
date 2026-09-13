export type Opportunity360Actor = {
  id: string;
  name: string | null;
};

export type Opportunity360TimelineItem = {
  type: 'ACTIVITY' | 'TASK' | 'FEEDBACK' | 'OUTCOME' | 'SEQUENCE' | 'WORKFLOW' | 'NEXT_ACTION';
  occurred_at: string | null;
  actor: Opportunity360Actor | null;
  title: string;
  description: string | null;
  source_entity: string;
  metadata: Record<string, unknown>;
};

export type Opportunity360Task = {
  id: string;
  task_type: string;
  title: string;
  description: string | null;
  status: string;
  source: string;
  due_at: string | null;
  completed_at: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  owner?: Opportunity360Actor | null;
  owner_user_id?: string | null;
};

export type Opportunity360Patch = {
  owner_user_id?: string | null;
  status?: string | null;
  negotiation_stage?: string | null;
  value?: number | null;
  expected_close_date?: string | null;
  next_action_at?: string | null;
  lost_reason?: string | null;
  notes?: string | null;
};

export type OpportunityTaskCreate = {
  client_request_id: string;
  title: string;
  description?: string | null;
  task_type?: string;
  due_at?: string | null;
  owner_user_id?: string | null;
};

export type OpportunityTaskPatch = {
  title?: string;
  description?: string | null;
  due_at?: string | null;
  owner_user_id?: string | null;
  status?: 'OPEN' | 'COMPLETED' | 'DISMISSED';
};

export type Opportunity360CommandResult = {
  opportunity_id: string;
  lead_id: string;
  changed: Record<string, unknown>;
  commercial: {
    owner_user_id: string | null;
    status: string | null;
    negotiation_stage: string | null;
    value: number | null;
    expected_close_date: string | null;
    next_action_at: string | null;
    lost_reason: string | null;
    notes: string | null;
  };
};

export type Opportunity360Payload = {
  opportunity: {
    id: string;
    lead_id: string;
    offer_key: string;
    offer_version: string | null;
    profile_key: string | null;
    score: number;
    resolved_from: string | null;
    signals_matched: string[];
    signals_missing: string[];
    evidence: unknown[];
    score_breakdown: Record<string, number | string>;
    created_at: string | null;
    updated_at: string | null;
  };
  lead: {
    id: string;
    company_name: string;
    category: string | null;
    city: string | null;
    state: string | null;
    country: string | null;
    website: string | null;
    cnpj: string | null;
    qualification_score: number | null;
    qualification_reason: string | null;
    priority: string | null;
    primary_need: string | null;
    notes: string | null;
    next_action_at: string | null;
    last_contacted_at: string | null;
    campaign_id: string | null;
    created_at: string | null;
    updated_at: string | null;
  };
  company: {
    id: string | null;
    name: string;
    cnpj: string | null;
    domain: string | null;
    website: string | null;
    city: string | null;
    state: string | null;
    country: string | null;
    industry: string | null;
    source: string | null;
  };
  decision_maker: {
    person_id?: string | null;
    contact_id?: string | null;
    name: string | null;
    title: string | null;
    seniority: string | null;
    department: string | null;
    buyer_role: string | null;
    email: string | null;
    phone: string | null;
    linkedin_url: string | null;
    identity_confidence: number | null;
    contact_confidence: number | null;
  } | null;
  contacts: Array<{
    id: string;
    name: string | null;
    role: string | null;
    role_label: string | null;
    email: string | null;
    email_verified: boolean;
    phone: string | null;
    linkedin_url: string | null;
    is_primary: boolean;
    identity_confidence: number | null;
    contact_confidence: number | null;
    verification_status: string | null;
    routability_type: string | null;
    routable: boolean;
    source: string | null;
  }>;
  qualification: Record<string, number | null>;
  enrichment: {
    website_exists: boolean | null;
    responsive_design: boolean | null;
    cms: string | null;
    lighthouse_score: number | null;
    load_time_ms: number | null;
    created_at: string | null;
  } | null;
  commercial: {
    status: string | null;
    negotiation_stage: string | null;
    contract_outcome: string | null;
    value: number | null;
    expected_close_date: string | null;
    outcome_date: string | null;
    lost_reason: string | null;
  };
  owner: (Opportunity360Actor & { email: string | null; assigned_at: string | null }) | null;
  next_action: {
    id: string | null;
    action: string;
    why: string;
    confidence: number | null;
    evidence: unknown[];
    deadline: string | null;
    status: string;
    offer_key: string | null;
    created_at: string | null;
  } | null;
  tasks: Opportunity360Task[];
  activities: Array<{
    id: string;
    action: string;
    actor: Opportunity360Actor | null;
    status_from: string | null;
    status_to: string | null;
    detail: string | null;
    created_at: string | null;
  }>;
  usefulness_feedback: Array<{
    id: string;
    useful: boolean;
    reason: string | null;
    detail: string | null;
    actor: Opportunity360Actor | null;
    created_at: string | null;
    updated_at: string | null;
  }>;
  outcomes: Array<{
    id: string;
    outcome: string;
    value: number;
    provider: string | null;
    event_key: string;
    outreach_at: string | null;
    recorded_at: string | null;
  }>;
  engagement: {
    enrollments: unknown[];
    executions: unknown[];
    workflow_runs: unknown[];
  };
  timeline: Opportunity360TimelineItem[];
  capabilities: {
    proposal_entity: boolean;
    contract_entity: boolean;
    notes_entity: boolean;
    read_only: boolean;
    can_edit?: boolean;
    can_manage_owners?: boolean;
  };
};
