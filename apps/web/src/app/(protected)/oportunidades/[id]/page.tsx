'use client';

import { use } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ArrowLeft, Phone, Mail, MapPin, Calendar, Globe, Loader2, Copy, UserPlus, ShieldCheck, ShieldAlert, Trophy, MessageCircle, Save, Sparkles } from 'lucide-react';
import { LinkedInIcon } from '@/components/ui/linkedin-icon';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { whatsAppLink } from '@/lib/utils';
import { useLead, useUpdateLeadStatus, useGenerateMessages, useEnrichContacts, useRegisterConversion, useUpdateLead } from '@/hooks/use-api';
import { CadencePanel } from '@/components/oportunidades/cadence-panel';
import { EvidenceCard } from '@/components/oportunidades/evidence-card';
import { LeadPitchTab } from '@/components/oportunidades/lead-pitch';
import { NegotiationControl } from '@/components/oportunidades/negotiation-control';
import { PostSaleControl } from '@/components/oportunidades/post-sale-control';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import { OutreachMessages } from '@/types/index';
import { useState } from 'react';

const primaryNeedLabels: Record<string, string> = {
  SECURITY_FIX: 'Problemas de segurança',
  MODERN_WEBSITE: 'Site desatualizado',
  PERFORMANCE: 'Site lento',
  SEO: 'Problemas de visibilidade',
  LGPD: 'Adequação LGPD',
  NONE: 'Sem necessidade identificada',
};

const priorityBadgeConfig: Record<string, { label: string; color: string; emoji: string }> = {
  HOT: { label: 'Quente', color: 'bg-red-100 text-red-700', emoji: '🔥' },
  WARM: { label: 'Morno', color: 'bg-amber-100 text-amber-700', emoji: '🌤️' },
  COLD: { label: 'Frio', color: 'bg-sky-100 text-sky-700', emoji: '❄️' },
};

function formatPrimaryNeed(value?: string): string {
  if (!value) return 'Sem necessidade identificada';
  return primaryNeedLabels[value] || value;
}

const statusLabels: Record<string, string> = {
  NOVO: 'Novo',
  ANALISADO: 'Analisado',
  QUALIFICADO: 'Apto para contato',
  DESQUALIFICADO: 'Desqualificado',
  CONTATADO: 'Contatado',
  RESPONDIDO: 'Respondeu',
  REUNIAO_MARCADA: 'Reunião marcada',
  REUNIAO_FEITA: 'Reunião realizada',
  PROPOSTA_ENVIADA: 'Proposta enviada',
  PERDIDO: 'Perdido',
};

const negotiationStatuses = new Set([
  'RESPONDIDO',
  'REUNIAO_MARCADA',
  'REUNIAO_FEITA',
  'PROPOSTA_ENVIADA',
]);

const activityLabels: Record<string, string> = {
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
};

function FollowUpCard({ lead }: { lead: NonNullable<ReturnType<typeof useLead>['data']> }) {
  const updateLead = useUpdateLead();
  const [draftNotes, setDraftNotes] = useState(lead.notes ?? '');
  const [draftWhatsapp, setDraftWhatsapp] = useState(lead.whatsapp ?? '');
  const [draftNextAction, setDraftNextAction] = useState(
    lead.next_action_at ? lead.next_action_at.slice(0, 16) : ''
  );

  const saveFollowUp = () => {
    updateLead.mutate(
      {
        id: lead.id,
        data: {
          notes: draftNotes,
          whatsapp: draftWhatsapp || undefined,
          next_action_at: draftNextAction ? new Date(draftNextAction).toISOString() : null,
        },
      },
      {
        onSuccess: () => toast.success('Acompanhamento salvo.'),
        onError: (err) => toast.error(err instanceof Error ? err.message : 'Erro ao salvar acompanhamento.'),
      }
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Acompanhamento</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <label htmlFor="lead-whatsapp" className="text-sm font-medium">
              WhatsApp
            </label>
            <Input
              id="lead-whatsapp"
              placeholder="(16) 99999-9999"
              value={draftWhatsapp}
              onChange={(e) => setDraftWhatsapp(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="lead-next-action" className="text-sm font-medium">
              Próxima ação
            </label>
            <Input
              id="lead-next-action"
              type="datetime-local"
              value={draftNextAction}
              onChange={(e) => setDraftNextAction(e.target.value)}
            />
          </div>
        </div>
        <div className="space-y-2">
          <label htmlFor="lead-notes" className="text-sm font-medium">
            Notas
          </label>
          <Textarea
            id="lead-notes"
            rows={3}
            placeholder="Contexto da conversa, objeções, próximos passos..."
            value={draftNotes}
            onChange={(e) => setDraftNotes(e.target.value)}
          />
        </div>
        <div className="flex items-center justify-end">
          <Button size="sm" onClick={saveFollowUp} disabled={updateLead.isPending}>
            {updateLead.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Salvar acompanhamento
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function LeadDetailPage(props: { params: Promise<{ id: string }> }) {
  const params = use(props.params);
  const router = useRouter();
  const { data: lead, isLoading } = useLead(params.id);
  const updateStatus = useUpdateLeadStatus();
  const generateMessagesMutation = useGenerateMessages();
  const enrichContacts = useEnrichContacts();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [generatedMessages, setGeneratedMessages] = useState<OutreachMessages | null>(null);
  const [selectedChannel] = useState<"EMAIL" | "WHATSAPP">("EMAIL");
  const [convOpen, setConvOpen] = useState(false);
  const [convService, setConvService] = useState('');
  const [convValue, setConvValue] = useState('');
  const [convNotes, setConvNotes] = useState('');
  const registerConversion = useRegisterConversion();

  const copyToClipboard = (text: string, message: string) => {
    navigator.clipboard.writeText(text);
    toast.success(message);
  };

  const handleOpenMessagesModal = async () => {
    if (!lead) return;
    setIsModalOpen(true);
    if (!generatedMessages) {
      try {
        const msgs = await generateMessagesMutation.mutateAsync({ id: lead.id });
        setGeneratedMessages(msgs);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Falha ao gerar mensagens com IA.');
      }
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!lead) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Lead não encontrado</p>
        <Link href="/oportunidades">
          <Button variant="link" className="mt-4">Voltar para oportunidades</Button>
        </Link>
      </div>
    );
  }

  const enrichment = lead.enrichment;
  const securityIssues = enrichment?.security_issues || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <Link href="/oportunidades">
          <Button variant="ghost" size="icon" className="h-10 w-10 shrink-0">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-2xl font-bold tracking-tight">{lead.company_name}</h2>
            <Badge className="bg-emerald-100 text-emerald-700 text-lg">{lead.qualification_score}</Badge>
            {lead.priority && priorityBadgeConfig[lead.priority] && (
              <Badge className={priorityBadgeConfig[lead.priority].color}>
                <span className="mr-1">{priorityBadgeConfig[lead.priority].emoji}</span>
                {priorityBadgeConfig[lead.priority].label}
              </Badge>
            )}
          </div>
          <p className="text-muted-foreground">{lead.category || 'Sem categoria'} • {lead.city || 'Não informado'}{lead.state ? `, ${lead.state}` : ''}</p>
        </div>
        <div className="flex items-center gap-2">
          {whatsAppLink(lead.whatsapp || lead.phone) && (
            <a
              href={whatsAppLink(lead.whatsapp || lead.phone) as string}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-10 items-center gap-2 rounded-md border border-input bg-background px-4 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              <MessageCircle className="h-4 w-4 text-emerald-600" />
              WhatsApp
            </a>
          )}
          <Button className="h-10" onClick={handleOpenMessagesModal} disabled={generateMessagesMutation.isPending}>
            {generateMessagesMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Mail className="mr-2 h-4 w-4" />
            )}
            Gerar/Enviar mensagem
          </Button>
        </div>
      </div>

      {/* Highlight Card: Gancho Recomendado */}
      {lead.pitch_angle && (
        <Card className="border-sidebar-border bg-gradient-to-r from-sidebar/95 to-sidebar text-sidebar-foreground shadow-sm">
          <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-sidebar-primary" />
                <span className="text-xs font-semibold uppercase tracking-wider text-sidebar-primary">
                  Gancho de Abordagem Sugerido
                </span>
              </div>
              <p className="text-sm font-medium leading-relaxed text-sidebar-foreground">
                &ldquo;{lead.pitch_angle}&rdquo;
              </p>
              {lead.suggested_subject && (
                <p className="text-xs text-sidebar-foreground/60">
                  Assunto de e-mail recomendado: <strong className="text-sidebar-foreground">{lead.suggested_subject}</strong>
                </p>
              )}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="shrink-0 border-sidebar-border bg-sidebar-accent text-sidebar-foreground hover:bg-sidebar-primary hover:text-sidebar-primary-foreground"
              onClick={() => copyToClipboard(lead.pitch_angle || '', 'Gancho copiado!')}
            >
              <Copy className="mr-1.5 h-3.5 w-3.5" />
              Copiar Gancho
            </Button>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="h-10">
          <TabsTrigger value="overview" className="h-9">Dados gerais</TabsTrigger>
          <TabsTrigger value="pitch" className="h-9">Pitch One-Pager</TabsTrigger>
          <TabsTrigger value="evidence" className="h-9">Evidências</TabsTrigger>
          <TabsTrigger value="technical" className="h-9">Análise do site</TabsTrigger>
          <TabsTrigger value="contacts" className="h-9">Contatos</TabsTrigger>
          <TabsTrigger value="cadence" className="h-9">Cadência</TabsTrigger>
          <TabsTrigger value="activities" className="h-9">Atividades</TabsTrigger>
          <TabsTrigger value="actions" className="h-9">Ações</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Informações do Lead</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {lead.website && (
                  <div className="flex items-center gap-3">
                    <Globe className="h-4 w-4 text-muted-foreground" />
                    <a href={lead.website} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                      {lead.website}
                    </a>
                  </div>
                )}
                {lead.phone && (
                  <div className="flex items-center gap-3">
                    <Phone className="h-4 w-4 text-muted-foreground" />
                    <span>{lead.phone}</span>
                  </div>
                )}
                {lead.email && (
                  <div className="flex items-center gap-3">
                    <Mail className="h-4 w-4 text-muted-foreground" />
                    <span>{lead.email}</span>
                  </div>
                )}
                <div className="flex items-center gap-3">
                  <MapPin className="h-4 w-4 text-muted-foreground" />
                  <span>{lead.city || 'Não informado'}{lead.state ? `, ${lead.state}` : ''}{lead.country ? `, ${lead.country}` : ''}</span>
                </div>
                <div className="flex items-center gap-3">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <span>Encontrado em {new Date(lead.created_at).toLocaleDateString('pt-BR')}</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Aptidão</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Pontuação:</span>
                  <Badge className="bg-emerald-100 text-emerald-700 text-lg">{lead.qualification_score}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Necessidade:</span>
                  <Badge variant="outline">{formatPrimaryNeed(lead.primary_need)}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Status:</span>
                  <Badge>{statusLabels[lead.status] || lead.status}</Badge>
                </div>
                {lead.qualification_reason && (
                  <div className="pt-2">
                    <p className="text-sm text-muted-foreground">Por que este lead é uma oportunidade:</p>
                    <p className="text-sm mt-1">{lead.qualification_reason}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {(lead.pitch_angle || lead.suggested_subject) && (
            <Card>
              <CardHeader>
                <CardTitle>Pitch de Abordagem</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {lead.pitch_angle && (
                  <div>
                    <p className="text-sm text-muted-foreground">Gancho principal:</p>
                    <p className="text-sm mt-1">{lead.pitch_angle}</p>
                  </div>
                )}
                {lead.suggested_subject && (
                  <div>
                    <p className="text-sm text-muted-foreground">Sugestão de assunto para e-mail:</p>
                    <p className="text-sm mt-1 italic">&ldquo;{lead.suggested_subject}&rdquo;</p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          <FollowUpCard lead={lead} />
        </TabsContent>

        <TabsContent value="pitch" className="space-y-4">
          <LeadPitchTab leadId={lead.id} />
        </TabsContent>

        <TabsContent value="evidence" className="space-y-4">
          <EvidenceCard
            score={lead.qualification_score}
            priority={lead.priority}
            priorityReasoning={lead.priority_reasoning}
            executiveSummary={lead.executive_summary}
            scoreFactors={lead.score_factors}
            evidence={lead.evidence}
          />
        </TabsContent>

        <TabsContent value="technical" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Análise do Site</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {enrichment ? (
                <>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="text-center">
                      <p className="text-2xl">{enrichment.ssl_ok ? '✅' : '❌'}</p>
                      <p className="text-sm font-medium mt-1">Certificado SSL</p>
                      <p className="text-xs text-muted-foreground">{enrichment.ssl_ok ? 'Configurado' : 'Não configurado'}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl">⚙️</p>
                      <p className="text-sm font-medium mt-1">Tecnologia</p>
                      <p className="text-xs text-muted-foreground">{enrichment.cms || 'Não identificada'}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl">{enrichment.load_time_ms && enrichment.load_time_ms > 3000 ? '🐢' : '⚡'}</p>
                      <p className="text-sm font-medium mt-1">Velocidade</p>
                      <p className="text-xs text-muted-foreground">{enrichment.load_time_ms ? `${(enrichment.load_time_ms / 1000).toFixed(1)}s` : 'Não medido'}</p>
                    </div>
                  </div>
                  {securityIssues.length > 0 && (
                    <div>
                      <h4 className="mb-3 font-medium">Problemas encontrados</h4>
                      <div className="space-y-2">
                        {securityIssues.map((issue: string, index: number) => (
                          <div key={index} className="flex items-start gap-3 rounded-lg border p-3">
                            <div className="text-sm">{issue}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">Nenhuma análise técnica disponível</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="contacts" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle>Contatos de decisores</CardTitle>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  enrichContacts.mutate({ leadId: lead.id }, {
                    onSuccess: () => toast.success('Decisores enriquecidos (e-mail/LinkedIn).'),
                    onError: (err) => toast.error(err instanceof Error ? err.message : 'Erro ao enriquecer contatos.'),
                  });
                }}
                disabled={enrichContacts.isPending}
              >
                {enrichContacts.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <UserPlus className="mr-2 h-4 w-4" aria-hidden="true" />
                )}
                Enriquecer decisores
              </Button>
            </CardHeader>
            <CardContent>
              {lead.contacts && lead.contacts.length > 0 ? (
                <div className="space-y-3">
                  {lead.contacts.map((contact) => (
                    <div key={contact.id} className="rounded-lg border p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <p className="font-medium">{contact.name}</p>
                            {contact.is_primary && (
                              <Badge variant="secondary" className="text-[10px] font-normal">Principal</Badge>
                            )}
                          </div>
                          {contact.role_label && (
                            <p className="text-xs text-muted-foreground">{contact.role_label}</p>
                          )}
                        </div>
                        {contact.confidence != null && (
                          <Badge className={contact.confidence >= 50 ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}>
                            Confiança {contact.confidence}
                          </Badge>
                        )}
                      </div>

                      <div className="mt-3 space-y-2 text-sm">
                        {contact.email && (
                          <div className="flex items-center gap-2">
                            <Mail className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                            <a href={`mailto:${contact.email}`} className="text-primary hover:underline">{contact.email}</a>
                            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => copyToClipboard(contact.email || '', 'E-mail copiado.')} aria-label="Copiar e-mail">
                              <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                            </Button>
                            {contact.email_verified ? (
                              <Badge variant="outline" className="text-[10px] font-normal gap-1">
                                <ShieldCheck className="h-3 w-3 text-emerald-500" aria-hidden="true" />
                                E-mail verificado
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="text-[10px] font-normal gap-1">
                                <ShieldAlert className="h-3 w-3 text-amber-500" aria-hidden="true" />
                                Não verificado
                              </Badge>
                            )}
                          </div>
                        )}
                        {contact.phone && (
                          <div className="flex items-center gap-2">
                            <Phone className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                            <span>{contact.phone}</span>
                          </div>
                        )}
                        {contact.linkedin_url ? (
                          <div className="flex items-center gap-2">
                            <LinkedInIcon className="h-4 w-4 text-primary" />
                            <a
                              href={contact.linkedin_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-primary hover:underline truncate max-w-[280px]"
                            >
                              {contact.linkedin_url}
                            </a>
                            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => copyToClipboard(contact.linkedin_url || '', 'Link do LinkedIn copiado.')} aria-label="Copiar LinkedIn">
                              <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                            </Button>
                            {contact.linkedin_confidence != null && contact.linkedin_confidence < 50 ? (
                              <Badge variant="outline" className="text-[10px] font-normal gap-1">
                                <ShieldAlert className="h-3 w-3 text-amber-500" aria-hidden="true" />
                                Não validado
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="text-[10px] font-normal gap-1">
                                <ShieldCheck className="h-3 w-3 text-emerald-500" aria-hidden="true" />
                                Perfil validado
                              </Badge>
                            )}
                          </div>
                        ) : (
                          <p className="flex items-center gap-2 text-xs text-muted-foreground">
                            <LinkedInIcon className="h-4 w-4" />
                            LinkedIn não encontrado — use &quot;Enriquecer decisores&quot;.
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3 py-10 text-center">
                  <UserPlus className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
                  <p className="text-sm text-muted-foreground max-w-sm">
                    Nenhum contato de decisor cadastrado ainda. Use &quot;Enriquecer decisores&quot; para buscar
                    sócios via Receita Federal e enriquecer com e-mail e LinkedIn (busca passiva).
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="cadence" className="space-y-4">
          <CadencePanel leadId={lead.id} />
        </TabsContent>

        <TabsContent value="activities" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Trilha de atividades</CardTitle>
            </CardHeader>
            <CardContent>
              {lead.activities && lead.activities.length > 0 ? (
                <ol className="relative space-y-4 border-l pl-6">
                  {lead.activities.map((activity) => (
                    <li key={activity.id} className="relative">
                      <span className="absolute -left-[31px] flex h-4 w-4 items-center justify-center rounded-full border-2 border-background bg-primary" />
                      <div className="flex flex-wrap items-center gap-2 text-sm">
                        <span className="font-medium">{activityLabels[activity.action] || activity.action}</span>
                        {activity.user_name && (
                          <span className="text-xs text-muted-foreground">por {activity.user_name}</span>
                        )}
                        <span className="ml-auto text-xs text-muted-foreground">
                          {new Date(activity.created_at).toLocaleString('pt-BR')}
                        </span>
                      </div>
                      {activity.status_from && activity.status_to && (
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {statusLabels[activity.status_from] || activity.status_from} → {statusLabels[activity.status_to] || activity.status_to}
                        </p>
                      )}
                      {activity.detail && (
                        <p className="mt-0.5 text-xs text-muted-foreground">{activity.detail}</p>
                      )}
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Nenhuma atividade registrada ainda.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="actions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Próximas Ações</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button
                className="w-full h-11"
                onClick={async () => {
                  try {
                    const result = await generateMessagesMutation.mutateAsync({ id: lead.id, channel: selectedChannel });
                    setGeneratedMessages(result);
                    setIsModalOpen(true);
                  } catch (error) {
                    toast.error("Falha ao gerar mensagem.");
                    console.error("Erro ao gerar mensagem:", error);
                  }
                }}
                disabled={generateMessagesMutation.isPending}
              >
                {generateMessagesMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Mail className="mr-2 h-4 w-4" />
                )}
                Gerar mensagem personalizada
              </Button>
              <Button
                variant="outline"
                className="w-full h-11"
                onClick={() =>
                  updateStatus.mutate(
                    { id: params.id, status: 'CONTATADO' },
                    { onSuccess: () => router.push('/vendas') }
                  )
                }
                disabled={updateStatus.isPending}
              >
                {updateStatus.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Phone className="mr-2 h-4 w-4" />
                )}
                Registrar contato realizado
              </Button>
              <Button
                variant="outline"
                className="w-full h-11"
                onClick={() => setConvOpen(true)}
              >
                <Trophy className="mr-2 h-4 w-4 text-emerald-600" />
                Registrar conversão
              </Button>
              {negotiationStatuses.has(lead.status ?? '') && (
                <NegotiationControl
                  key={lead.id}
                  leadId={lead.id}
                  initialStage={lead.negotiation_stage}
                  initialOutcome={lead.contract_outcome}
                />
              )}
              {(lead.contract_outcome === 'APROVADO' || lead.post_sale_contacted_at) && (
                <PostSaleControl key={`pos-${lead.id}`} leadId={lead.id} />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={convOpen} onOpenChange={setConvOpen}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>Registrar conversão</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="convService" className="text-sm font-medium">
                Serviço vendido
              </label>
              <Input
                id="convService"
                value={convService}
                onChange={(e) => setConvService(e.target.value)}
                placeholder="Ex.: Landing page, site institucional..."
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="convValue" className="text-sm font-medium">
                Valor do contrato (R$)
              </label>
              <Input
                id="convValue"
                type="number"
                min="0"
                step="0.01"
                value={convValue}
                onChange={(e) => setConvValue(e.target.value)}
                placeholder="0,00"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="convNotes" className="text-sm font-medium">
                Observações
              </label>
              <Textarea
                id="convNotes"
                value={convNotes}
                onChange={(e) => setConvNotes(e.target.value)}
                placeholder="Como fechou? Contexto do negócio..."
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConvOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={async () => {
                try {
                  const value = convValue.replace(',', '.');
                  await registerConversion.mutateAsync({
                    id: lead.id,
                    data: {
                      service_sold: convService || undefined,
                      contract_value: value ? Number(value) : undefined,
                      notes: convNotes || undefined,
                    },
                  });
                  toast.success('Conversão registrada.');
                  setConvOpen(false);
                  setConvService('');
                  setConvValue('');
                  setConvNotes('');
                } catch (error) {
                  toast.error(error instanceof Error ? error.message : 'Erro ao registrar conversão.');
                }
              }}
              disabled={registerConversion.isPending}
            >
              {registerConversion.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Trophy className="mr-2 h-4 w-4" />
              )}
              Registrar conversão
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="sm:max-w-[700px]">
          <DialogHeader>
            <DialogTitle>Mensagem gerada para {lead.company_name}</DialogTitle>
          </DialogHeader>
          {generateMessagesMutation.isPending ? (
            <div className="flex flex-col items-center justify-center py-12 space-y-3">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">
                Gerando sequência personalizada de outreach com IA...
              </p>
            </div>
          ) : generatedMessages ? (
            <Tabs defaultValue="email" className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="email">E-mail</TabsTrigger>
                <TabsTrigger value="followups">Follow-ups</TabsTrigger>
                <TabsTrigger value="whatsapp">WhatsApp</TabsTrigger>
              </TabsList>
              <TabsContent value="email" className="space-y-4 pt-4">
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Assunto:</p>
                  <div className="flex items-center space-x-2">
                    <Input value={generatedMessages.subject} readOnly />
                    <Button variant="outline" size="sm" onClick={() => copyToClipboard(generatedMessages.subject, 'Assunto copiado!')}>
                      Copiar
                    </Button>
                  </div>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Corpo da mensagem:</p>
                  <div className="flex items-center space-x-2">
                    <Textarea value={generatedMessages.body_opening} readOnly rows={8} />
                    <Button variant="outline" size="sm" onClick={() => copyToClipboard(generatedMessages.body_opening, 'Corpo do e-mail copiado!')}>
                      Copiar
                    </Button>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">Gerado com base nas evidências reais do lead</p>
              </TabsContent>
              <TabsContent value="followups" className="space-y-4 pt-4">
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Follow-up 1 — Dia 3:</p>
                  <Textarea value={generatedMessages.followup_1} readOnly rows={5} />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Follow-up 2 — Dia 7:</p>
                  <Textarea value={generatedMessages.followup_2} readOnly rows={5} />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Encerramento — Dia 14:</p>
                  <Textarea value={generatedMessages.closing} readOnly rows={3} />
                </div>
              </TabsContent>
              <TabsContent value="whatsapp" className="space-y-4 pt-4">
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Mensagem para WhatsApp:</p>
                  <Textarea value={generatedMessages.whatsapp_short} readOnly rows={6} />
                  <Badge className="mt-2">Versão curta para WhatsApp Business</Badge>
                </div>
                {whatsAppLink(lead.whatsapp || lead.phone, generatedMessages.whatsapp_short) ? (
                  <a
                    href={whatsAppLink(lead.whatsapp || lead.phone, generatedMessages.whatsapp_short) as string}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-emerald-600 px-4 text-sm font-medium text-white shadow-sm transition-colors hover:bg-emerald-700"
                  >
                    <MessageCircle className="h-4 w-4" />
                    Abrir no WhatsApp
                  </a>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Adicione um WhatsApp no lead (aba Dados gerais) para abrir a conversa direto.
                  </p>
                )}
              </TabsContent>
            </Tabs>
          ) : (
            <div className="text-center py-6">
              <p className="text-sm text-muted-foreground mb-4">Nenhuma mensagem gerada ainda.</p>
              <Button onClick={handleOpenMessagesModal} disabled={generateMessagesMutation.isPending}>
                <Sparkles className="mr-2 h-4 w-4" />
                Gerar Mensagem com IA
              </Button>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsModalOpen(false)}>Fechar</Button>
            <Button
              onClick={() =>
                copyToClipboard(
                  `${generatedMessages?.subject}\n\n${generatedMessages?.body_opening}`,
                  'E-mail completo copiado!'
                )
              }
              disabled={!generatedMessages}
            >
              Copiar e-mail completo
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}