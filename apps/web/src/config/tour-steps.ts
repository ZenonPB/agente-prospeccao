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
    description:
      'Esta é a plataforma de prospecção B2B da sua equipe: ela encontra empresas que combinam com o seu serviço, analisa cada uma e organiza o contato. Vamos percorrer cada tela para você conhecer todas as funções. Use "Próximo" para avançar e "Voltar" para revisar qualquer etapa.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'metrics',
    targetRoute: '/dashboard',
    elementSelector: '[data-tour="dashboard-metrics"]',
    title: 'Números do seu funil',
    description:
      'Aqui você vê, em tempo real: quantos leads foram coletados, quantos foram qualificados (aptos para contato), a taxa de conversão até o fechamento e o faturamento gerado. Clique em um cartão para filtrar o restante do painel por aquele critério — é uma forma rápida de focar no que importa.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'funnel',
    targetRoute: '/dashboard',
    elementSelector: '[data-tour="dashboard-funnel"]',
    title: 'Funil e tendência',
    description:
      'O gráfico mostra o caminho completo do lead: do primeiro contato até a venda fechada. Acompanhe quantos leads estão em cada estágio e onde eles costumam parar. Se um estágio está com muita gente presa, é um sinal de que o trabalho ali precisa de atenção.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'active-campaigns',
    targetRoute: '/dashboard',
    elementSelector: '[data-tour="dashboard-campanhas"]',
    title: 'Suas buscas em andamento',
    description:
      'Esta lista mostra as campanhas ativas e o quanto cada uma avançou: quantos leads já foram encontrados e qual a aptidão média deles. É o lugar para perceber se uma busca está rendendo bem ou se vale pausar e ajustar a estratégia.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'today-actions',
    targetRoute: '/dashboard',
    elementSelector: '[data-tour="dashboard-hoje"]',
    title: 'O que precisa de você hoje',
    description:
      'Aqui ficam os compromissos pendentes: leads que passaram tempo demais parados, respostas que precisam de próximo passo e contatos agendados. Revisar esse painel todo dia garante que nenhuma oportunidade esfrie na sua mesa.',
    popoverSide: 'bottom',
    popoverAlign: 'end',
  },
  {
    id: 'timeline',
    targetRoute: '/dashboard',
    elementSelector: '[data-tour="dashboard-timeline"]',
    title: 'Histórico de atividade',
    description:
      'A linha do tempo registra o movimento da equipe: coleta, análise, contato, respostas e conversões. Todos os acontecimentos importantes ficam anotados automaticamente — você sempre sabe o que foi feito e quando.',
    popoverSide: 'bottom',
    popoverAlign: 'end',
  },
  {
    id: 'campaigns',
    targetRoute: '/campanhas',
    elementSelector: '[data-tour="campanhas-header"]',
    title: 'Campanhas: onde tudo começa',
    description:
      'Uma campanha é uma busca de prospecção: quem você quer encontrar, onde procurar e como avaliar. Você pode criá-la no wizard em passos guiados ou deixar a IA interpretar uma descrição sua. Cada campanha coleta empresas e as qualifica automaticamente.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'campaign-list',
    targetRoute: '/campanhas',
    elementSelector: '[data-tour="campanhas-lista"]',
    title: 'Suas campanhas e a nova campanha',
    description:
      'O botão "Nova Campanha" abre o assistente de criação em 4 passos: nome, segmento e cidade, tipo de análise e a vertente de critérios. Vale explorar também o modo Agente — você descreve em uma frase o que vende e a IA monta a campanha para você.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'campaign-cards',
    targetRoute: '/campanhas',
    elementSelector: '[data-tour="campanhas-cards"]',
    title: 'Card de campanha e coleta',
    description:
      'Cada card resume: quantos leads foram encontrados, o status da busca (em andamento, pausada, concluída) e a aptidão média. O botão "Iniciar Coleta" roda uma rodada de prospecção agora mesmo. Pelo menu de três pontos você pausa, retoma, duplica ou arquiva a busca. O detalhe da campanha tem entradas para importar CSV e buscar empresas por ramo de atividade (CNAE).',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'opportunities',
    targetRoute: '/oportunidades',
    elementSelector: '[data-tour="oportunidades-header"]',
    title: 'Oportunidades: seus leads analisados',
    description:
      'Aqui estão todas as empresas coletadas, já avaliadas com uma nota de 0 a 100. A nota reflete o quanto cada empresa combina com o que você vende. Abra um card para ver o dossiê completo: dados cadastrais, análise do site, contatos e sugestão de abordagem.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'opportunities-filters',
    targetRoute: '/oportunidades',
    elementSelector: '[data-tour="oportunidades-filtros"]',
    title: 'Filtros rápidos',
    description:
      'Três atalhos resumem os filtros mais usados: "Leads Quentes" (nota 80 ou mais), "Aptos para Contato" (nota 60 ou mais) e "Meus Leads" (só os que estão atribuídos a você). Um clique alterna o conteúdo da tela inteira.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'opportunities-search',
    targetRoute: '/oportunidades',
    elementSelector: '[data-tour="oportunidades-busca"]',
    title: 'Busca, campanha e ordenação',
    description:
      'Use a busca para achar uma empresa pelo nome. O seletor de campanha limita a lista a uma busca específica. E a ordenação decide a prioridade da listagem — por aptidão (maior/menor nota) ou por data (mais recentes ou antigos).',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'opportunities-cards',
    targetRoute: '/oportunidades',
    elementSelector: '[data-tour="oportunidades-lista"]',
    title: 'Cards, seleção e ações em lote',
    description:
      'Cada card mostra a nota, a prioridade (quente/morno/frio), a necessidade detectada e o status do lead. Marque vários cards para abrir as ações em lote: atribuir a um consultor, mover o funil em massa ou exportar em CSV. Clique no card para abrir o dossiê completo do lead.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'sales-header',
    targetRoute: '/vendas',
    elementSelector: '[data-tour="vendas-header"]',
    title: 'Negociações: o funil de vendas',
    description:
      'Esta tela organiza seus contatos como um quadro de negociações. Cada coluna é um estágio: novo, apto, contatado, respondeu, reunião marcada, reunião feita, proposta enviada — até o resultado final, fechou ou perdeu.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'sales-kanban',
    targetRoute: '/vendas',
    elementSelector: '[data-tour="vendas-kanban"]',
    title: 'Mover, acionar e acompanhar',
    description:
      'Arraste um card para trocar o estágio — isso registra o status no sistema e na linha do tempo. No card, você vê o valor estimado, os dias sem resposta e atalhos: enviar WhatsApp com 1 clique e atribuir o lead a um consultor. Leads vencidos recebem um alerta para você não deixá-los esfriar.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
  },
  {
    id: 'analytics',
    targetRoute: '/relatorios',
    elementSelector: '[data-tour="relatorios-header"]',
    title: 'Relatórios: a visão do time',
    description:
      'Aqui está a inteligência de negócio: KPIs executivos, funil completo com taxas de conversão, receita realizada, previsão ponderada e o desempenho de cada consultor. Use para decidir onde a equipe deve focar e quanto faturamento está a caminho.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
    analystOnly: true,
  },
  {
    id: 'analytics-controls',
    targetRoute: '/relatorios',
    elementSelector: '[data-tour="relatorios-controles"]',
    title: 'Período e exportação em PDF',
    description:
      'Escolha o período do relatório — últimos 30 dias, 90 dias ou um intervalo personalizado — e tudo é recalculado na hora. O botão de exportar gera um PDF executivo com visual, funil, campanhas, consultores e as melhores oportunidades para enviar à diretoria.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
    analystOnly: true,
  },
  {
    id: 'analytics-content',
    targetRoute: '/relatorios',
    elementSelector: '[data-tour="relatorios-conteudo"]',
    title: 'Mapa, scorebands e rankings',
    description:
      'Nesta tela você encontra o mapa de oportunidades por região, a taxa de conversão por faixa de nota (entende qual "perfil" de lead fecha mais), as melhores oportunidades, o ranking por consultor e a evolução temporal. É o raio-x do negócio todo.',
    popoverSide: 'bottom',
    popoverAlign: 'center',
    analystOnly: true,
  },
  {
    id: 'vertentes-header',
    targetRoute: '/configuracoes/vertentes',
    elementSelector: '[data-tour="vertentes-header"]',
    title: 'Vertentes: os perfis que a IA avalia',
    description:
      'Uma vertente define como a IA avalia e aborda um tipo de empresa: quais informações buscar, o que indica oportunidade e como acompanhar. Existem vertentes de fábrica (para todos os times) e vertentes criadas pelo seu. Gestores podem criar, duplicar e ativar.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'vertentes-busca',
    targetRoute: '/configuracoes/vertentes',
    elementSelector: '[data-tour="vertentes-busca"]',
    title: 'Criar, duplicar e usar vertentes',
    description:
      'Pesquise pelo nome da vertente. Gestores podem criar uma nova descrevendo em uma frase o que vendem (ex.: "manutenção de compressores para indústrias de alimentos") — a IA gera um rascunho revisável. Ou duplique uma vertente de fábrica como ponto de partida e ajuste os critérios ao seu público.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'settings-profile',
    targetRoute: '/configuracoes',
    elementSelector: '[data-tour="configuracoes-perfil"]',
    title: 'Seu perfil e aparência',
    description:
      'Edite seu nome, veja seu papel na equipe, altere a senha e troque o tema do sistema (Claro, Escuro ou AlphaMec). As preferências ficam salvas no seu navegador.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'settings-keys',
    targetRoute: '/configuracoes',
    elementSelector: '[data-tour="configuracoes-chaves"]',
    title: 'Chaves de IA e envio automático',
    description:
      'Nas chaves de API você conecta as chaves da sua organização para IA e Google (a equipe define quem pode gerenciá-las). Ajuste também o envio automático de acompanhamentos: limite diário, horário de envio e o remetente usado.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'settings-envio',
    targetRoute: '/configuracoes',
    elementSelector: '[data-tour="configuracoes-envio"]',
    title: 'Enviar mensagens automaticamente',
    description:
      'Esta seção controla os follow-ups automáticos: se o envio está ativo, quantas mensagens por dia podem sair e em que janela de horário. Também dá para configurar prazos de SLA — quando um lead parado deve voltar ao radar — e o limite de nota para a fila de contato.',
    popoverSide: 'bottom',
    popoverAlign: 'start',
  },
  {
    id: 'settings-finish',
    targetRoute: '/configuracoes',
    elementSelector: '[data-tour="configuracoes-tour-card"]',
    title: 'Tudo pronto!',
    description:
      'Você conheceu as principais telas: dashboard, campanhas, oportunidades, negociações, relatórios, vertentes e configurações. Pode refazer este tour a qualquer momento por este cartão ou pelo menu do seu perfil no topo. Bom trabalho em campo!',
    popoverSide: 'top',
    popoverAlign: 'start',
  },
];