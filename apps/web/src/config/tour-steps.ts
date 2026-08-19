export interface TourStep {
  id: string;
  targetRoute: string;
  elementSelector: string;
  title: string;
  description: string;
  popoverSide?: 'top' | 'bottom' | 'left' | 'right';
  popoverAlign?: 'start' | 'center' | 'end';
  analystOnly?: boolean;
}

export const TOUR_STEPS: TourStep[] = [
  {
    id: 'welcome',
    targetRoute: '/dashboard',
    elementSelector: '[data-tour="dashboard-header"]',
    title: 'Boas-vindas ao Agente Prospecção',
    description: 'Sua plataforma inteligente de prospecção B2B. Vamos fazer um tour guiado rápido pelas principais funcionalidades do sistema.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'metrics',
    targetRoute: '/dashboard',
    elementSelector: '[data-tour="dashboard-metrics"]',
    title: 'Visão Geral & Métricas',
    description: 'Acompanhe seu funil em tempo real, total de leads qualificados, taxa de conversão e alertas de SLA de atendimento.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'campaigns',
    targetRoute: '/campanhas',
    elementSelector: '[data-tour="campanhas-header"]',
    title: 'Campanhas de Prospecção',
    description: 'Crie e gerencie buscas de leads com inteligência artificial, integração ao Google Places, filtro por CNAE ou importação por CSV.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'opportunities',
    targetRoute: '/oportunidades',
    elementSelector: '[data-tour="oportunidades-header"]',
    title: 'Oportunidades & Qualificação',
    description: 'Explore os leads analisados com score de 0 a 100, dossiê do site, evidências e gerador automático de mensagens de abordagem.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'sales-kanban',
    targetRoute: '/vendas',
    elementSelector: '[data-tour="vendas-kanban"]',
    title: 'Negociações & Funil Kanban',
    description: 'Acompanhe suas negociações por estágio, mova cartões e acione clientes no WhatsApp com 1 clique diretamente pelo painel.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'analytics',
    targetRoute: '/relatorios',
    elementSelector: '[data-tour="relatorios-header"]',
    title: 'Relatórios & Inteligência BI',
    description: 'Analise o mapa geográfico de oportunidades, taxa por consultor, evolução temporal e exporte relatórios executivos em PDF.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
    analystOnly: true,
  },
  {
    id: 'settings',
    targetRoute: '/configuracoes',
    elementSelector: '[data-tour="configuracoes-tour-card"]',
    title: 'Configurações & Tutorial',
    description: 'Tudo pronto! Você pode editar seu perfil, gerenciar chaves e refazer este tutorial a qualquer momento nesta tela ou pelo menu superior.',
    popoverSide: 'top',
    popoverAlign: 'start',
  },
];
