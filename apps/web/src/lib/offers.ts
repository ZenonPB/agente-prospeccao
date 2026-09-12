/** Rótulos de apresentação do catálogo comercial. */
export const OFFER_PROFILE_OPTIONS = [
  { key: 'landing_page', label: 'Landing Page de Conversão' },
  { key: 'web_systems_erp', label: 'Sistemas Web e ERP' },
  { key: 'mechanical_project', label: 'Projeto Mecânico' },
  { key: 'technical_drawing', label: 'Desenho Técnico' },
  { key: 'machine_manual', label: 'Manual de Máquinas e NR-12' },
  { key: '3d_printing', label: 'Impressão 3D' },
  { key: 'laser_cutting_technical', label: 'Corte a Laser Técnico' },
  { key: 'laser_custom_products', label: 'Produtos Personalizados a Laser' },
  { key: 'trophies', label: 'Troféus Personalizados' },
] as const;

export type OfferProfileKey = (typeof OFFER_PROFILE_OPTIONS)[number]['key'];

const OFFER_LABEL_BY_KEY: Record<string, string> = Object.fromEntries(
  OFFER_PROFILE_OPTIONS.map((option) => [option.key, option.label]),
);

export function humanizeCode(value?: string | null): string {
  if (!value) return '—';
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLocaleLowerCase('pt-BR')
    .replace(/(^|\s)\p{L}/gu, (letter) => letter.toLocaleUpperCase('pt-BR'));
}

export function offerProfileLabel(key?: string | null): string {
  if (!key) return 'Não identificada';
  return OFFER_LABEL_BY_KEY[key] ?? humanizeCode(key);
}

export function offerOriginLabel(resolvedFrom?: string | null): string {
  switch (resolvedFrom) {
    case 'explicit':
      return 'Você escolheu';
    case 'vertical':
    case 'archetype':
      return 'Detectada a partir das informações da oportunidade';
    default:
      return 'Sugestão do sistema';
  }
}

export const SIGNAL_LABELS: Record<string, string> = {
  NO_OWN_WEBSITE: 'Sem site próprio',
  HAS_OWN_WEBSITE_INSTITUTIONAL: 'Já tem site institucional',
  HAS_INSTAGRAM: 'Tem Instagram ativo',
  HAS_PHONE: 'Tem telefone para contato',
  HAS_CNPJ: 'Empresa formalizada',
  HAS_BUSINESS_EMAIL: 'Tem e-mail comercial',
  GOOGLE_RATING: 'Bem avaliada no Google',
  GOOGLE_RATING_COUNT: 'Tem muitas avaliações no Google',
  RETAIL_FOCUSED: 'Foco em varejo',
  SERVICE_ONLY: 'Atuação concentrada em serviços',
  ENTERPRISE: 'Empresa de grande porte',
  CNAE_INDUSTRIAL: 'Atividade industrial',
  HOSTS_EVENTS: 'Organiza eventos',
  ONLINE_ONLY_RESALE: 'Vende somente pela internet',
  HIRING: 'Está contratando',
  EXPANDING: 'Está em expansão',
  EXPANSION: 'Está em expansão',
  EXPANDING_FACTORY: 'Expansão da fábrica',
  NEW_BRANCH: 'Nova unidade identificada',
  NEW_FACTORY: 'Nova fábrica identificada',
  NEW_PRODUCT: 'Novo produto identificado',
  FUNDING: 'Novo investimento identificado',
  MANAGEMENT_CHANGE: 'Mudança de gestão',
  NEW_EQUIPMENT: 'Equipamento novo identificado',
  EVENT_SCHEDULED: 'Evento programado',
  SEASONAL_DEMAND: 'Demanda sazonal',
  HAS_ADS: 'Investe em anúncios',
  WEAK_CTA: 'Chamadas para ação pouco claras',
  NO_CONTACT_FORM: 'Sem formulário de contato',
  WEAK_CONVERSION_FLOW: 'Fluxo de conversão pode melhorar',
  HAS_PRODUCTION_LINE: 'Possui linha de produção',
  CUSTOM_MACHINERY: 'Utiliza máquinas personalizadas',
  AUTOMATION: 'Possui processos automatizados',
  HAS_CNC: 'Possui máquinas CNC',
  HIRING_MECHANICAL_ENGINEER: 'Contratando engenharia mecânica',
  HIRING_PROJECT_DESIGNER: 'Contratando projetista',
  HIRING_MAINTENANCE: 'Contratando para manutenção',
  HIRING_AUTOMATION: 'Contratando para automação',
  HIRING_CNC_OPERATOR: 'Contratando operador de CNC',
  HIRING_IT: 'Contratando para tecnologia',
  HIRING_OPERATIONS: 'Contratando para operações',
  HIRING_DATA: 'Contratando para dados',
  USINAGEM: 'Atua com usinagem',
  CUSTOM_PARTS: 'Demanda por peças sob medida',
  REPLACEMENT_PARTS: 'Demanda por peças de reposição',
  REVERSE_ENGINEERING: 'Necessidade de engenharia reversa',
  CUSTOM_MANUFACTURING: 'Fabricação personalizada',
  MACHINE_MANUFACTURER: 'Fabrica máquinas',
  NR12: 'Demanda relacionada à NR-12',
  INDUSTRIAL_SAFETY: 'Demanda de segurança industrial',
  TECHNICAL_DOCUMENTATION: 'Necessidade de documentação técnica',
  NEW_MACHINE: 'Nova máquina identificada',
  MULTI_UNIT: 'Opera em múltiplas unidades',
  MANUAL_PROCESS: 'Processo manual relevante',
  USES_SPREADSHEETS: 'Dependência de planilhas',
  SAAS_LIMITATION: 'Limitação do sistema atual',
  VERY_SMALL_LOW_COMPLEXITY: 'Operação pequena e pouco complexa',
  PROTOTYPE: 'Necessidade de protótipo',
  R_AND_D: 'Atuação em pesquisa e desenvolvimento',
  CUSTOM_PRODUCTS: 'Demanda por produtos personalizados',
  TENDER_OPEN: 'Licitação aberta',
  SOFTWARE_PROCUREMENT: 'Compra de software em andamento',
  INDUSTRIAL_PROCUREMENT: 'Compra industrial em andamento',
  EVENT_PROCUREMENT: 'Compra para evento ou premiação',
  JOB_CHANGE: 'Mudança de empresa do contato',
  ROLE_CHANGE: 'Mudança de cargo do contato',
};

export function signalLabel(key?: string | null): string {
  if (!key) return '—';
  return SIGNAL_LABELS[key] ?? humanizeCode(key);
}
