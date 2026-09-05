'use client';

import { use } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  ArrowLeft,
  Phone,
  Loader2,
  Copy,
  AlertTriangle,
  Trophy,
  MessageCircle,
  Mail,
  Sparkles,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { whatsAppLink } from '@/lib/utils';
import {
  useLead,
  useUpdateLeadStatus,
  useGenerateMessages,
  useRecordWhatsAppClick,
  useUpdateCadenceStep,
  useCreatePlaybook,
  useLeadDuplicates,
  useLeadOpportunities,
} from '@/hooks/use-api';
import { CadencePanel } from '@/components/oportunidades/cadence-panel';
import { EvidenceCard } from '@/components/oportunidades/evidence-card';
import { LeadPitchTab } from '@/components/oportunidades/lead-pitch';
import { NegotiationControl } from '@/components/oportunidades/negotiation-control';
import { PostSaleControl } from '@/components/oportunidades/post-sale-control';
import { LinkedInAssociateDialog } from '@/components/oportunidades/linkedin-associate-dialog';
import { TechnicalTab } from '@/components/oportunidades/technical-tab';
import { ContactsTab } from '@/components/oportunidades/contacts-tab';
import { OverviewTab } from '@/components/oportunidades/overview-tab';
import { ActivitiesTab } from '@/components/oportunidades/activities-tab';
import { ConversionDialog } from '@/components/oportunidades/conversion-dialog';
import { OutreachMessagesModal } from '@/components/oportunidades/outreach-messages-modal';
import { toast } from 'sonner';
import type { ContactItem, OutreachMessages, OutreachVariant } from '@/types/index';
import { useState } from 'react';
import { Reveal } from '@/components/ui/motion';

const priorityBadgeConfig: Record<string, { label: string; color: string; emoji: string }> = {
  HOT: { label: 'Quente', color: 'bg-red-100 text-red-700', emoji: '🔥' },
  WARM: { label: 'Morno', color: 'bg-amber-100 text-amber-700', emoji: '🌤️' },
  COLD: { label: 'Frio', color: 'bg-sky-100 text-sky-700', emoji: '❄️' },
};

const negotiationStatuses = new Set([
  'RESPONDIDO',
  'REUNIAO_MARCADA',
  'REUNIAO_FEITA',
  'PROPOSTA_ENVIADA',
]);

export default function LeadDetailPage(props: { params: Promise<{ id: string }> }) {
  const { id: leadId } = use(props.params);
  const router = useRouter();
  const { data: lead, isLoading } = useLead(leadId);
  const duplicatesQ = useLeadDuplicates(leadId);
  const opportunitiesQ = useLeadOpportunities(leadId);
  const updateStatus = useUpdateLeadStatus();
  const generateMessagesMutation = useGenerateMessages();
  const updateStepMutation = useUpdateCadenceStep();
  const createPlaybookMutation = useCreatePlaybook();
  const recordWhatsApp = useRecordWhatsAppClick();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [generatedMessages, setGeneratedMessages] = useState<OutreachMessages | null>(null);
  const [convOpen, setConvOpen] = useState(false);
  const [associateContact, setAssociateContact] = useState<ContactItem | null>(null);

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

  const handleGenerateVariants = async () => {
    if (!lead) return;
    try {
      const msgs = await generateMessagesMutation.mutateAsync({
        id: lead.id,
        variants: true,
      });
      setGeneratedMessages(msgs);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Falha ao gerar variantes A/B.');
    }
  };

  const applyVariantToStep = async (
    step: 'OPENING' | 'FOLLOWUP_1' | 'FOLLOWUP_2' | 'CLOSING',
    variant: OutreachMessages
  ) => {
    if (!lead) return;
    try {
      await updateStepMutation.mutateAsync({
        id: lead.id,
        step,
        data: {
          variant: (variant as OutreachVariant).label || 'A',
          subject: variant.subject,
          content: step === 'OPENING' ? variant.body_opening : variant[step.toLowerCase() as 'followup_1' | 'followup_2' | 'closing'],
        },
      });
      toast.success(`Etapa ${step} atualizada com variante ${(variant as OutreachVariant).label || 'A'}.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Falha ao aplicar variante.');
    }
  };

  const saveToPlaybook = async (subject: string, body: string) => {
    if (!subject.trim() || !body.trim()) {
      toast.error('Mensagem sem assunto/corpo — nada para salvar.');
      return;
    }
    try {
      await createPlaybookMutation.mutateAsync({
        vertical: lead?.category || undefined,
        subject: subject.trim(),
        body,
      });
      toast.success('Mensagem salva no playbook da organização.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Falha ao salvar no playbook.');
    }
  };

  const handleGenerateFromActions = async () => {
    if (!lead) return;
    try {
      const result = await generateMessagesMutation.mutateAsync({ id: lead.id, channel: 'EMAIL' });
      setGeneratedMessages(result);
      setIsModalOpen(true);
    } catch (error) {
      toast.error('Falha ao gerar mensagem.');
      console.error('Erro ao gerar mensagem:', error);
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

  return (
    <div className="space-y-6">
      {duplicatesQ.data && duplicatesQ.data.count > 0 && (
        <div className="flex items-start gap-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm dark:bg-amber-900/20">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
          <div className="min-w-0 flex-1">
            <p className="font-medium text-amber-800 dark:text-amber-300">
              Possível duplicata ({duplicatesQ.data.count} lead{duplicatesQ.data.count === 1 ? '' : 's'} na mesma organização)
            </p>
            <ul className="mt-1 space-y-0.5 text-amber-700 dark:text-amber-400">
              {duplicatesQ.data.matches.slice(0, 3).map((m) => (
                <li key={m.lead_id} className="flex flex-wrap items-center gap-x-2">
                  <Link
                    href={`/oportunidades/${m.lead_id}`}
                    className="underline-offset-2 hover:underline"
                  >
                    {m.company_name || m.lead_id}
                  </Link>
                  <span className="text-xs">— {m.matched_by.join(', ')}</span>
                </li>
              ))}
              {duplicatesQ.data.count > 3 && (
                <li className="text-xs">+ {duplicatesQ.data.count - 3} outros</li>
              )}
            </ul>
          </div>
        </div>
      )}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <Link href="/oportunidades">
          <Button variant="ghost" size="icon" className="h-11 w-11 shrink-0" aria-label="Voltar para oportunidades">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="break-words text-2xl font-bold tracking-tight">{lead.company_name}</h2>
            <Badge className="bg-emerald-100 text-emerald-700 text-lg">{lead.qualification_score}</Badge>
            {lead.priority && priorityBadgeConfig[lead.priority] && (
              <Badge className={priorityBadgeConfig[lead.priority].color}>
                <span className="mr-1">{priorityBadgeConfig[lead.priority].emoji}</span>
                {priorityBadgeConfig[lead.priority].label}
              </Badge>
            )}
          </div>
          <p className="break-words text-muted-foreground">{lead.category || 'Sem categoria'} • {lead.city || 'Não informado'}{lead.state ? `, ${lead.state}` : ''}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {whatsAppLink(lead.whatsapp || lead.phone) && (
            <Button
              variant="outline"
              className="h-11 gap-2 border-input bg-background font-medium shadow-sm hover:bg-accent hover:text-accent-foreground"
              disabled={recordWhatsApp.isPending}
              onClick={() => {
                recordWhatsApp.mutate(
                  { leadId: lead.id },
                  {
                    onSuccess: (res) => {
                      if (res.whatsapp_url) {
                        window.open(res.whatsapp_url, '_blank');
                        toast.success('WhatsApp acionado e registrado na trilha');
                      }
                    },
                    onError: () => {
                      const fallback = whatsAppLink(lead.whatsapp || lead.phone);
                      if (fallback) window.open(fallback, '_blank');
                    },
                  }
                );
              }}
            >
              {recordWhatsApp.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin text-emerald-600" />
              ) : (
                <MessageCircle className="h-4 w-4 text-emerald-600" />
              )}
              WhatsApp
            </Button>
          )}
          <Button className="h-11" onClick={handleOpenMessagesModal} disabled={generateMessagesMutation.isPending}>
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
        <Reveal delay={60}>
          <Card className="border-sidebar-border bg-gradient-to-r from-sidebar/95 to-sidebar text-sidebar-foreground shadow-sm">
          <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-sidebar-primary" />
                <span className="text-xs font-semibold uppercase tracking-wider text-sidebar-primary">
                  Gancho de Abordagem Sugerido
                </span>
              </div>
              <p className="break-words text-sm font-medium leading-relaxed text-sidebar-foreground">
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
              className="h-11 shrink-0 border-sidebar-border bg-sidebar-accent text-sidebar-foreground hover:bg-sidebar-primary hover:text-sidebar-primary-foreground"
              onClick={() => copyToClipboard(lead.pitch_angle || '', 'Gancho copiado!')}
            >
              <Copy className="mr-1.5 h-3.5 w-3.5" />
              Copiar Gancho
            </Button>
          </CardContent>
        </Card>
        </Reveal>
      )}

      <Tabs defaultValue="overview" className="space-y-4 animate-fade-up stagger-2">
        <TabsList className="h-11 w-full max-w-full justify-start gap-1 overflow-x-auto">
          <TabsTrigger value="overview" className="h-11 shrink-0">Visão Geral</TabsTrigger>
          <TabsTrigger value="offers" className="h-11 shrink-0">Ofertas relacionadas</TabsTrigger>
          <TabsTrigger value="pitch" className="h-11 shrink-0">Resumo para o Vendedor</TabsTrigger>
          <TabsTrigger value="evidence" className="h-11 shrink-0">Por que a IA recomendou</TabsTrigger>
          <TabsTrigger value="technical" className="h-11 shrink-0">Análise da Página</TabsTrigger>
          <TabsTrigger value="contacts" className="h-11 shrink-0">Decisores e Contatos</TabsTrigger>
          <TabsTrigger value="cadence" className="h-11 shrink-0">Passos de Envio</TabsTrigger>
          <TabsTrigger value="activities" className="h-11 shrink-0">Histórico do Cliente</TabsTrigger>
          <TabsTrigger value="actions" className="h-11 shrink-0">Próximas Tarefas</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <OverviewTab lead={lead} />
        </TabsContent>

        <TabsContent value="offers" className="space-y-4">
          <Card>
            <CardContent className="space-y-3 pt-6">
              <div>
                <h3 className="font-semibold">Oportunidades por oferta</h3>
                <p className="text-sm text-muted-foreground">
                  Correspondências calculadas pelo perfil comercial e suas evidências.
                </p>
              </div>
              {opportunitiesQ.isLoading && <p className="text-sm text-muted-foreground">Carregando ofertas…</p>}
              {!opportunitiesQ.isLoading && (opportunitiesQ.data?.oportunidades ?? []).length === 0 && (
                <p className="text-sm text-muted-foreground">Nenhuma oferta relacionada foi registrada.</p>
              )}
              <div className="grid gap-3 sm:grid-cols-2">
                {(opportunitiesQ.data?.oportunidades ?? []).map((opportunity) => (
                  <div key={opportunity.id} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{opportunity.offer_key}</span>
                      <Badge>{opportunity.score}</Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Versão {opportunity.offer_version ?? 'não informada'} · origem {opportunity.resolved_from ?? 'não informada'}
                    </p>
                    {opportunity.evidence.length > 0 && (
                      <p className="mt-2 text-xs">Evidências: {opportunity.evidence.join(', ')}</p>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
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
          <TechnicalTab enrichment={lead.enrichment} />
        </TabsContent>

        <TabsContent value="contacts" className="space-y-4">
          <ContactsTab lead={lead} onAssociate={setAssociateContact} />
        </TabsContent>

        <TabsContent value="cadence" className="space-y-4">
          <CadencePanel leadId={lead.id} />
        </TabsContent>

        <TabsContent value="activities" className="space-y-4">
          <ActivitiesTab activities={lead.activities ?? []} />
        </TabsContent>

        <TabsContent value="actions" className="space-y-4">
          <Card>
            <CardContent className="space-y-3 pt-6">
              <Button
                className="w-full h-11"
                onClick={handleGenerateFromActions}
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
                    { id: leadId, status: 'CONTATADO' },
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

      <ConversionDialog leadId={lead.id} open={convOpen} onOpenChange={setConvOpen} />

      <OutreachMessagesModal
        lead={lead}
        open={isModalOpen}
        onOpenChange={setIsModalOpen}
        messages={generatedMessages}
        isGenerating={generateMessagesMutation.isPending}
        onRegenerateVariants={handleGenerateVariants}
        onApplyVariant={(step, variant) => void applyVariantToStep(step, variant)}
        onSaveToPlaybook={(subject, body) => void saveToPlaybook(subject, body)}
      />

      {associateContact && (
        <LinkedInAssociateDialog
          leadId={lead.id}
          companyName={lead.company_name}
          contact={associateContact}
          open={!!associateContact}
          onOpenChange={(open) => {
            if (!open) setAssociateContact(null);
          }}
        />
      )}
    </div>
  );
}
