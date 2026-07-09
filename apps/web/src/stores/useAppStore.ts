import { create } from 'zustand';
import { Lead, Campaign, DashboardMetrics } from '@/types';

interface AppState {
  // Dashboard
  metrics: DashboardMetrics | null;
  setMetrics: (metrics: DashboardMetrics) => void;
  
  // Leads
  leads: Lead[];
  setLeads: (leads: Lead[]) => void;
  addLead: (lead: Lead) => void;
  updateLead: (id: string, updates: Partial<Lead>) => void;
  
  // Campaigns
  campaigns: Campaign[];
  setCampaigns: (campaigns: Campaign[]) => void;
  addCampaign: (campaign: Campaign) => void;
  updateCampaign: (id: string, updates: Partial<Campaign>) => void;
  
  // UI State
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  
  // Pipeline
  pipelineStage: string | null;
  setPipelineStage: (stage: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Dashboard
  metrics: null,
  setMetrics: (metrics) => set({ metrics }),
  
  // Leads
  leads: [],
  setLeads: (leads) => set({ leads }),
  addLead: (lead) => set((state) => ({ leads: [...state.leads, lead] })),
  updateLead: (id, updates) => set((state) => ({
    leads: state.leads.map((lead) =>
      lead.id === id ? { ...lead, ...updates } : lead
    ),
  })),
  
  // Campaigns
  campaigns: [],
  setCampaigns: (campaigns) => set({ campaigns }),
  addCampaign: (campaign) => set((state) => ({ campaigns: [...state.campaigns, campaign] })),
  updateCampaign: (id, updates) => set((state) => ({
    campaigns: state.campaigns.map((campaign) =>
      campaign.id === id ? { ...campaign, ...updates } : campaign
    ),
  })),
  
  // UI State
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  
  // Pipeline
  pipelineStage: null,
  setPipelineStage: (stage) => set({ pipelineStage: stage }),
}));