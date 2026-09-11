/**
 * Rótulos em português das ofertas e dos sinais comerciais.
 *
 * Mapa centralizado e reutilizável: qualquer tela que mostre uma oferta
 * (campanhas, oportunidades, conversão, relatórios) deve usar
 * `offerProfileLabel` / `SIGNAL_LABELS` em vez da chave crua
 * (`landing_page`, `HOSTS_EVENTS`, ...). Nomes PT espelham o catálogo
 * de ofertas do backend.
 */

export const OFFER_PROFILE_OPTIONS = [
  { key: 'landing_page', label: 'Landing Page de Conversão' },
  { key: 'mechanical_project', label: 'Projeto Mecânico' },
  { key: 'technical_drawing', label: 'Desenho Técnico' },
  { key: 'machine_manual', label: 'Manual de Máquinas' },
  { key: 'trophies', label: 'Troféus Personalizados' },
] as const;

export type OfferProfileKey = (typeof OFFER_PROFILE_OPTIONS)[number]['key'];

const OFFER_LABEL_BY_KEY: Record<string, string> = Object.fromEntries(
  OFFER_PROFILE_OPTIONS.map((option) => [option.key, option.label]),
);

/** Nome em português da oferta; desconhecida mostra a chave original. */
export function offerProfileLabel(key?: string | null): string {
  if (!key) return 'Não identificada';
  return OFFER_LABEL_BY_KEY[key] ?? key;
}

/** De onde veio a sugestão da oferta, em linguagem de vendedor. */
export function offerOriginLabel(resolvedFrom?: string | null): string {
  switch (resolvedFrom) {
    case 'explicit':
      return 'Você escolheu';
    case 'vertical':
    case 'archetype':
      return 'Detectada no texto que você escreveu';
    default:
      return 'Sugestão padrão do sistema';
  }
}

/** Sinais comerciais traduzidos para linguagem de vendedor. */
export const SIGNAL_LABELS: Record<string, string> = {
  NO_OWN_WEBSITE: 'Sem site próprio',
  HAS_OWN_WEBSITE_INSTITUTIONAL: 'Já tem site institucional',
  HAS_INSTAGRAM: 'Tem Instagram ativo',
  HAS_PHONE: 'Tem telefone para contato',
  HAS_CNPJ: 'Empresa formal (CNPJ)',
  HAS_BUSINESS_EMAIL: 'Tem e-mail comercial',
  GOOGLE_RATING: 'Bem avaliada no Google',
  GOOGLE_RATING_COUNT: 'Bastante avaliada no Google',
  RETAIL_FOCUSED: 'Foco em varejo',
  SERVICE_ONLY: 'Só presta serviços',
  ENTERPRISE: 'Empresa de grande porte',
  CNAE_INDUSTRIAL: 'Atividade industrial',
  HOSTS_EVENTS: 'Organiza eventos',
  ONLINE_ONLY_RESALE: 'Vende só pela internet',
  HIRING: 'Está contratando',
  EXPANDING: 'Está crescendo',
  NEW_EQUIPMENT: 'Comprou equipamento novo',
  EVENT_SCHEDULED: 'Evento marcado',
  SEASONAL_DEMAND: 'Demanda de temporada',
};

/** Rótulo PT de um sinal; desconhecido mostra a chave original. */
export function signalLabel(key?: string | null): string {
  if (!key) return '—';
  return SIGNAL_LABELS[key] ?? key;
}
