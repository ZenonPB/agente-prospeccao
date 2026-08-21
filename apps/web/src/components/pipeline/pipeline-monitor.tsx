'use client';

import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Pause, Loader2, Play, WifiOff } from 'lucide-react';
import { useStartPipeline, usePipelineJobs, useInvalidateJobs } from '@/hooks/use-api';
import { useReconnectableWs } from '@/hooks/use-reconnectable-ws';
import { createPipelineWs } from '@/lib/api';
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

export function PipelineMonitor() {
  const [query, setQuery] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState('');
  const [summary, setSummary] = useState<PipelineEvent['summary'] | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const startPipeline = useStartPipeline();
  const jobsQuery = usePipelineJobs(undefined, 5);
  const invalidateJobs = useInvalidateJobs();

  const { isReconnecting, reconnectCount, connect, disconnect } = useReconnectableWs({
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

  // Restaura o resumo do último job da organização após reload/navegação.
  const latestJob = jobsQuery.data?.jobs?.[0] ?? null;
  const restoredSummary = summary ?? (latestJob?.status === 'COMPLETED' ? latestJob.summary : null);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events]);

  const handleStart = async () => {
    if (!query.trim()) return;

    setIsRunning(true);
    setEvents([]);
    setProgress(0);
    setCurrentStep('');
    setSummary(null);

    try {
      const result = await startPipeline.mutateAsync({
        query: query.trim(),
        max_leads: 10,
      });
      invalidateJobs();

      // Usar hook de reconexão automática
      const wsUrl = createPipelineWs(result.job_id).url;
      connect(wsUrl);
    } catch {
      setIsRunning(false);
      setEvents((prev) => [...prev, { type: 'error', message: 'Erro ao iniciar pipeline' }]);
    }
  };

  const handleStop = () => {
    disconnect();
    setIsRunning(false);
  };

  return (
    <div className="space-y-6">
      {/* Start Pipeline */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Iniciar Nova Busca</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <Input
              placeholder="Ex: Restaurantes em Araraquara, SP"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={isRunning}
              className="flex-1"
            />
            {isRunning ? (
              <Button variant="destructive" onClick={handleStop}>
                <Pause className="mr-2 h-4 w-4" />
                Parar
              </Button>
            ) : (
              <Button onClick={handleStart} disabled={!query.trim() || startPipeline.isPending}>
                {startPipeline.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Play className="mr-2 h-4 w-4" />
                )}
                Iniciar
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Reconnection banner */}
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

      {/* Progress Bar */}
      {(isRunning || events.length > 0 || restoredSummary) && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <CardTitle>Busca em Andamento</CardTitle>
              {restoredSummary && (
                <Badge className="bg-emerald-100 text-emerald-700">
                  Concluído
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                {currentStep ? `Etapa: ${currentStep}` : 'Progresso geral'}
              </span>
              <span className="font-medium">{Math.round(progress)}%</span>
            </div>
            <Progress value={progress} className="h-2" />
            {restoredSummary && (
              <>
                <div className="mt-4 grid grid-cols-2 gap-4 text-center sm:grid-cols-4">
                  <div>
                    <div className="text-2xl font-bold">{restoredSummary.collected}</div>
                    <div className="text-sm text-muted-foreground">Coletados</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold">{restoredSummary.scored}</div>
                    <div className="text-sm text-muted-foreground">Pontuados</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-emerald-600">{restoredSummary.qualified}</div>
                    <div className="text-sm text-muted-foreground">Aptos</div>
                  </div>
                  <div>
                    <div className={`text-2xl font-bold ${restoredSummary.failed > 0 ? 'text-amber-600' : ''}`}>
                      {restoredSummary.failed}
                    </div>
                    <div className="text-sm text-muted-foreground">Falhas</div>
                  </div>
                </div>
                {(restoredSummary.queue_remaining ?? 0) > 0 && (
                  <p className="mt-2 text-xs text-sky-700">
                    {restoredSummary.queue_remaining} leads coletados aguardam pontuação — rode a coleta de novo para analisá-los.
                  </p>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* Real-time Log */}
      {events.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Andamento em Tempo Real</CardTitle>
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
                    return null; // Handled by progress bar
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
                        <span className={scoreColor}>→</span> {event.name} — Aptidão: {event.score} ({event.status})
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