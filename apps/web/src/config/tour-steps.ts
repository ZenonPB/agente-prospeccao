export interface TourStep {
  id: string;
  chapter: 'Começando' | 'Encontrando clientes' | 'Vendendo' | 'Melhorando' | 'Configuração';
  targetRoute: string;
  routeResolver?: 'first-campaign';
  elementSelector?: string | null;
  title: string;
  description: string;
  popoverSide?: 'top' | 'bottom' | 'left' | 'right';
  popoverAlign?: 'start' | 'center' | 'end';
  analystOnly?: boolean;
}

export const TOUR_STEPS: TourStep[] = [
  {
    id: 'welcome', chapter: 'Começando', targetRoute: '/dashboard', elementSelector: null,
    title: 'Bem-vindo ao Prospect.ai',
    description: 'A ideia é simples: você diz o que quer vender, o sistema encontra empresas com sinais de necessidade, ajuda a priorizar quem abordar e organiza o trabalho até o fechamento. Você pode fechar este tutorial a qualquer momento e continuar de onde parou.',
  },
  {
    id: 'dashboard-metrics', chapter: 'Começando', targetRoute: '/dashboard', elementSelector: '[data-tour="dashboard-metrics"]',
    title: 'Seu negócio em uma olhada',
    description: 'Aqui você vê quantas empresas entraram, quantas estão prontas para contato, quantas avançaram e onde o time está concentrando esforço. Use este painel para perceber rapidamente quando algo está parado.',
    popoverSide: 'bottom', popoverAlign: 'center',
  },
  {
    id: 'dashboard-today', chapter: 'Começando', targetRoute: '/dashboard', elementSelector: '[data-tour="dashboard-hoje"]',
    title: 'Comece pelo que precisa de atenção',
    description: 'Esta área resume pendências e oportunidades que não deveriam esperar. Para a operação diária, ela é mais importante do que ficar procurando lead por lead.',
    popoverSide: 'bottom', popoverAlign: 'end',
  },
  {
    id: 'crm-home', chapter: 'Começando', targetRoute: '/crm', elementSelector: null,
    title: 'Minha carteira é a sua central de trabalho',
    description: 'Pesquise qualquer empresa, pessoa ou oportunidade e veja a fila priorizada do dia. Quando estiver em dúvida sobre o que fazer agora, volte para esta tela.',
  },
  {
    id: 'campaigns', chapter: 'Encontrando clientes', targetRoute: '/campanhas', elementSelector: '[data-tour="campanhas-header"]',
    title: 'Buscar clientes começa por uma campanha',
    description: 'Campanha aqui significa uma busca organizada por um tipo de cliente. Você não precisa conhecer termos técnicos: basta partir do que a AlphaMec quer vender e para quem.',
    popoverSide: 'bottom', popoverAlign: 'start',
  },
  {
    id: 'campaign-create', chapter: 'Encontrando clientes', targetRoute: '/campanhas', elementSelector: '[data-tour="campanhas-lista"]',
    title: 'Crie a busca falando normalmente',
    description: 'Clique em “Nova campanha” e escreva algo como “quero vender landing pages para clínicas de psicologia de Araraquara” ou “quero encontrar eventos de empresa júnior que possam precisar de troféus”. O sistema transforma a frase em uma estratégia para você revisar.',
    popoverSide: 'bottom', popoverAlign: 'start',
  },
  {
    id: 'campaign-cards', chapter: 'Encontrando clientes', targetRoute: '/campanhas', elementSelector: '[data-tour="campanhas-cards"]',
    title: 'Acompanhe o que cada busca encontrou',
    description: 'Os cartões mostram o andamento de cada busca. Abra uma campanha para entender o que foi encontrado, revisar a qualidade e decidir se vale continuar, ajustar ou pausar.',
    popoverSide: 'bottom', popoverAlign: 'center',
  },
  {
    id: 'campaign-detail', chapter: 'Encontrando clientes', targetRoute: '/campanhas', routeResolver: 'first-campaign', elementSelector: '[data-tour="campanha-pipeline"]',
    title: 'Dentro de uma campanha',
    description: 'Se já existir uma campanha, esta tela mostra como os leads percorrem a busca e a análise. A nota nunca deve ser lida sozinha: abra o lead e confira os motivos e evidências que justificam a recomendação.',
    popoverSide: 'bottom', popoverAlign: 'center',
  },
  {
    id: 'opportunities', chapter: 'Encontrando clientes', targetRoute: '/oportunidades', elementSelector: '[data-tour="oportunidades-header"]',
    title: 'Leads qualificados',
    description: 'Aqui ficam as empresas que passaram pela análise. Use filtros, busca e ordenação para reduzir a lista antes de gastar tempo pesquisando ou entrando em contato.',
    popoverSide: 'bottom', popoverAlign: 'start',
  },
  {
    id: 'opportunities-list', chapter: 'Encontrando clientes', targetRoute: '/oportunidades', elementSelector: '[data-tour="oportunidades-lista"]',
    title: 'Abra o dossiê antes de abordar',
    description: 'Cada lead reúne sinais, contatos, histórico e oportunidades por serviço. Prefira evidências concretas a suposições e use a visão completa para preparar uma abordagem específica.',
    popoverSide: 'bottom', popoverAlign: 'center',
  },
  {
    id: 'followups', chapter: 'Vendendo', targetRoute: '/sequences', elementSelector: null,
    title: 'Follow-ups sem depender da memória',
    description: 'As sequências organizam os próximos passos de contato. Elas ajudam a lembrar quando agir, mas não transformam ausência de resposta em interesse e não devem substituir revisão humana antes de uma abordagem sensível.',
  },
  {
    id: 'sales', chapter: 'Vendendo', targetRoute: '/vendas', elementSelector: '[data-tour="vendas-header"]',
    title: 'Funil de vendas',
    description: 'O quadro mostra em que ponto cada negociação está. Mova as oportunidades conforme algo realmente aconteceu — contato, resposta, reunião, proposta — para que os relatórios representem a realidade.',
    popoverSide: 'bottom', popoverAlign: 'start',
  },
  {
    id: 'sales-kanban', chapter: 'Vendendo', targetRoute: '/vendas', elementSelector: '[data-tour="vendas-kanban"]',
    title: 'O quadro é a memória comercial da equipe',
    description: 'Atualize responsável, estágio, próxima ação e resultado. Isso alimenta a fila do dia, os indicadores e o aprendizado do sistema sem criar uma planilha paralela.',
    popoverSide: 'bottom', popoverAlign: 'center',
  },
  {
    id: 'crm-operate', chapter: 'Vendendo', targetRoute: '/crm/operacao', elementSelector: null,
    title: 'Trabalhe várias oportunidades de uma vez',
    description: 'Na operação da carteira você pode filtrar, salvar visões, criar tarefas, aplicar tags, mover estágio e iniciar follow-ups em lote. O sistema mostra uma prévia antes de alterações em massa.',
  },
  {
    id: 'reports', chapter: 'Melhorando', targetRoute: '/relatorios', elementSelector: '[data-tour="relatorios-header"]',
    title: 'Resultados para decidir onde insistir',
    description: 'Veja conversão, atividade, regiões, campanhas e desempenho do time. Filtros se combinam entre si; use-os para responder perguntas concretas, como “qual campanha trouxe reuniões neste período?”.',
    popoverSide: 'bottom', popoverAlign: 'start', analystOnly: true,
  },
  {
    id: 'learning', chapter: 'Melhorando', targetRoute: '/inteligencia-comercial', elementSelector: null,
    title: 'Melhorias da IA sempre passam por pessoas',
    description: 'Feedbacks e resultados reais podem sugerir ajustes, mas o sistema não muda a forma de pontuar sozinho. A gestão revisa evidências, aprova uma versão e pode voltar para a anterior se necessário.',
    analystOnly: true,
  },
  {
    id: 'radar', chapter: 'Melhorando', targetRoute: '/monitoramento', elementSelector: null,
    title: 'Sinais e oportunidades que mudaram',
    description: 'O radar ajuda a perceber fatos novos e oportunidades que merecem revisão. Ele é apoio para priorização, não uma prova automática de que a empresa vai comprar.',
    analystOnly: true,
  },
  {
    id: 'data-quality', chapter: 'Melhorando', targetRoute: '/data-health', elementSelector: null,
    title: 'Qualidade dos dados',
    description: 'Use esta área quando contatos, cadastros ou fontes parecerem incompletos. Dados melhores significam menos tempo perdido e menos confiança indevida em uma pontuação.',
    analystOnly: true,
  },
  {
    id: 'offer-strategies', chapter: 'Configuração', targetRoute: '/configuracoes/vertentes', elementSelector: '[data-tour="vertentes-header"]',
    title: 'O que vendemos',
    description: 'Aqui ficam as estratégias que dizem ao sistema como reconhecer um bom cliente para cada serviço. Gestores podem revisar e adaptar critérios sem alterar o motor geral de prospecção.',
    popoverSide: 'bottom', popoverAlign: 'start',
  },
  {
    id: 'integrations', chapter: 'Configuração', targetRoute: '/integracoes', elementSelector: null,
    title: 'Integrações',
    description: 'Conexões com outros sistemas ficam separadas por workspace. Só habilite o que a equipe realmente usa e valide a conexão antes de depender dela na operação.',
    analystOnly: true,
  },
  {
    id: 'settings-profile', chapter: 'Configuração', targetRoute: '/configuracoes', elementSelector: '[data-tour="configuracoes-perfil"]',
    title: 'Preferências e acesso',
    description: 'Configurações pessoais, equipe, limites e comportamento da operação ficam aqui. O que aparece para você depende do seu papel no workspace.',
    popoverSide: 'bottom', popoverAlign: 'start',
  },
  {
    id: 'settings-connections', chapter: 'Configuração', targetRoute: '/configuracoes', elementSelector: '[data-tour="configuracoes-chaves"]',
    title: 'Teste as conexões antes de usar',
    description: 'Administradores podem salvar as chaves da equipe e usar “Testar conexões”. A tela confirma se busca de empresas e IA estão prontas sem mostrar a chave salva.',
    popoverSide: 'bottom', popoverAlign: 'start',
  },
  {
    id: 'help', chapter: 'Configuração', targetRoute: '/ajuda', elementSelector: null,
    title: 'Ajuda e tutorial sempre disponíveis',
    description: 'A Central de ajuda resume o fluxo diário, responde dúvidas e permite começar ou continuar este tutorial. Você também pode reabri-lo pelo menu do seu perfil ou pelas Configurações.',
  },
  {
    id: 'finish', chapter: 'Configuração', targetRoute: '/ajuda', elementSelector: null,
    title: 'Pronto para começar',
    description: 'Fluxo recomendado: descreva o que quer vender → revise os leads encontrados → trabalhe a fila do dia → registre o que aconteceu no funil → use os resultados e feedbacks para melhorar. Se ficar em dúvida, volte para Minha carteira.',
  },
];
