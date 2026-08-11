import { create } from 'zustand';
import { Lead, Campaign, DashboardMetrics } from '@/types';

interface AppState {
  metrics: DashboardMetrics | null;
  setMetrics: (metrics: DashboardMetrics) => void;
  
  leads: Lead[];
  setLeads: (leads: Lead[]) => void;
  addLead: (lead: Lead) => void;
  updateLead: (id: string, updates: Partial<Lead>) => void;
  
  campaigns: Campaign[];
  setCampaigns: (campaigns: Campaign[]) => void;
  addCampaign: (campaign: Campaign) => void;
  updateCampaign: (id: string, updates: Partial<Campaign>) => void;
  
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  
  pipelineStage: string | null;
  setPipelineStage: (stage: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  metrics: null,
  setMetrics: (metrics) => set({ metrics }),
  
  leads: [],
  setLeads: (leads) => set({ leads }),
  addLead: (lead) => set((state) => ({ leads: [...state.leads, lead] })),
  updateLead: (id, updates) => set((state) => ({
    leads: state.leads.map((lead) =>
      lead.id === id ? { ...lead, ...updates } : lead
    ),
  })),
  
  campaigns: [],
  setCampaigns: (campaigns) => set({ campaigns }),
  addCampaign: (campaign) => set((state) => ({ campaigns: [...state.campaigns, campaign] })),
  updateCampaign: (id, updates) => set((state) => ({
    campaigns: state.campaigns.map((campaign) =>
      campaign.id === id ? { ...campaign, ...updates } : campaign
    ),
  })),
  
  // Item 4.17 (auditoria mobile): a sidebar nasce FECHADA em telas < lg
  // (off-canvas) e ABERTA no desktop — evita o menu cobrindo o conteúdo no
  // primeiro acesso mobile. O usuário alterna pelo hambúrguer.
  sidebarOpen: typeof window === 'undefined' || window.innerWidth >= 1024,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  
  pipelineStage: null,
  setPipelineStage: (stage) => set({ pipelineStage: stage }),
}));