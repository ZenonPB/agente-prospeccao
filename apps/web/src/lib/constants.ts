/**
 * Centralized configuration objects for status, priority, and labels
 * Used across campaign, lead, and sales components
 */

// Campaign Status Configuration
export const CAMPAIGN_STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  ACTIVE: { label: 'Em andamento', color: 'bg-emerald-100 text-emerald-700' },
  PAUSED: { label: 'Pausada', color: 'bg-amber-100 text-amber-700' },
  COMPLETED: { label: 'Concluída', color: 'bg-blue-100 text-blue-700' },
  ARCHIVED: { label: 'Arquivada', color: 'bg-gray-100 text-gray-700' },
};

// Lead Status Labels
export const LEAD_STATUS_LABELS: Record<string, string> = {
  NOVO: 'Novo',
  ANALISADO: 'Analisado',
  QUALIFICADO: 'Apto',
  DESQUALIFICADO: 'Desqualificado',
  CONTATADO: 'Contatado',
  RESPONDIDO: 'Respondeu',
  REUNIAO_MARCADA: 'Reunião',
  REUNIAO_FEITA: 'Reunião realizada',
  PROPOSTA_ENVIADA: 'Proposta enviada',
  PERDIDO: 'Perdido',
};

// Lead Priority Badge Configuration
export const PRIORITY_BADGE_CONFIG: Record<string, { label: string; color: string; emoji: string }> = {
  HOT: { label: 'Quente', color: 'bg-red-100 text-red-700', emoji: '🔥' },
  WARM: { label: 'Morno', color: 'bg-amber-100 text-amber-700', emoji: '🌤️' },
  COLD: { label: 'Frio', color: 'bg-sky-100 text-sky-700', emoji: '❄️' },
};

// Primary Need Labels
export const PRIMARY_NEED_LABELS: Record<string, string> = {
  SECURITY_FIX: 'Problemas de segurança',
  MODERN_WEBSITE: 'Site desatualizado',
  PERFORMANCE: 'Site lento',
  SEO: 'Problemas de visibilidade',
  LGPD: 'Adequação LGPD',
  NONE: 'Sem necessidade identificada',
};

// Score Color Helpers
export const SCORE_COLORS = {
  high: 'bg-emerald-100 text-emerald-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-red-100 text-red-700',
};

export function getScoreColor(score: number): string {
  if (score >= 80) return SCORE_COLORS.high;
  if (score >= 60) return SCORE_COLORS.medium;
  return SCORE_COLORS.low;
}

export function formatPrimaryNeed(value?: string): string {
  if (!value) return PRIMARY_NEED_LABELS.NONE;
  return PRIMARY_NEED_LABELS[value] || value;
}

// Activity Labels
export const ACTIVITY_LABELS: Record<string, string> = {
  CREATED: 'Lead criado',
  ASSIGNED: 'Atribuído a consultor',
  UNASSIGNED: 'Lead desatribuído',
  STATUS_CHANGED: 'Status alterado',
  MESSAGE_GENERATED: 'Mensagem gerada',
  CONTACTED: 'Contato realizado',
  RESPONDED: 'Lead respondeu',
  MEETING_SCHEDULED: 'Reunião marcada',
  PROPOSAL_SENT: 'Proposta enviada',
  LOST: 'Lead perdido',
  CONVERTED: 'Conversão registrada',
  CONTACT_ENRICHED: 'Decisores enriquecidos',
  WHATSAPP_SENT: 'WhatsApp acionado',
  LINKEDIN_ASSOCIATED: 'Perfil LinkedIn associado',
};

// Kanban Column Status Configuration
export const KANBAN_STATUS_CONFIG: Record<string, { icon: string; label: string; color: string }> = {
  NOVO: { icon: '📋', label: 'Encontrado', color: 'bg-blue-100 text-blue-700' },
  ANALISADO: { icon: '🔍', label: 'Analisado', color: 'bg-purple-100 text-purple-700' },
  QUALIFICADO: { icon: '✅', label: 'Apto', color: 'bg-emerald-100 text-emerald-700' },
  DESQUALIFICADO: { icon: '❌', label: 'Desqualificado', color: 'bg-gray-100 text-gray-700' },
  CONTATADO: { icon: '📧', label: 'Mensagem enviada', color: 'bg-amber-100 text-amber-700' },
  RESPONDIDO: { icon: '💬', label: 'Respondeu', color: 'bg-purple-100 text-purple-700' },
  REUNIAO_MARCADA: { icon: '📅', label: 'Reunião', color: 'bg-pink-100 text-pink-700' },
  PERDIDO: { icon: '🚫', label: 'Perdido', color: 'bg-red-100 text-red-700' },
};

// Bulk Status Options
export const BULK_STATUS_OPTIONS = [
  { value: 'CONTATADO', label: 'Marcar como contatado' },
  { value: 'RESPONDIDO', label: 'Marcar como respondeu' },
  { value: 'REUNIAO_MARCADA', label: 'Marcar reunião marcada' },
  { value: 'PROPOSTA_ENVIADA', label: 'Marcar proposta enviada' },
  { value: 'PERDIDO', label: 'Marcar como perdido' },
];
