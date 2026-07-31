'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Play, CheckCircle, XCircle, Loader2,
  ExternalLink, Sparkles, RefreshCw,
} from 'lucide-react';
import { useStartPipeline, useReanalyzeCampaign } from '@/hooks/use-api';
import { createPipelineWs } from '@/lib/api';

interface PipelineEvent {
  type: string;
  message?: string;
  step?: string;
  percent?: number;
  name?: string;
  score?: number;
  status?: string;
  summary?: {
    collected: number;
    qualified: number;
    total_processed: number;
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
  const [mode, setMode] = useState<'collect' | 'reanalyze'>('collect');
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState('');
  const [summary, setSummary] = useState<PipelineEvent['summary'] | null>(null);
  const [hasStarted, setHasStarted] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const startPipeline = useStartPipeline();
  const reanalyzeCampaign = useReanalyzeCampaign();

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events]);

  const handleStart = async (startMode: 'collect' | 'reanalyze' = 'collect') => {
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
        startMode === 'reanalyze'
          ? await reanalyzeCampaign.mutateAsync(campaignId)
          : await startPipeline.mutateAsync({
              campaign_id: campaignId,
              max_leads: 10,
            });

      const ws = createPipelineWs(result.job_id);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const data: PipelineEvent = JSON.parse(event.data);
        setEvents((prev) => [...prev, data]);

        if (data.type === 'progress' && data.percent !== undefined) {
          setProgress(data.percent);
          if (data.step) setCurrentStep(data.step);
        }

        if (data.type === 'done') {
          setSummary(data.summary);
          setIsRunning(false);
        }

        if (data.type === 'error') {
          setIsRunning(false);
          setErrorMessage(data.message || 'Erro durante o pipeline');
        }
      };

      ws.onerror = () => {
        setIsRunning(false);
        setEvents((prev) => [...prev, { type: 'error', message: 'Erro na conexão WebSocket' }]);
      };

      ws.onclose = () => {
        setIsRunning(false);
      };
    } catch (e) {
      setIsRunning(false);
      const msg = e instanceof Error ? e.message : 'Erro ao iniciar pipeline';
      setErrorMessage(msg);
      setEvents((prev) => [...prev, { type: 'error', message: msg }]);
    }
  };

  const handleStop = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsRunning(false);
  };

  useEffect(() => {
    if (autoStart && !hasStarted && !isRunning) {
      // Use setTimeout to break the synchronous setState chain
      const timer = setTimeout(() => {
        handleStart('collect');
      }, 0);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart]);

  return (
    <div className="space-y-6">
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
                  <Button
                    size="lg"
                    variant="outline"
                    onClick={() => handleStart('reanalyze')}
                    disabled={startPipeline.isPending || reanalyzeCampaign.isPending}
                    title="Reanalisa os leads já coletados desta campanha com os critérios contextuais atualizados"
                  >
                    {reanalyzeCampaign.isPending ? (
                      <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                    ) : (
                      <RefreshCw className="mr-2 h-5 w-5" />
                    )}
                    Reanalisar leads
                  </Button>
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

      {isRunning && (
        <Card className="border-primary/50">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
                <CardTitle>
                  {mode === 'reanalyze' ? 'Reanalisando leads...' : 'Coletando leads...'}
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

      {summary && (
        <Card className="border-emerald-200 bg-emerald-50/50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 mb-4">
              <CheckCircle className="h-6 w-6 text-emerald-600" />
              <h3 className="text-lg font-semibold text-emerald-800">
                {mode === 'reanalyze' ? 'Reanálise finalizada' : 'Coleta finalizada'}
              </h3>
            </div>
            <div className="grid grid-cols-3 gap-4 text-center mb-4">
              <div className="rounded-lg bg-white p-3 shadow-sm">
                <div className="text-2xl font-bold">{summary.collected}</div>
                <div className="text-sm text-muted-foreground">Coletados</div>
              </div>
              <div className="rounded-lg bg-white p-3 shadow-sm">
                <div className="text-2xl font-bold text-emerald-600">{summary.qualified}</div>
                <div className="text-sm text-muted-foreground">Qualificados</div>
              </div>
              <div className="rounded-lg bg-white p-3 shadow-sm">
                <div className="text-2xl font-bold">{summary.total_processed}</div>
                <div className="text-sm text-muted-foreground">Processados</div>
              </div>
            </div>
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
                {events.map((event, i) => {
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
                    const scoreColor = (event.score || 0) >= 60 ? 'text-emerald-500' : 'text-amber-500';
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
