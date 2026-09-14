'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { commercialPlatformApi, type CRMProvider, type CRMSyncMode } from '@/lib/commercial-platform-api';

const keys = {
  connections: ['commercial-platform', 'connections'] as const,
  runs: ['commercial-platform', 'sync-runs'] as const,
  certifications: ['commercial-platform', 'crm-certifications'] as const,
  intelligence: ['commercial-platform', 'intelligence'] as const,
  calibration: ['commercial-platform', 'calibration'] as const,
  coaching: ['commercial-platform', 'coaching'] as const,
  proposals: ['commercial-platform', 'learning-proposals'] as const,
  versions: ['commercial-platform', 'offer-profile-versions'] as const,
};

export function useCRMConnections() { return useQuery({ queryKey: keys.connections, queryFn: commercialPlatformApi.connections, staleTime: 30_000 }); }
export function useSaveCRMConnection() { const client = useQueryClient(); return useMutation({ mutationFn: (body: { provider: CRMProvider; sync_mode: CRMSyncMode; token?: string; base_url?: string; enabled: boolean }) => commercialPlatformApi.saveConnection(body), onSuccess: async () => client.invalidateQueries({ queryKey: keys.connections }) }); }
export function useCRMHealth() { const client = useQueryClient(); return useMutation({ mutationFn: commercialPlatformApi.health, onSuccess: async () => client.invalidateQueries({ queryKey: keys.connections }) }); }
export function useCRMCertifications() { return useQuery({ queryKey: keys.certifications, queryFn: commercialPlatformApi.certifications, staleTime: 15_000 }); }
export function useCertifyCRMConnection() { const client = useQueryClient(); return useMutation({ mutationFn: commercialPlatformApi.certify, onSuccess: async () => Promise.all([client.invalidateQueries({ queryKey: keys.connections }), client.invalidateQueries({ queryKey: keys.certifications })]) }); }
export function usePullCRMChanges() { const client = useQueryClient(); return useMutation({ mutationFn: commercialPlatformApi.pull, onSuccess: async () => Promise.all([client.invalidateQueries({ queryKey: keys.connections }), client.invalidateQueries({ queryKey: keys.runs }), client.invalidateQueries({ queryKey: keys.intelligence })]) }); }
export function useCRMSyncRuns() { return useQuery({ queryKey: keys.runs, queryFn: commercialPlatformApi.syncRuns, staleTime: 15_000 }); }
export function useCommercialIntelligence() { return useQuery({ queryKey: keys.intelligence, queryFn: commercialPlatformApi.intelligence, staleTime: 60_000 }); }

export function useCalibrationOverview() { return useQuery({ queryKey: keys.calibration, queryFn: () => commercialPlatformApi.calibrationOverview(20), staleTime: 30_000 }); }
export function useCommercialCoaching() { return useQuery({ queryKey: keys.coaching, queryFn: commercialPlatformApi.coaching, staleTime: 30_000 }); }
export function useLearningProposals() { return useQuery({ queryKey: keys.proposals, queryFn: commercialPlatformApi.learningProposals, staleTime: 15_000 }); }
export function useOfferProfileVersions() { return useQuery({ queryKey: keys.versions, queryFn: commercialPlatformApi.offerProfileVersions, staleTime: 15_000 }); }

function useRefreshLearningState() {
  const client = useQueryClient();
  return async () => Promise.all([
    client.invalidateQueries({ queryKey: keys.calibration }),
    client.invalidateQueries({ queryKey: keys.proposals }),
    client.invalidateQueries({ queryKey: keys.versions }),
    client.invalidateQueries({ queryKey: keys.intelligence }),
  ]);
}

export function useCreateCalibrationComparison() {
  const refresh = useRefreshLearningState();
  return useMutation({ mutationFn: commercialPlatformApi.createCalibrationComparison, onSuccess: refresh });
}

export function useApproveCalibrationComparison() {
  const refresh = useRefreshLearningState();
  return useMutation({
    mutationFn: ({ comparisonId, approvedVersion, evidence }: { comparisonId: string; approvedVersion: string; evidence: string }) => commercialPlatformApi.approveComparison(comparisonId, { approved_version: approvedVersion, evidence }),
    onSuccess: refresh,
  });
}

export function usePublishLearningProposal() {
  const refresh = useRefreshLearningState();
  return useMutation({ mutationFn: commercialPlatformApi.publishLearningProposal, onSuccess: refresh });
}

export function useRollbackOfferProfile() {
  const refresh = useRefreshLearningState();
  return useMutation({ mutationFn: ({ offerKey, targetVersion }: { offerKey: string; targetVersion: string }) => commercialPlatformApi.rollbackOfferProfile(offerKey, targetVersion), onSuccess: refresh });
}
