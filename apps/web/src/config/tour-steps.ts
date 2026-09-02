export interface TourStep {
  id: string;
  targetRoute: string;
  /**
   * Resolve a rota em tempo real: 'first-campaign' aponta para o detalhe da
   * primeira campanha da org (a rota real depende do id). Sem campanha, o
   * passo é pulado.
   */
  routeResolver?: 'first-campaign';
  /** Seletor do elemento a destacar. Omita (ou use null) para um popover centralizado. */
  elementSelector?: string | null;
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
    elementSelector: null,
    title: 'Boas-vindas ao Prospect.ai',
    description:
      'Este sistema encontra empresas com perfil para o seu serviço, analisa cada uma e organiza o contato até a reunião. O tour passa pelas telas principais em poucos minutos — e você pode pausar quando quiser: ele lembra onde parou.',
  },
  {
    id: 'metrics',
    targetRoute: '/dashboard',
    elementSelector: '[data-tour="dashboard-metrics"]',
    title: 'Os números do funil',
    description:
      'Em tempo real: empresas encontradas, prontas para contato, em conversa e reuniões marcadas. Clique em um cartão para filtrar o painel inteiro por aquele número.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'funnel',
    targetRoute: '/dashboard',
    elementSelector: '[data-tour="dashboard-funnel"]',
    title: 'O caminho até a venda',
    description:
      'Da primeira busca ao fechamento, etapa por etapa. Repare onde os leads se acumulam — é ali que vale agir.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'active-campaigns',
    targetRoute: '/dashboard',
    elementSelector: '[data-tour="dashboard-campanhas"]',
    title: 'Buscas em andamento',
    description:
      'Cada linha é uma busca e o quanto ela já rendeu. Use para decidir quando pausar, ajustar ou reforçar.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'today-actions',
    targetRoute: '/dashboard',
    elementSelector: '[data-tour="dashboard-hoje"]',
    title: 'O que precisa de você hoje',
    description:
      'Leads parados há tempo demais, respostas pendentes e reuniões próximas. Comece o dia por aqui para nenhuma oportunidade esfriar.',
    popoverSide: 'bottom',
    popoverAlign: 'end',
  },
  {
    id: 'timeline',
    targetRoute: '/dashboard',
    elementSelector: '[data-tour="dashboard-timeline"]',
    title: 'Histórico do time',
    description:
      'Coletas, análises, contatos e respostas — tudo registrado automaticamente. Você sempre sabe o que foi feito e quando.',
    popoverSide: 'bottom',
    popoverAlign: 'end',
  },
  {
    id: 'campaigns',
    targetRoute: '/campanhas',
    elementSelector: '[data-tour="campanhas-header"]',
    title: 'Campanhas: onde tudo começa',
    description:
      'Uma campanha é uma busca: quem encontrar, onde procurar e como avaliar. A IA monta a campanha a partir de uma frase sua — ou você cria passo a passo.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'campaign-list',
    targetRoute: '/campanhas',
    elementSelector: '[data-tour="campanhas-lista"]',
    title: 'Criar uma nova campanha',
    description:
      'O botão "Nova Campanha" abre o assistente em 4 passos. No modo Agente, descreva o que você vende e a IA prepara tudo — depois é só revisar.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'campaign-cards',
    targetRoute: '/campanhas',
    elementSelector: '[data-tour="campanhas-cards"]',
    title: 'Acompanhar cada busca',
    description:
      'Cada card mostra quantos leads a busca trouxe e a nota média deles. "Iniciar Coleta" roda uma rodada agora; no menu ⋯ você pausa, duplica ou arquiva. Abra um card para ver a busca por dentro.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'campaign-pipeline',
    targetRoute: '/campanhas',
    routeResolver: 'first-campaign',
    elementSelector: '[data-tour="campanha-pipeline"]',
    title: 'Dentro de uma busca',
    description:
      'Aqui a IA trabalha: coleta empresas, analisa sites e dados cadastrais e dá uma nota de 0 a 100 com justificativa. "Iniciar Coleta" traz novos leads; "Reanalisar" refaz a avaliação com os critérios atuais.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'campaign-learning',
    targetRoute: '/campanhas',
    routeResolver: 'first-campaign',
    elementSelector: '[data-tour="campanha-aprendizados"]',
    title: 'A IA aprende com o seu time 🧠',
    description:
      'A nota é um ponto de partida — quem conhece o cliente é você. No kanban, "Discordar do score" registra a nota certa e o motivo; aqui, "Sintetizar aprendizados" transforma as correções em regras que a IA usa nas próximas análises. Com o tempo, ela erra cada vez menos.',
    popoverSide: 'top',
    popoverAlign: 'center',
  },
  {
    id: 'opportunities',
    targetRoute: '/oportunidades',
    elementSelector: '[data-tour="oportunidades-header"]',
    title: 'Oportunidades: leads analisados',
    description:
      'Todas as empresas coletadas com uma nota de 0 a 100 — quanto maior, mais combina com o que você vende. Abra um card para ver o dossiê completo.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'opportunities-filters',
    targetRoute: '/oportunidades',
    elementSelector: '[data-tour="oportunidades-filtros"]',
    title: 'Filtros rápidos',
    description:
      'Atalhos para o que mais se usa: Quentes (nota 80+), Prontos (60+) e Meus Leads. Um clique muda a lista inteira.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'opportunities-search',
    targetRoute: '/oportunidades',
    elementSelector: '[data-tour="oportunidades-busca"]',
    title: 'Busca e ordenação',
    description:
      'Ache uma empresa pelo nome, limite a lista a uma campanha e escolha a ordem — por nota ou por data.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'opportunities-cards',
    targetRoute: '/oportunidades',
    elementSelector: '[data-tour="oportunidades-lista"]',
    title: 'Cards e ações em lote',
    description:
      'Nota, prioridade e necessidade de cada empresa. Marque vários para agir em lote: atribuir, mover no funil ou exportar.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'sales-header',
    targetRoute: '/vendas',
    elementSelector: '[data-tour="vendas-header"]',
    title: 'Negociações: o funil de vendas',
    description:
      'Cada coluna é uma etapa do comercial: do lead novo até a proposta enviada. É o quadro que o time acompanha todo dia.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'sales-kanban',
    targetRoute: '/vendas',
    elementSelector: '[data-tour="vendas-kanban"]',
    title: 'Mover pelo quadro',
    description:
      'Segure o topo de um cartão e arraste para a próxima etapa — o status atualiza na hora. No cartão há atalhos de WhatsApp e atribuição; alertas vermelhos marcam leads parados.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'ai-score-feedback',
    targetRoute: '/vendas',
    elementSelector: '[data-tour="vendas-card-menu"]',
    title: 'Discorde de uma nota errada',
    description:
      'A IA errou a avaliação de um lead? No menu ⋯ do cartão, use "Discordar do score": informe a nota que você daria e o motivo. Sua correção vira aprendizado — vale no próximo ciclo de análises.',
    popoverSide: 'bottom',
    popoverAlign: 'end',
  },
  {
    id: 'analytics',
    targetRoute: '/relatorios',
    elementSelector: '[data-tour="relatorios-header"]',
    title: 'Relatórios: os números do negócio',
    description:
      'Funil com taxas de conversão, receita, previsão e desempenho por consultor. É daqui que saem as decisões de foco.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
    analystOnly: true,
  },
  {
    id: 'analytics-controls',
    targetRoute: '/relatorios',
    elementSelector: '[data-tour="relatorios-controles"]',
    title: 'Período e PDF para a diretoria',
    description:
      'Escolha o período — 30 dias, 90 dias ou um intervalo seu — e tudo é recalculado na hora. O botão de exportação gera um PDF executivo pronto para enviar.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
    analystOnly: true,
  },
  {
    id: 'analytics-content',
    targetRoute: '/relatorios',
    elementSelector: '[data-tour="relatorios-conteudo"]',
    title: 'Mapa, faixas de nota e rankings',
    description:
      'Oportunidades por região, conversão por faixa de nota (qual perfil fecha mais) e ranking dos consultores — o raio-x do negócio.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
    analystOnly: true,
  },
  {
    id: 'analytics-convergence',
    targetRoute: '/relatorios',
    elementSelector: '[data-tour="relatorios-convergencia"]',
    title: 'A IA está aprendendo?',
    description:
      'Este card mostra o desvio médio entre a nota da IA e a do consultor. Barras encolhendo = a IA convergindo com o time. Se aparecer aqui, é porque o time já está ensinando pela correção de scores.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
    analystOnly: true,
  },
  {
    id: 'vertentes-header',
    targetRoute: '/configuracoes/vertentes',
    elementSelector: '[data-tour="vertentes-header"]',
    title: 'Vertentes: como a IA avalia',
    description:
      'Uma vertente ensina a IA a avaliar e abordar um tipo de empresa. Existem vertentes prontas e as criadas pelo seu time — gestores podem criar e ajustar.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'vertentes-busca',
    targetRoute: '/configuracoes/vertentes',
    elementSelector: '[data-tour="vertentes-busca"]',
    title: 'Criar ou duplicar',
    description:
      'Descreva o que você vende em uma frase (ex.: "manutenção de compressores para indústrias") e a IA gera um rascunho revisável. Ou duplique uma pronta e ajuste os critérios.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'settings-profile',
    targetRoute: '/configuracoes',
    elementSelector: '[data-tour="configuracoes-perfil"]',
    title: 'Seu perfil e aparência',
    description:
      'Nome, papel na equipe, senha e o tema do sistema: Claro, Escuro ou AlphaMec.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'settings-keys',
    targetRoute: '/configuracoes',
    elementSelector: '[data-tour="configuracoes-chaves"]',
    title: 'Chaves de IA e do Google',
    description:
      'Conecte as chaves da sua organização (quem pode mexer nelas é definido pela equipe). Sem isso, o sistema usa o pool global.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'settings-envio',
    targetRoute: '/configuracoes',
    elementSelector: '[data-tour="configuracoes-envio"]',
    title: 'Envio automático de mensagens',
    description:
      'Quantas mensagens por dia, em que horários e os prazos em que um lead parado volta ao radar. Configure com calma — é o motor dos follow-ups.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'settings-finish',
    targetRoute: '/configuracoes',
    elementSelector: null,
    title: 'Tudo pronto! 🎉',
    description:
      'Você conheceu as telas principais: dashboard, campanhas, oportunidades, negociações, relatórios, vertentes e configurações. Refaça este tour quando quiser — pelo menu do seu perfil ou pelo cartão de tour nas Configurações. Bom trabalho!',
  },
];