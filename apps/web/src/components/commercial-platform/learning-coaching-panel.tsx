'use client';

import { useState } from 'react';
import { BrainCircuit, CheckCircle2, History, Loader2, RotateCcw, Sparkles, UsersRound } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { useOrgMembership } from '@/hooks/use-api';
import {
  useApproveCalibrationComparison,
  useCalibrationOverview,
  useCommercialCoaching,
  useCreateCalibrationComparison,
  useLearningProposals,
  useOfferProfileVersions,
  usePublishLearningProposal,
  useRollbackOfferProfile,
} from '@/hooks/use-commercial-platform';
import type { CalibrationComparison } from '@/lib/commercial-platform-api';
import { offerProfileLabel } from '@/lib/offers';

function pct(value: number | null | undefined) {
  return value == null ? '—' : `${Math.round(value * 100)}%`;
}

export function LearningCoachingPanel() {
  const calibration = useCalibrationOverview();
  const coaching = useCommercialCoaching();
  const proposals = useLearningProposals();
  const versions = useOfferProfileVersions();
  const membership = useOrgMembership();
  const createComparison = useCreateCalibrationComparison();
  const approve = useApproveCalibrationComparison();
  const publish = usePublishLearningProposal();
  const rollback = useRollbackOfferProfile();
  const [comparison, setComparison] = useState<CalibrationComparison | null>(null);
  const [approvalEvidence, setApprovalEvidence] = useState('Replay histórico com outcomes atribuídos e gates mínimos atendidos.');
  const canManage = ['OWNER', 'ADMIN'].includes(membership.data?.membership?.role ?? '') || membership.data?.membership?.sales_role === 'MANAGER';

  const create = async (offerKey: string) => {
    try {
      const value = await createComparison.mutateAsync({ offer_key: offerKey, min_samples: 20, top_k: 20 });
      setComparison(value);
      toast.success(`Comparação ${value.version_a} → ${value.version_b} criada com replay histórico.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível criar a comparação.');
    }
  };

  const approveCurrent = async () => {
    if (!comparison || comparison.result.verdict !== 'v2') return;
    try {
      const value = await approve.mutateAsync({ comparisonId: comparison.id, approvedVersion: comparison.version_b, evidence: approvalEvidence.trim() });
      setComparison(value);
      toast.success('Comparação aprovada. A proposta ficou pronta para publicação explícita.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível aprovar a comparação.');
    }
  };

  return <div className="space-y-6">
    <Card>
      <CardHeader>
        <div className="flex items-start gap-3"><BrainCircuit className="mt-1 size-5 text-primary" aria-hidden="true" /><div><CardTitle>Learning controlado e calibração</CardTitle><CardDescription>O sistema só sugere mudança quando a amostra, a atribuição e os resultados atingem os gates mínimos. Nada é publicado automaticamente.</CardDescription></div></div>
      </CardHeader>
      <CardContent className="space-y-4">
        {calibration.isLoading ? <Loading label="Calculando amostras e associações..." /> : calibration.isError ? <EmptyState title="Não foi possível calcular a calibração" description="Os dados comerciais continuam preservados; tente recarregar a página." /> : !calibration.data?.items.length ? <EmptyState title="Ainda não há histórico suficiente para calibrar" description="Aparecerão aqui as ofertas com oportunidades ou outcomes registrados." /> : calibration.data.items.map((item) => <article key={item.offer_key} className="rounded-xl border p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><p className="text-sm text-muted-foreground">{offerProfileLabel(item.offer_key)} · versão ativa {item.active_version}</p><h3 className="mt-1 font-medium">{item.sample_quality.observed_opportunities} oportunidade(s) observadas · {item.sample_quality.wins} venda(s)</h3></div>
            <Badge variant={item.sample_quality.eligible_for_proposal ? 'secondary' : 'outline'}>{item.sample_quality.eligible_for_proposal ? 'Gates atendidos' : 'Amostra insuficiente'}</Badge>
          </div>
          <div className="mt-3 grid gap-3 text-sm sm:grid-cols-4">
            <Metric label="Atribuição" value={pct(item.sample_quality.attribution_rate)} />
            <Metric label="Úteis pelo time" value={pct(item.human_feedback.useful_rate)} />
            <Metric label="Feedbacks de score" value={String(item.human_feedback.score_feedback_total)} />
            <Metric label="Mínimo exigido" value={String(item.sample_quality.required_observed_opportunities)} />
          </div>
          {item.associations.length ? <div className="mt-4 flex flex-wrap gap-2">{item.associations.slice(0, 5).map((signal) => <Badge key={signal.signal} variant="outline">{signal.signal} · venda {pct(signal.win_rate)} · n={signal.sample_size}</Badge>)}</div> : null}
          <p className="mt-3 text-xs text-muted-foreground">Associações históricas não são tratadas como causalidade. Sinal ausente continua desconhecido, não falso.</p>
          {canManage ? <div className="mt-4"><Button disabled={!item.sample_quality.eligible_for_proposal || createComparison.isPending} onClick={() => void create(item.offer_key)}><Sparkles className="mr-2 size-4" />Gerar candidato e validar no replay</Button></div> : null}
        </article>)}
      </CardContent>
    </Card>

    {comparison ? <Card className="border-primary/30">
      <CardHeader><CardTitle>Replay {comparison.version_a} → {comparison.version_b}</CardTitle><CardDescription>{comparison.result.recommendation}</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-4"><Metric label="Δ resposta" value={pct(comparison.result.delta.reply_precision)} signed /><Metric label="Δ reunião" value={pct(comparison.result.delta.meeting_precision)} signed /><Metric label="Δ venda" value={pct(comparison.result.delta.win_precision)} signed /><Metric label="Veredito" value={comparison.result.verdict === 'v2' ? 'Candidato venceu' : comparison.result.verdict === 'v1' ? 'Atual venceu' : 'Inconclusivo'} /></div>
        {comparison.result.verdict === 'v2' && !comparison.learning_proposal && canManage ? <div className="space-y-2"><label className="text-sm font-medium" htmlFor="approval-evidence">Evidência humana da aprovação</label><Input id="approval-evidence" value={approvalEvidence} onChange={(event) => setApprovalEvidence(event.target.value)} /><Button disabled={approval.isPending || approvalEvidence.trim().length < 3} onClick={() => void approveCurrent()}><CheckCircle2 className="mr-2 size-4" />Aprovar candidato</Button></div> : null}
        {comparison.learning_proposal ? <p className="text-sm text-muted-foreground">Proposta #{comparison.learning_proposal.proposal_version} criada. A publicação continua sendo uma ação separada e auditável.</p> : null}
      </CardContent>
    </Card> : null}

    <div className="grid gap-6 xl:grid-cols-2">
      <Card><CardHeader><CardTitle>Propostas aguardando publicação</CardTitle><CardDescription>Publicar ativa exatamente o snapshot candidato aprovado; o navegador não pode trocar o conteúdo aprovado.</CardDescription></CardHeader><CardContent className="space-y-3">{proposals.isLoading ? <Loading label="Carregando propostas..." /> : !proposals.data?.proposals.length ? <EmptyState title="Nenhuma proposta pendente" description="Quando uma comparação conclusiva for aprovada, ela aparecerá aqui." /> : proposals.data.proposals.map((proposal) => <div key={proposal.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4"><div><p className="font-medium">{offerProfileLabel(proposal.offer_key)} · {proposal.approved_version}</p><p className="text-sm text-muted-foreground">Proposta #{proposal.proposal_version} · {proposal.status}</p></div>{canManage && proposal.status === 'PROPOSED' ? <Button disabled={publish.isPending} onClick={() => publish.mutate(proposal.id, { onSuccess: () => toast.success('Nova versão publicada no workspace.'), onError: (error) => toast.error(error instanceof Error ? error.message : 'Falha ao publicar.') })}>Publicar versão aprovada</Button> : <Badge variant="outline">{proposal.status}</Badge>}</div>)}</CardContent></Card>
      <Card><CardHeader><CardTitle>Histórico e rollback</CardTitle><CardDescription>Rollback reativa um snapshot histórico conhecido; não recalcula uma aproximação.</CardDescription></CardHeader><CardContent className="space-y-3">{versions.isLoading ? <Loading label="Carregando versões..." /> : !versions.data?.items.length ? <EmptyState title="Sem versões publicadas" description="O baseline continua vindo do catálogo padrão enquanto não houver overlay do workspace." /> : versions.data.items.map((version) => <div key={version.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4"><div className="flex items-center gap-2"><History className="size-4 text-muted-foreground" /><div><p className="font-medium">{offerProfileLabel(version.offer_key)} · {version.version}</p><p className="text-sm text-muted-foreground">{version.is_active ? 'Ativa agora' : 'Snapshot histórico'}</p></div></div>{version.is_active ? <Badge variant="secondary">Ativa</Badge> : canManage ? <Button variant="outline" disabled={rollback.isPending} onClick={() => rollback.mutate({ offerKey: version.offer_key, targetVersion: version.version }, { onSuccess: () => toast.success('Rollback concluído.'), onError: (error) => toast.error(error instanceof Error ? error.message : 'Falha no rollback.') })}><RotateCcw className="mr-2 size-4" />Reativar</Button> : null}</div>)}</CardContent></Card>
    </div>

    <Card>
      <CardHeader><div className="flex items-start gap-3"><UsersRound className="mt-1 size-5 text-primary" /><div><CardTitle>Coaching comercial baseado em evidência</CardTitle><CardDescription>Diagnóstico por consultor usando atividades, outcomes e prazos reais. Recomendações deixam explícito quando são apenas associações.</CardDescription></div></div></CardHeader>
      <CardContent className="space-y-4">{coaching.isLoading ? <Loading label="Analisando operação do time..." /> : coaching.isError || !coaching.data ? <EmptyState title="Não foi possível montar o coaching" description="Tente novamente em alguns instantes." /> : <>
        <div className="grid gap-3 sm:grid-cols-4"><Metric label="Leads atribuídos" value={String(coaching.data.team.assigned_leads)} /><Metric label="Reuniões" value={String(coaching.data.team.meetings)} /><Metric label="Vendas" value={String(coaching.data.team.wins)} /><Metric label="Follow-ups vencidos" value={String(coaching.data.team.overdue_followups)} /></div>
        {!coaching.data.consultants.length ? <EmptyState title="Ainda não há carteira atribuída" description="O coaching aparece quando consultores possuem leads sob responsabilidade." /> : coaching.data.consultants.map((consultant) => <article key={consultant.user_id} className="rounded-xl border p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-medium">{consultant.name}</h3><p className="text-sm text-muted-foreground">{consultant.contacted} contatos · {consultant.meetings} reuniões · {consultant.proposals} propostas · {consultant.wins} vendas</p></div><Badge variant={consultant.recommendations.length ? 'secondary' : 'outline'}>{consultant.recommendations.length ? `${consultant.recommendations.length} ponto(s) de atenção` : 'Sem alerta com amostra suficiente'}</Badge></div>{consultant.recommendations.map((recommendation) => <div key={recommendation.kind} className="mt-3 rounded-lg bg-muted/40 p-3"><p className="font-medium">{recommendation.title}</p><p className="mt-1 text-sm">{recommendation.recommendation}</p><p className="mt-1 text-xs text-muted-foreground">Baseado em contagens reais desta carteira. Associação observada; não prova causalidade.</p></div>)}</article>)}
      </>}</CardContent>
    </Card>
  </div>;
}

function Loading({ label }: { label: string }) { return <div className="flex min-h-20 items-center justify-center text-sm text-muted-foreground" role="status"><Loader2 className="mr-2 size-4 animate-spin" />{label}</div>; }
function Metric({ label, value, signed = false }: { label: string; value: string; signed?: boolean }) { return <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 font-semibold tabular-nums">{signed && value !== '—' && !value.startsWith('-') && value !== '0%' ? `+${value}` : value}</p></div>; }
