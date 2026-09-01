'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Play, CheckCircle, XCircle, Loader2,
  ExternalLink, Sparkles, RefreshCw, WifiOff,
} from 'lucide-react';
import { useStartPipeline, useReanalyzeCampaign, usePipelineJobs, useInvalidateJobs } from '@/hooks/use-api';
import { useReconnectableWs } from '@/hooks/use-reconnectable-ws';
import { createPipelineWsUrl, getPipelineAuthPayload } from '@/lib/api';
import { toast } from 'sonner';

// Mantém o DOM/renders finitos mesmo em rodadas longas (anti-congelamento).
const MAX_LOG_LINES = 150;

interface PipelineEvent {
  type: string;
  message?: string;
  step?: string;
  percent?: number;
  name?: string;
  score?: number | null;
  status?: string;
  summary?: {
    collected: number;
    qualified: number;
    scored: number;
    failed: number;
    total_processed: number;
    queue_remaining?: number;
  };
  timestamp?: string;
}

interface CampaignPipelineProps {
  campaignId: string;
  campaignName: string;
  autoStart?: boolean;
  hasExistingLeads?: boolean;
}

export function CampaignPipeline({
  campaignId,
  campaignName,
  autoStart,
  hasExistingLeads,
}: CampaignPipelineProps) {
  const router = useRouter();
  const [isRunning, setIsRunning] = useState(false);
  const [mode, setMode] = useState<'collect' | 'reanalyze' | 'reanalyze-unscored'>('collect');
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState('');
  const [summary, setSummary] = useState<PipelineEvent['summary'] | null>(null);
  const [hasStarted, setHasStarted] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const startPipeline = useStartPipeline();
  const reanalyzeCampaign = useReanalyzeCampaign();
  const jobsQuery = usePipelineJobs(campaignId, 5);
  const invalidateJobs = useInvalidateJobs();

  const { wsRef, isReconnecting, reconnectCount, connect, disconnect } = useReconnectableWs({
    maxRetries: 5,
    baseDelay: 1000,
    onMessage: (data) => {
      const event = data as PipelineEvent;
      setEvents((prev) => [...prev.slice(-MAX_LOG_LINES + 1), event]);

      if (event.type === 'progress' && event.percent !== undefined) {
        setProgress(event.percent);
        if (event.step) setCurrentStep(event.step);
      }

      if (event.type === 'done') {
        setSummary(event.summary);
        setIsRunning(false);
        invalidateJobs();
      }

      if (event.type === 'error') {
        setIsRunning(false);
        setErrorMessage(event.message || 'Erro durante o pipeline');
        invalidateJobs();
      }
    },
    onOpen: () => {
      if (reconnectCount > 0) {
        toast.success('Reconectado ao pipeline');
      }
    },
    onClose: () => {
      setIsRunning(false);
    },
  });

  // Com o pipeline em background (job-consumer), o usuário pode sair da tela e
  // voltar: o resumo é restaurado do último job COMPLETED da campanha.
  const latestJob = jobsQuery.data?.jobs?.[0] ?? null;
  const hasActiveJob =
    !!latestJob && (latestJob.status === 'PENDING' || latestJob.status === 'IN_PROGRESS');
  const restoredSummary = summary ?? (latestJob?.status === 'COMPLETED' ? latestJob.summary : null);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events]);

  // Voltou à página com job em andamento: reconecta ao WS para retomar o
  // feed em tempo real (o resumo final vem do evento 'done' ou do job COMPLETED).
  const activeJobId = hasActiveJob && latestJob ? latestJob.id : null;
  useEffect(() => {
    if (activeJobId && !wsRef.current) {
      setIsRunning(true);
      connect(createPipelineWsUrl(activeJobId), getPipelineAuthPayload());
    }
  }, [activeJobId, connect, wsRef]);

  const handleStart = useCallback(async (startMode: 'collect' | 'reanalyze' | 'reanalyze-unscored' = 'collect') => {
    setHasStarted(true);
    setIsRunning(true);
    setMode(startMode);
    setEvents([]);
    setProgress(0);
    setCurrentStep('');
    setSummary(null);
    setErrorMessage(null);

    try {
      const result =
        startMode === 'collect'
          ? await startPipeline.mutateAsync({
              campaign_id: campaignId,
              max_leads: 10,
            })
          : await reanalyzeCampaign.mutateAsync({
              campaign_id: campaignId,
              unscored_only: startMode === 'reanalyze-unscored',
            });
      invalidateJobs();

      // Usar hook de reconexão automática (auth reenviada a cada reconexão)
      connect(createPipelineWsUrl(result.job_id), getPipelineAuthPayload());
    } catch (e) {
      setIsRunning(false);
      const msg = e instanceof Error ? e.message : 'Erro ao iniciar pipeline';
      setErrorMessage(msg);
      setEvents((prev) => [...prev, { type: 'error', message: msg }]);
    }
  }, [campaignId, startPipeline, reanalyzeCampaign, invalidateJobs, connect]);

  useEffect(() => {
    // Auto-start intencional: navegação com ?start=true dispara a coleta uma
    // única vez. Dispara via microtask para não sincronizar estado no effect.
    if (autoStart && !hasStarted && !isRunning) {
      const t = setTimeout(() => handleStart('collect'), 0);
      return () => clearTimeout(t);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart]);

  const handleStop = () => {
    disconnect();
    setIsRunning(false);
  };

  return (
    <div className="space-y-6" data-tour="campanha-pipeline">
      {!hasStarted && !isRunning && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-col items-center gap-4 text-center">
              <div className="rounded-full bg-primary/10 p-3">
                <Sparkles className="h-8 w-8 text-primary" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">Pronto para coletar leads</h3>
                <p className="text-sm text-muted-foreground">
                  Inicie a coleta de leads para &ldquo;{campaignName}&rdquo;
                </p>
              </div>
              <div className="flex flex-wrap gap-2 justify-center">
                <Button size="lg" onClick={() => handleStart('collect')} disabled={startPipeline.isPending || reanalyzeCampaign.isPending}>
                  {startPipeline.isPending ? (
                    <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  ) : (
                    <Play className="mr-2 h-5 w-5" />
                  )}
                  Iniciar Coleta
                </Button>
                {hasExistingLeads && (
                  <>
                    <Button
                      size="lg"
                      variant="outline"
                      onClick={() => handleStart('reanalyze')}
                      disabled={startPipeline.isPending || reanalyzeCampaign.isPending}
                      title="Reavalia todos os clientes desta campanha usando as regras mais recentes"
                    >
                      {reanalyzeCampaign.isPending ? (
                        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                      ) : (
                        <RefreshCw className="mr-2 h-5 w-5" />
                      )}
                      Reavaliar todos os clientes
                    </Button>
                    <Button
                      size="lg"
                      variant="secondary"
                      onClick={() => handleStart('reanalyze-unscored')}
                      disabled={startPipeline.isPending || reanalyzeCampaign.isPending}
                      title="Avalia apenas os clientes que ainda não possuem pontuação — sem gastar seu limite com clientes já analisados"
                    >
                      {reanalyzeCampaign.isPending ? (
                        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                      ) : (
                        <RefreshCw className="mr-2 h-5 w-5" />
                      )}
                      Avaliar apenas pendentes
                    </Button>
                  </>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {errorMessage && !isRunning && (
        <Card className="border-red-200 bg-red-50/50">
          <CardContent className="pt-6">
            <div className="flex items-start gap-2">
              <XCircle className="h-5 w-5 text-red-600 mt-0.5 shrink-0" />
              <div>
                <h3 className="text-sm font-semibold text-red-800">Erro</h3>
                <p className="text-sm text-red-700 mt-1">{errorMessage}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {isReconnecting && (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardContent className="py-3">
            <div className="flex items-center gap-2 text-sm text-amber-800">
              <WifiOff className="h-4 w-4 shrink-0 animate-pulse" />
              <span>
                Conexão perdida — reconectando... (tentativa {reconnectCount}/5)
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      {hasActiveJob && !isRunning && !hasStarted && (
        <Card className="border-primary/40 bg-primary/5">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-sm">
              <Loader2 className="h-4 w-4 animate-spin text-primary shrink-0" />
              <span>
                Há uma coleta/análise em andamento para esta campanha. Você pode sair desta
                tela — o job continua em segundo plano e o resumo aparecerá aqui.
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      {isRunning && (
        <Card className="border-primary/50">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
                <CardTitle>
                  {mode === 'reanalyze' || mode === 'reanalyze-unscored' ? 'Reanalisando leads...' : 'Coletando leads...'}
                </CardTitle>
              </div>
              <Button variant="outline" size="sm" onClick={handleStop}>
                <XCircle className="mr-2 h-4 w-4" />
                Parar
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                {currentStep ? `Etapa: ${currentStep}` : 'Iniciando...'}
              </span>
              <span className="font-medium">{Math.round(progress)}%</span>
            </div>
            <Progress value={progress} className="h-2" />
          </CardContent>
        </Card>
      )}

      {restoredSummary && (
        <Card className="border-emerald-200 bg-emerald-50/50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 mb-4">
              <CheckCircle className="h-6 w-6 text-emerald-600" />
              <h3 className="text-lg font-semibold text-emerald-800">
                {mode === 'reanalyze' || mode === 'reanalyze-unscored' ? 'Reanálise finalizada' : 'Coleta finalizada'}
              </h3>
            </div>
            <div className="grid grid-cols-2 gap-4 text-center mb-2 sm:grid-cols-4">
              <div className="rounded-lg bg-white p-3 shadow-sm">
                <div className="text-2xl font-bold">{restoredSummary.collected}</div>
                <div className="text-sm text-muted-foreground">Coletados</div>
              </div>
              <div className="rounded-lg bg-white p-3 shadow-sm">
                <div className="text-2xl font-bold">{restoredSummary.scored}</div>
                <div className="text-sm text-muted-foreground">Pontuados</div>
              </div>
              <div className="rounded-lg bg-white p-3 shadow-sm">
                <div className="text-2xl font-bold text-emerald-600">{restoredSummary.qualified}</div>
                <div className="text-sm text-muted-foreground">Qualificados</div>
              </div>
              <div className="rounded-lg bg-white p-3 shadow-sm">
                <div className={`text-2xl font-bold ${restoredSummary.failed > 0 ? 'text-amber-600' : ''}`}>
                  {restoredSummary.failed}
                </div>
                <div className="text-sm text-muted-foreground">Falhas</div>
              </div>
            </div>
            {restoredSummary.failed > 0 && (
              <p className="text-xs text-amber-700 mb-2">
                Leads não pontuados (falha do provedor) voltam à fila automaticamente no próximo job.
              </p>
            )}
            {mode !== 'reanalyze' && (restoredSummary.queue_remaining ?? 0) > 0 && (
              <p className="text-xs text-sky-700 mb-2">
                {restoredSummary.queue_remaining} leads coletados ainda aguardam pontuação — rode «Coletar» de novo para analisá-los.
              </p>
            )}
            <Button onClick={() => router.push('/oportunidades')}>
              <ExternalLink className="mr-2 h-4 w-4" />
              Ver Oportunidades
            </Button>
          </CardContent>
        </Card>
      )}

      {(isRunning || events.length > 0) && (
        <Card>
          <CardHeader>
            <CardTitle>Atividade em Tempo Real</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[400px] overflow-y-auto rounded-lg bg-muted/50 p-4 font-mono text-sm">
              <div className="space-y-1">
                {events.slice(-MAX_LOG_LINES).map((event, i) => {
                  if (event.type === 'log') {
                    return (
                      <p key={i}>
                        <span className="text-emerald-500">✓</span> {event.message}
                      </p>
                    );
                  }
                  if (event.type === 'progress') {
                    return null;
                  }
                  if (event.type === 'lead') {
                    if (event.score == null) {
                      return (
                        <p key={i}>
                          <span className="text-red-400">→</span> {event.name} — não pontuado
                          (falha do provedor)
                        </p>
                      );
                    }
                    const scoreColor = event.score >= 60 ? 'text-emerald-500' : 'text-amber-500';
                    return (
                      <p key={i}>
                        <span className={scoreColor}>→</span> {event.name} — Score: {event.score} ({event.status})
                      </p>
                    );
                  }
                  if (event.type === 'error') {
                    return (
                      <p key={i} className="text-red-500">
                        ✗ {event.message}
                      </p>
                    );
                  }
                  return null;
                })}
                <div ref={logsEndRef} />
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
