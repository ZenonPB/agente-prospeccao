# Interface Web — Visão e Requisitos

> Este documento descreve o que o usuário vê e faz na interface web da plataforma.
> É a referência de UX, fluxo e funcionalidades para o desenvolvimento do frontend.
> Leia junto com architecture.md para entender a stack técnica.

---

## Princípios de Design

Antes de qualquer funcionalidade, estes princípios guiam todas as decisões de interface:

- **UX impecável acima de tudo** — qualquer membro novo, seja trainee ou não,
  deve conseguir usar o sistema sem treinamento. Se precisar de explicação,
  a interface falhou.
- **Clean e funcional** — sem poluição visual. Cada elemento na tela existe
  por um motivo. Informação densa mas organizada.
- **Responsivo** — funciona bem em desktop, tablet e mobile.
- **Semântico** — HTML correto, acessível, navegável por teclado.
- **Agradável** — usar o sistema deve ser uma boa experiência, não uma obrigação.
  Microinterações, feedback visual, estados de loading bem feitos.
- **Feedback sempre** — o usuário nunca fica sem saber o que está acontecendo.
  Todo processo longo tem indicador de progresso. Todo erro tem mensagem clara.

---

## Stack Frontend

- **Next.js** — framework principal (App Router)
- **NextAuth.js** — autenticação (Google OAuth + GitHub)
- **Tailwind CSS** — estilização
- **shadcn/ui** — componentes base (acessíveis, customizáveis)
- **Recharts** — gráficos do dashboard
- **WebSockets ou Server-Sent Events** — pipeline em tempo real

---

## Estrutura Geral da Interface
┌─────────────────────────────────────────────┐
│  Logo        [Notificações]  [Avatar/Perfil] │  ← Header
├──────────┬──────────────────────────────────┤
│          │                                  │
│  Menu    │   Conteúdo principal             │
│  Lateral │                                  │
│          │                                  │
│  →  Dashboard                               │
│  →  Campanhas                               │
│  →  Oportunidades                           │
│  →  Pipeline                                │
│  →  Configurações                           │
│          │                                  │
└──────────┴──────────────────────────────────┘

---

## Telas e Funcionalidades

### 1. Login

Tela limpa com duas opções:
- Entrar com Google
- Entrar com GitHub

Sem formulário de cadastro manual no MVP — acesso controlado pelos admins.

---

### 2. Dashboard (tela inicial)

Primeira coisa que o usuário vê ao logar. Responde à pergunta:
**"O que está acontecendo e o que devo fazer agora?"**

**Métricas em destaque (cards no topo):**
- Total de leads coletados
- Leads qualificados (score >= 60)
- Leads contatados
- Reuniões marcadas
- Taxa de resposta geral

**Gráficos:**
- Funil de conversão — quantos leads em cada status (barra horizontal ou funil visual)
- Leads por campanha — quais campanhas estão gerando mais resultado
- Score médio por segmento — quais nichos têm mais oportunidade
- Atividade recente — linha do tempo de ações dos últimos 7 dias

**Seção "O que fazer agora":**
Lista curta de ações sugeridas, gerada automaticamente:
- "Você tem 12 leads qualificados aguardando contato"
- "3 leads não responderam há 7 dias — hora do follow-up"
- "Campanha X está há 5 dias sem novos leads — considere expandir a região"

**Seção de campanhas ativas:**
Cards resumidos das campanhas em andamento com progresso.

---

### 3. Campanhas

Central de controle das buscas de leads. O usuário não faz buscas pontuais —
ele cria campanhas que ficam salvas, acumulam leads e podem ser gerenciadas.

**Lista de campanhas:**
- Cards com nome, segmento, região, status, total de leads, score médio
- Filtros: ativa, pausada, concluída, arquivada
- Botão de criar nova campanha em destaque

**Criar / Editar campanha:**

Formulário guiado em etapas (não um formulário longo de uma vez):

*Etapa 1 — O que você quer vender?*
- Serviço-alvo (campo livre + sugestões): "Landing page", "ERP", "App mobile",
  "Sistema de gestão", "Projeto de usinagem"...
- Descrição do serviço (para a IA entender o contexto e gerar mensagens certas)

*Etapa 2 — Para quem?*
- Segmento-alvo (campo livre + sugestões): "Restaurantes", "Clínicas",
  "Academias", "Indústrias de usinagem"...
- **Sugestão da IA:** botão "Me sugira segmentos" — a IA analisa o histórico
  de conversões e sugere nichos com maior potencial que ainda não foram prospectados

*Etapa 3 — Onde?*
- Cidade e estado
- Raio de busca (ex: 10km, 50km, ou cidade específica)
- Opção de expansão gradual (começar em Araraquara, depois expandir para região)

*Etapa 4 — Revisão e confirmação*
- Resumo da campanha antes de salvar
- Estimativa de leads disponíveis (baseada em buscas anteriores similares)

**Ações em uma campanha existente:**
- Pausar / Reativar
- Duplicar para outra cidade
- Ver todos os leads dessa campanha
- Iniciar nova rodada de coleta
- Arquivar

---

### 4. Pipeline (processamento em tempo real)

Quando o usuário dispara uma coleta ou enriquecimento, ele é levado para
esta tela (ou um painel lateral abre) mostrando tudo acontecendo ao vivo.

**O que aparece em tempo real:**
✅ Conectado à Google Places API
🔍 Buscando "Restaurantes em Araraquara, SP"...
Encontrados 29 estabelecimentos
📋 Processando leads...
✅ Tijuca Restaurante & Bar — coletado
✅ Restaurante Pau Seco — coletado
⏳ KIBELANCHE — processando...
🔒 Iniciando enriquecimento técnico...
✅ Tijuca Restaurante & Bar
SSL: ✅ OK
Headers de segurança: ⚠️ 2 ausentes
Arquivos expostos: ❌ /robots.txt acessível
✅ Restaurante Pau Seco
SSL: ❌ Sem HTTPS
...
🤖 Scoring com IA...
✅ Tijuca Restaurante & Bar — Score: 74 (QUALIFICADO)
✅ Restaurante Pau Seco — Score: 88 (QUALIFICADO)
...
✅ Pipeline finalizado
12 leads coletados | 9 qualificados | 3 desqualificados
[Ver oportunidades →]

- Log rolável em tempo real
- Barra de progresso geral no topo
- Possibilidade de cancelar o pipeline
- Ao finalizar, botão direto para a tela de Oportunidades

---

### 5. Oportunidades

Lista de todos os leads qualificados, onde o usuário decide quem abordar.

**Lista principal (paginada — 20 por página):**

Cada card de lead mostra:
- Nome da empresa e segmento
- Score em destaque (cor: verde > 80, amarelo 60-79)
- Necessidade primária (SECURITY_FIX, MODERN_WEBSITE, etc.)
- Cidade e campanha de origem
- Site e telefone
- Status atual
- Data de coleta

**Filtros e ordenação:**
- Por campanha
- Por score (maior primeiro por padrão)
- Por status
- Por segmento
- Por data
- Busca por nome

**Detalhe do lead (abre em painel lateral ou página própria):**

*Aba Visão Geral:*
- Todos os dados coletados
- Score e justificativa completa em linguagem simples
- Lista de issues encontrados com severidade

*Aba Análise Técnica:*
- Relatório completo do enriquecimento
- SSL, headers, CMS detectado, arquivos expostos
- Tempo de carregamento

*Aba Contatos:*
- E-mails de decisores encontrados (Hunter.io — fase 4)
- Nome, cargo, confidence score de cada contato
- LinkedIn quando disponível

*Aba Ações:*

**Gerar Pitch** — botão que abre um modal com:
- Mensagem personalizada gerada pela IA (Llama 3.3 70B)
- Cita problemas reais encontrados na análise
- Tom adequado para o segmento
- Botões: Copiar, Regenerar, Editar antes de copiar

**Registrar contato** — marcar que já entrou em contato
(muda status para CONTATADO e move para a tela de Pipeline de Vendas)

---

### 6. Pipeline de Vendas

Gestão dos leads que já estão sendo prospectados ativamente.

**Visão em Kanban** (colunas por status):
CONTATADO | RESPONDIDO | REUNIÃO MARCADA | REUNIÃO FEITA | PROPOSTA ENVIADA

Cada card no Kanban mostra:
- Nome da empresa
- Score original
- Dias desde o primeiro contato
- Próxima ação sugerida

**Detalhe do lead no pipeline:**

*Histórico completo:*
- Linha do tempo de todas as interações
- Mensagens enviadas, respostas recebidas
- Datas de cada etapa

*Follow-up automático:*
- IA sugere mensagem de follow-up baseada no histórico
- Usuário aprova, edita ou rejeita antes de enviar
- Sequência automática: dia 3, dia 7, dia 14

*Ações manuais:*
- Marcar como respondeu
- Agendar reunião (integração Cal.com)
- Marcar reunião como feita
- Enviar proposta
- Marcar como perdido (com motivo)
- Reativar após 90 dias

**Alerta de leads esquecidos:**
Badge vermelho em leads que estão há mais de X dias sem ação.

---

## Fluxo Completo do Usuário
Login
↓
Dashboard — entende o que está acontecendo
↓
Campanhas — cria nova campanha com parâmetros
↓
Pipeline — acompanha coleta + enriquecimento + scoring em tempo real
↓
Oportunidades — revisa leads qualificados, gera pitch, registra contato
↓
Pipeline de Vendas — acompanha negociações, follow-ups, reuniões
↓
Dashboard — métricas atualizadas refletem o trabalho feito

---

## Futuro — Alphamec (Multi-tenant)

> Não implementar agora. Documentado para guiar decisões arquiteturais futuras.

Quando a plataforma for disponibilizada para a Alphamec:

**Por área/setor:**
- Cada área (TI, Engenharia Mecânica, etc.) tem suas próprias campanhas
- Dashboard da liderança agrega todas as áreas
- Métricas por área: leads gerados, taxa de resposta, conversões, valor em contrato

**Por membro:**
- Cada consultor de vendas tem seu perfil
- Dashboard individual: prospecções na semana, leads em andamento, metas
- Ranking de consultores (gamificação opcional)
- Histórico de atividade por membro

**Gestão administrativa:**
- Convidar/remover membros
- Definir áreas e permissões
- Relatórios exportáveis por período

---

## O que NÃO entra no MVP da interface

Para manter o escopo controlado na fase 2:

- Envio de e-mail direto pela interface (fase 3)
- Integração Cal.com (fase 3)
- Enriquecimento de contatos / Hunter.io (fase 4)
- Multi-tenant / Alphamec (fase 6)
- App mobile nativo
- Exportação de relatórios em PDF
- Integração com WhatsApp ou LinkedIn