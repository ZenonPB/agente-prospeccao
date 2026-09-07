'use client';

import { CalendarDays, ExternalLink, Loader2, TrendingUp, FlaskConical, UserRound, Phone, Mail } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useApproveCommercialComparison, useCommercialComparison, useIntelligence } from '@/hooks/use-api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useState } from 'react';
import { toast } from 'sonner';

function formatDate(value: string) {
  return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium' }).format(new Date(`${value}T12:00:00`));
}

export function IntelligenceSection({ period }: { period?: { from?: string; to?: string } }) {
  const { events, outcomes } = useIntelligence(period);

  if (events.isLoading || outcomes.isLoading) {
    return <div className="flex items-center justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }

  if (events.isError || outcomes.isError) {
    return <p className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">Não foi possível carregar a inteligência comercial agora. Tente novamente mais tarde.</p>;
  }

  const metrics = outcomes.data?.metrics ?? [];
  const eventItems = events.data?.events ?? [];

  return (
    <section className="space-y-4" aria-labelledby="inteligencia-comercial">
      <div>
        <h2 id="inteligencia-comercial" className="font-heading text-lg font-semibold">Inteligência comercial</h2>
        <p className="text-sm text-muted-foreground">Sinais de oportunidade e resultados por oferta.</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><CalendarDays className="h-4 w-4 text-primary" />Eventos futuros</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {eventItems.length === 0 ? <p className="text-sm text-muted-foreground">Nenhum evento futuro foi encontrado.</p> : eventItems.slice(0, 6).map((event) => (
              <div key={event.id} className="flex items-start justify-between gap-3 rounded-lg border p-3">
                <div className="min-w-0 space-y-1">
                  <p className="font-medium">{event.name}</p>
                  <p className="text-xs text-muted-foreground">{formatDate(event.event_date)} · {event.location || 'Local não informado'}</p>
                  <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1"><UserRound className="h-3 w-3" />{event.decision_maker_status === 'resolved' ? 'Decisor resolvido' : event.decision_maker_status === 'failed' ? 'Falha ao resolver decisor' : 'Decisor pendente'}</span>
                    {event.recommended_channel && <span className="inline-flex items-center gap-1">{event.recommended_channel === 'email' ? <Mail className="h-3 w-3" /> : <Phone className="h-3 w-3" />}Canal: {event.recommended_channel}</span>}
                  </div>
                  {event.next_action && <p className="text-xs text-foreground/80">{event.next_action}</p>}
                </div>
                <a className="shrink-0 text-primary" href={event.source_url} target="_blank" rel="noreferrer" aria-label={`Abrir fonte de ${event.name}`}><ExternalLink className="h-4 w-4" /></a>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><TrendingUp className="h-4 w-4 text-primary" />Resultados por oferta</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {metrics.length === 0 ? <p className="text-sm text-muted-foreground">Ainda não há resultados comerciais registrados neste período.</p> : metrics.map((metric) => (
              <div key={`${metric.offer_key}-${metric.offer_version || 'atual'}`} className="flex items-center justify-between gap-3 rounded-lg border p-3"><div><p className="font-medium">{metric.offer_key}</p><p className="text-xs text-muted-foreground">{metric.won} de {metric.total} outcomes · amostra {metric.sample_size}/{metric.sample_minimum}</p><p className="text-xs text-muted-foreground">Ticket médio R$ {metric.average_ticket.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</p></div><div className="text-right"><strong className="text-emerald-600">{metric.conversion_rate.toLocaleString('pt-BR')}%</strong>{!metric.sample_sufficient && <p className="text-[11px] text-amber-700">Amostra insuficiente</p>}</div></div>
            ))}
          </CardContent>
        </Card>
      </div>
      <ComparisonCard />
    </section>
  );
}

function ComparisonCard() {
  const [offerKey, setOfferKey] = useState('trophies');
  const [versionA, setVersionA] = useState('1.0');
  const [versionB, setVersionB] = useState('2.0');
  const [run, setRun] = useState(false);
  const comparison = useCommercialComparison({ offer_key: offerKey, version_a: versionA, version_b: versionB }, run);
  const approval = useApproveCommercialComparison();
  const result = comparison.data?.result;
  const canApprove = !!result?.recommendation && (result.verdict === 'v1' || result.verdict === 'v2');

  const approve = async () => {
    if (!comparison.data || !canApprove) return;
    const selected = result.verdict === 'v1' ? versionA : versionB;
    const evidence = `Aprovação manual baseada no veredicto ${result.verdict}, delta ${result.delta}pp e intervalos de Wilson.`;
    try {
      await approval.mutateAsync({ id: comparison.data.id, approved_version: selected, evidence });
      toast.success(`Versão ${selected} aprovada e auditada.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível aprovar a versão.');
    }
  };

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><FlaskConical className="h-4 w-4 text-primary" />Comparação A/B</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">Compare versões com amostra mínima e intervalo de confiança. Nenhuma recomendação altera o sistema sem aprovação humana.</p>
        <div className="grid gap-3 sm:grid-cols-3">
          <div><Label htmlFor="comparison-offer">Oferta</Label><Input id="comparison-offer" value={offerKey} onChange={(e) => setOfferKey(e.target.value)} /></div>
          <div><Label htmlFor="comparison-a">Versão A</Label><Input id="comparison-a" value={versionA} onChange={(e) => setVersionA(e.target.value)} /></div>
          <div><Label htmlFor="comparison-b">Versão B</Label><Input id="comparison-b" value={versionB} onChange={(e) => setVersionB(e.target.value)} /></div>
        </div>
        <Button type="button" onClick={() => setRun(true)} disabled={comparison.isFetching || !offerKey || !versionA || !versionB}>
          {comparison.isFetching ? 'Calculando…' : 'Calcular comparação'}
        </Button>
        {comparison.isError && <p className="text-sm text-amber-700">Não foi possível calcular a comparação agora.</p>}
        {result && (
          <div className="rounded-lg border p-4 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2"><strong>Veredicto: {result.verdict}</strong><span className="text-sm text-muted-foreground">Delta: {result.delta.toLocaleString('pt-BR')}pp</span></div>
            <p className="text-sm">A: {result.v1_conversion}% ({result.v1_total}) · B: {result.v2_conversion}% ({result.v2_total})</p>
            <p className="text-xs text-muted-foreground">{result.recommendation || 'Sem recomendação: amostra insuficiente ou intervalos sobrepostos.'}</p>
            {comparison.data?.approved_version && <p className="text-sm text-emerald-700">Aprovada: versão {comparison.data.approved_version}</p>}
            {canApprove && !comparison.data?.approved_version && <Button type="button" variant="secondary" onClick={approve} disabled={approval.isPending}>Aprovar recomendação</Button>}
          </div>
        )}
      </CardContent>
    </Card>
  );
}