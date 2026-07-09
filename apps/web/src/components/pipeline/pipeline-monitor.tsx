'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Pause, RotateCcw, CheckCircle, XCircle } from 'lucide-react';

interface PipelineStep {
  id: string;
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error';
  count?: number;
  details?: string;
}

const pipelineSteps: PipelineStep[] = [
  { id: '1', name: 'Conectado à Google Places API', status: 'completed' },
  { id: '2', name: 'Buscando "Restaurantes em Araraquara, SP"', status: 'completed', count: 29, details: '29 estabelecimentos encontrados' },
  { id: '3', name: 'Processando leads', status: 'completed', count: 12, details: '12 leads coletados' },
  { id: '4', name: 'Enriquecimento técnico', status: 'in_progress', count: 8, details: '8 de 12 processados' },
  { id: '5', name: 'Scoring com IA', status: 'pending' },
];

const statusIcons = {
  pending: <div className="h-4 w-4 rounded-full border-2 border-muted" />,
  in_progress: <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />,
  completed: <CheckCircle className="h-4 w-4 text-green-500" />,
  error: <XCircle className="h-4 w-4 text-red-500" />,
};

export function PipelineMonitor() {
  const completedSteps = pipelineSteps.filter((s) => s.status === 'completed').length;
  const progress = (completedSteps / pipelineSteps.length) * 100;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle>Pipeline em Tempo Real</CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="sm">
                <Pause className="mr-2 h-4 w-4" />
                Pausar
              </Button>
              <Button variant="outline" size="sm">
                <RotateCcw className="mr-2 h-4 w-4" />
                Reiniciar
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Progresso geral</span>
            <span className="font-medium">{Math.round(progress)}%</span>
          </div>
          <Progress value={progress} className="h-2" />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Etapas do Pipeline</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {pipelineSteps.map((step) => (
              <div key={step.id} className="flex items-start gap-4 rounded-lg border p-4">
                <div className="mt-1">{statusIcons[step.status]}</div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{step.name}</span>
                    {step.count && <Badge variant="secondary">{step.count}</Badge>}
                  </div>
                  {step.details && (
                    <p className="text-sm text-muted-foreground">{step.details}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Log em Tempo Real</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] overflow-y-auto rounded-lg bg-muted p-4 font-mono text-sm">
            <div className="space-y-1">
              <p><span className="text-green-500">✅</span> Conectado à Google Places API</p>
              <p><span className="text-blue-500">🔍</span> Buscando "Restaurantes em Araraquara, SP"...</p>
              <p><span className="text-green-500">✅</span> Encontrados 29 estabelecimentos</p>
              <p><span className="text-blue-500">📋</span> Processando leads...</p>
              <p><span className="text-green-500">✅</span> Tijuca Restaurante & Bar — coletado</p>
              <p><span className="text-green-500">✅</span> Restaurante Pau Seco — coletado</p>
              <p><span className="text-yellow-500">⏳</span> KIBELANCHE — processando...</p>
              <p><span className="text-blue-500">🔒</span> Iniciando enriquecimento técnico...</p>
              <p><span className="text-green-500">✅</span> Tijuca Restaurante & Bar — Score: 74 (QUALIFICADO)</p>
              <p><span className="text-green-500">✅</span> Restaurante Pau Seco — Score: 88 (QUALIFICADO)</p>
              <p><span className="text-green-500">✅</span> Pipeline finalizado</p>
              <p className="font-bold">12 leads coletados | 9 qualificados | 3 desqualificados</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}