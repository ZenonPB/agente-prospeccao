import { request } from '@/lib/api';

export type ProviderDiagnosticStatus =
  | 'ok'
  | 'invalid_key'
  | 'quota_limited'
  | 'unavailable'
  | 'rejected'
  | 'timeout'
  | 'unreachable'
  | 'not_configured';

export interface ProviderDiagnosticItem {
  provider: 'google' | 'groq' | 'hunter';
  label: string;
  key_source: 'workspace' | 'shared';
  status: ProviderDiagnosticStatus;
}

export interface ProviderDiagnosticsResponse {
  tested_at: string;
  ready_for_basic_prospecting: boolean;
  providers: ProviderDiagnosticItem[];
}

export const providerDiagnosticsApi = {
  test: (organizationId: string) =>
    request<ProviderDiagnosticsResponse>(`/api/orgs/${organizationId}/provider-diagnostics`, {
      method: 'POST',
      body: JSON.stringify({ providers: ['google', 'groq', 'hunter'] }),
    }),
};
