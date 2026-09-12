import { request } from '@/lib/api';

export type SequenceStepType = 'EMAIL' | 'CALL' | 'LINKEDIN' | 'WHATSAPP' | 'RESEARCH' | 'WAIT' | 'CONDITION';

export interface SequenceStep {
  type: SequenceStepType;
  delay_minutes: number;
  title?: string;
  description?: string;
  subject?: string;
  content?: string;
  config?: Record<string, unknown>;
}

export interface SequenceTemplate {
  id: string;
  name: string;
  description?: string | null;
  offer_key?: string | null;
  persona_key?: string | null;
  version: number;
  steps: SequenceStep[];
  enabled: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SequenceEnrollment {
  id: string;
  sequence_id: string;
  lead_id: string;
  person_id?: string | null;
  status: string;
  current_step_index: number;
  pause_reason?: string | null;
  next_action_at?: string | null;
  last_action_at?: string | null;
  created_at?: string | null;
}

export interface CommercialTask {
  id: string;
  lead_id: string;
  person_id?: string | null;
  enrollment_id?: string | null;
  owner_user_id?: string | null;
  task_type: string;
  title: string;
  description?: string | null;
  due_at?: string | null;
  status: string;
  source: string;
  metadata: Record<string, unknown>;
  completed_at?: string | null;
}

export interface WorkflowDefinition {
  id: string;
  name: string;
  description?: string | null;
  trigger_type: string;
  conditions: Array<{ field: string; operator: string; value?: unknown }>;
  actions: Array<{ type: string; config: Record<string, unknown> }>;
  version: number;
  enabled: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface WorkflowRun {
  id: string;
  workflow_id: string;
  trigger_type: string;
  event_key: string;
  entity_type?: string | null;
  entity_id?: string | null;
  status: string;
  action_results: Array<Record<string, unknown>>;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export const engagementApi = {
  sequences: () => request<{ items: SequenceTemplate[] }>('/api/engagement/sequences'),
  createSequence: (body: {
    name: string;
    description?: string;
    offer_key?: string | null;
    persona_key?: string | null;
    steps: SequenceStep[];
  }) => request<SequenceTemplate>('/api/engagement/sequences', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  enrollments: () => request<{ items: SequenceEnrollment[] }>('/api/engagement/enrollments'),
  processDue: () => request<{ processed: number; tasks_created: number; completed: number; stopped: number }>('/api/engagement/sequences/process-due', { method: 'POST' }),
  tasks: () => request<{ items: CommercialTask[] }>('/api/engagement/tasks'),
  patchTask: (id: string, status: 'OPEN' | 'COMPLETED' | 'DISMISSED') => request<CommercialTask>(`/api/engagement/tasks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  }),
  workflows: () => request<{ items: WorkflowDefinition[]; triggers: string[] }>('/api/engagement/workflows'),
  createWorkflow: (body: {
    name: string;
    description?: string;
    trigger_type: string;
    conditions: Array<{ field: string; operator: string; value?: unknown }>;
    actions: Array<{ type: string; config: Record<string, unknown> }>;
  }) => request<WorkflowDefinition>('/api/engagement/workflows', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  workflowRuns: () => request<{ items: WorkflowRun[] }>('/api/engagement/workflow-runs'),
  disableWorkflow: (id: string) => request<void>(`/api/engagement/workflows/${id}`, { method: 'DELETE' }),
};
