import { humanizeCode, offerProfileLabel, signalLabel } from '@/lib/offers';

export const BUYER_ROLE_OPTIONS = [
  { value: 'ECONOMIC_BUYER', label: 'Responsável pela aprovação financeira' },
  { value: 'TECHNICAL_BUYER', label: 'Responsável pela avaliação técnica' },
  { value: 'CHAMPION', label: 'Pessoa que pode impulsionar a compra' },
  { value: 'INFLUENCER', label: 'Influenciador da decisão' },
  { value: 'END_USER', label: 'Usuário da solução' },
] as const;

const BUYER_ROLE_LABELS = Object.fromEntries(
  BUYER_ROLE_OPTIONS.map((item) => [item.value, item.label]),
) as Record<string, string>;

export function buyerRoleLabel(value?: string | null): string {
  if (!value) return 'Papel ainda não identificado';
  return BUYER_ROLE_LABELS[value] ?? humanizeCode(value);
}

const FRESHNESS_LABELS: Record<string, string> = {
  website: 'Site',
  company_registry: 'Dados cadastrais',
  technographics: 'Tecnologias utilizadas',
  employment: 'Vínculo profissional',
  email: 'E-mail',
  phone: 'Telefone',
  jobs: 'Vagas e contratações',
  news: 'Notícias',
  social: 'Redes sociais',
  intent: 'Sinais de compra',
  event: 'Evento',
};

export function freshnessLabel(value?: string | null): string {
  if (!value) return 'Informação';
  return FRESHNESS_LABELS[value] ?? humanizeCode(value);
}

const PHONE_STATE_LABELS: Record<string, string> = {
  VERIFIED: 'Verificado por fonte confiável',
  LIKELY_VALID: 'Formato provavelmente válido',
  UNKNOWN: 'Ainda não confirmado',
  INVALID: 'Formato inválido',
};

export function phoneStateLabel(value?: string | null): string {
  if (!value) return 'Ainda não confirmado';
  return PHONE_STATE_LABELS[value] ?? humanizeCode(value);
}

const PROVIDER_LABELS: Record<string, string> = {
  google_places: 'Google Maps',
  cnae_discovery: 'Dados cadastrais',
  website_people: 'Site oficial',
  company_site: 'Site oficial',
  hunter: 'Hunter',
  hunter_people: 'Hunter',
  job_postings: 'Vagas e carreiras',
  company_news: 'Notícias corporativas',
  procurement: 'Compras e licitações',
  pncp: 'PNCP',
  social: 'Redes sociais',
  events: 'Eventos',
  event: 'Eventos',
  passive_technographics: 'Site e tecnologias',
  continuous_intelligence: 'Monitoramento comercial',
  email_catchall: 'Validação de domínio de e-mail',
};

export function providerLabel(value?: string | null): string {
  if (!value) return 'Fonte não informada';
  return PROVIDER_LABELS[value] ?? humanizeCode(value);
}

const FILTER_LABELS: Record<string, string> = {
  q: 'Empresa ou termo',
  query: 'Empresa ou termo',
  city: 'Cidade',
  state: 'Estado',
  min_score: 'Qualidade mínima',
  has_email: 'Com e-mail',
  has_phone: 'Com telefone',
  offer_key: 'Oferta',
};

export function filterLabel(key: string): string {
  return FILTER_LABELS[key] ?? humanizeCode(key);
}

export function filterValueLabel(key: string, value: unknown): string {
  if (typeof value === 'boolean') return value ? 'Sim' : 'Não';
  if (key === 'offer_key') return offerProfileLabel(String(value));
  if (key === 'signal' || key === 'signals') return signalLabel(String(value));
  if (Array.isArray(value)) return value.map((item) => humanizeCode(String(item))).join(', ');
  return String(value);
}

export const SEARCH_SIGNAL_OPTIONS = [
  'HAS_CNC',
  'EXPANDING_FACTORY',
  'HIRING_MECHANICAL_ENGINEER',
  'NEW_FACTORY',
  'NEW_BRANCH',
  'HIRING_IT',
  'HIRING_OPERATIONS',
  'EVENT_SCHEDULED',
  'SEASONAL_DEMAND',
  'HAS_ADS',
  'NO_CONTACT_FORM',
] as const;
