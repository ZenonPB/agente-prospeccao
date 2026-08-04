'use client';

import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Pause, Loader2, Play } from 'lucide-react';
import { useStartPipeline } from '@/hooks/use-api';
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

export function PipelineMonitor() {
  const [query, setQuery] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState('');
  const [summary, setSummary] = useState<PipelineEvent['summary'] | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const startPipeline = useStartPipeline();

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
        }
      };

      ws.onerror = () => {
        setIsRunning(false);
        setEvents((prev) => [...prev, { type: 'error', message: 'Erro na conexão WebSocket' }]);
      };

      ws.onclose = () => {
        setIsRunning(false);
      };
    } catch {
      setIsRunning(false);
      setEvents((prev) => [...prev, { type: 'error', message: 'Erro ao iniciar pipeline' }]);
    }
  };

  const handleStop = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
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

      {/* Progress Bar */}
      {(isRunning || events.length > 0) && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <CardTitle>Busca em Andamento</CardTitle>
              {summary && (
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
            {summary && (
              <div className="mt-4 grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-2xl font-bold">{summary.collected}</div>
                  <div className="text-sm text-muted-foreground">Coletados</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-emerald-600">{summary.qualified}</div>
                  <div className="text-sm text-muted-foreground">Aptos</div>
                </div>
                <div>
                  <div className="text-2xl font-bold">{summary.total_processed}</div>
                  <div className="text-sm text-muted-foreground">Analisados</div>
                </div>
              </div>
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
                {events.map((event, i) => {
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
                    const scoreColor = (event.score || 0) >= 60 ? 'text-emerald-500' : 'text-amber-500';
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