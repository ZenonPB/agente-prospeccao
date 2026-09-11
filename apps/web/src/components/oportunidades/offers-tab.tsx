'use client';

import { useMemo, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ChevronDown, History, Loader2 } from 'lucide-react';
import { useLeadOpportunities, useLeadOpportunitiesHistory } from '@/hooks/use-api';
import { offerProfileLabel, signalLabel, SIGNAL_LABELS } from '@/lib/offers';
import { cn } from '@/lib/utils';
import type { LeadOpportunity } from '@/types';

/** Troca chaves cruas de sinal (ex.: HOSTS_EVENTS) pelo rótulo em português. */
function emPortugues(texto: string): string {
  let saida = texto;
  for (const [chave, rotulo] of Object.entries(SIGNAL_LABELS)) {
    if (saida.includes(chave)) saida = saida.split(chave).join(rotulo);
  }
  return saida
    .replace(/^Evidência de ICP:\s*/i, '')
    .replace(/^Evidência observada:\s*/i, '');
}

function formatarValor(valor: number | string): string {
  if (typeof valor === 'number') {
    return valor.toLocaleString('pt-BR', { maximumFractionDigits: 2 });
  }
  return valor;
}

function ResumoPontuacao({ breakdown }: { breakdown?: Record<string, number | string> | null }) {
  const linhas = useMemo(() => {
    if (!breakdown) return [];
    return Object.entries(breakdown).slice(0, 4);
  }, [breakdown]);
  if (linhas.length === 0) return null;
  return (
    <div className="mt-2 rounded-md bg-muted p-2 text-xs">
      <p className="font-medium">Como a nota foi montada</p>
      <ul className="mt-1 space-y-0.5 text-muted-foreground">
        {linhas.map(([chave, valor]) => (
          <li key={chave} className="flex justify-between gap-2">
            <span>{/^[A-Z_]+$/.test(chave) ? signalLabel(chave) : chave}</span>
            <span className="font-medium text-foreground">{formatarValor(valor)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CartaoOferta({ oportunidade }: { oportunidade: LeadOpportunity }) {
  const narrativa = oportunidade.narrative;
  const principaisSinais = (oportunidade.signals_matched ?? []).slice(0, 3);
  return (
    <div className="rounded-lg border p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">{offerProfileLabel(oportunidade.offer_key)}</span>
        <Badge>{oportunidade.score} pontos</Badge>
      </div>
      {oportunidade.offer_version && (
        <p className="mt-1 text-xs text-muted-foreground">
          Análise versão {oportunidade.offer_version}
        </p>
      )}
      {principaisSinais.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {principaisSinais.map((sinal) => (
            <Badge key={sinal} variant="secondary" className="font-normal">
              {signalLabel(sinal)}
            </Badge>
          ))}
        </div>
      )}
      {narrativa && (
        <div className="mt-2 space-y-2 text-xs">
          {narrativa.facts.length > 0 && (
            <div>
              <p className="font-medium">O que vimos neste cliente</p>
              <ul className="mt-0.5 list-disc space-y-0.5 pl-4 text-muted-foreground">
                {narrativa.facts.map((fato, i) => (
                  <li key={i}>{emPortugues(fato)}</li>
                ))}
              </ul>
            </div>
          )}
          {narrativa.hypotheses.length > 0 && (
            <div>
              <p className="font-medium">Por que pode fechar</p>
              <ul className="mt-0.5 list-disc space-y-0.5 pl-4 text-muted-foreground">
                {narrativa.hypotheses.map((hipotese, i) => (
                  <li key={i}>{emPortugues(hipotese)}</li>
                ))}
              </ul>
            </div>
          )}
          {narrativa.validation_questions.length > 0 && (
            <div>
              <p className="font-medium">O que confirmar com o cliente</p>
              <ul className="mt-0.5 list-disc space-y-0.5 pl-4 text-muted-foreground">
                {narrativa.validation_questions.map((pergunta, i) => (
                  <li key={i}>{emPortugues(pergunta)}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      <ResumoPontuacao breakdown={oportunidade.score_breakdown} />
    </div>
  );
}

function Historico({ leadId }: { leadId: string }) {
  const [aberto, setAberto] = useState(false);
  const historicoQ = useLeadOpportunitiesHistory(leadId, aberto);
  const itens = historicoQ.data?.historico ?? [];
  return (
    <div className="rounded-lg border p-3">
      <Button
        variant="ghost"
        className="h-11 w-full justify-between"
        onClick={() => setAberto((v) => !v)}
        aria-expanded={aberto}
      >
        <span className="flex items-center gap-2 text-sm font-medium">
          <History className="h-4 w-4" />
          Histórico de avaliações
          {aberto && historicoQ.data ? ` (${itens.length})` : ''}
        </span>
        <ChevronDown className={cn('h-4 w-4 transition-transform', aberto && 'rotate-180')} />
      </Button>
      {aberto && (
        <div className="mt-2 space-y-2">
          {historicoQ.isLoading && (
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Carregando histórico…
            </p>
          )}
          {historicoQ.isError && (
            <p className="text-xs text-muted-foreground">Não foi possível carregar o histórico.</p>
          )}
          {!historicoQ.isLoading && !historicoQ.isError && itens.length === 0 && (
            <p className="text-xs text-muted-foreground">Nenhuma avaliação anterior registrada.</p>
          )}
          {itens.map((item) => (
            <div key={item.id} className="rounded-md bg-muted p-2 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{offerProfileLabel(item.offer_key)}</span>
                <Badge variant="outline">{item.score} pontos</Badge>
              </div>
              <p className="mt-0.5 text-muted-foreground">
                {(item.scored_at || item.created_at)
                  ? new Date(item.scored_at || item.created_at as string).toLocaleDateString('pt-BR')
                  : 'Data não informada'}
                {item.offer_version ? ` · versão ${item.offer_version}` : ''}
                {item.reason ? ` · ${emPortugues(item.reason)}` : ''}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function OffersTab({ leadId }: { leadId: string }) {
  const oportunidadesQ = useLeadOpportunities(leadId);
  const oportunidades = useMemo(
    () => [...(oportunidadesQ.data?.oportunidades ?? [])].sort((a, b) => b.score - a.score),
    [oportunidadesQ.data],
  );
  return (
    <Card>
      <CardContent className="space-y-3 pt-6">
        <div>
          <h3 className="font-semibold">Oportunidades por oferta</h3>
          <p className="text-sm text-muted-foreground">
            O que este cliente pode comprar e por quê.
          </p>
        </div>
        {oportunidadesQ.isLoading && <p className="text-sm text-muted-foreground">Carregando ofertas…</p>}
        {oportunidadesQ.isError && (
          <p className="text-sm text-muted-foreground">Não foi possível carregar as ofertas.</p>
        )}
        {!oportunidadesQ.isLoading && !oportunidadesQ.isError && oportunidades.length === 0 && (
          <p className="text-sm text-muted-foreground">Nenhuma oferta relacionada foi registrada.</p>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          {oportunidades.map((oportunidade) => (
            <CartaoOferta key={oportunidade.id} oportunidade={oportunidade} />
          ))}
        </div>
        {!oportunidadesQ.isLoading && !oportunidadesQ.isError && <Historico leadId={leadId} />}
      </CardContent>
    </Card>
  );
}
