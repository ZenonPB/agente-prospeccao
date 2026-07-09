'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Pause, RotateCcw, CheckCircle, XCircle, Loader2 } from 'lucide-react';

interface PipelineStep {
  id: string;
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error';
  count?: number;
  details?: string;
}

const pipelineSteps: PipelineStep[] = [
  { id: '1', name: 'Conectado ao Google Maps', status: 'completed' },
  { id: '2', name: 'Buscando leads em Araraquara, SP', status: 'completed', count: 29, details: '29 estabelecimentos encontrados' },
  { id: '3', name: 'Coletando informações', status: 'completed', count: 12, details: '12 leads selecionados' },
  { id: '4', name: 'Analisando sites', status: 'in_progress', count: 8, details: '8 de 12 concluídos' },
  { id: '5', name: 'Calculando aptidão', status: 'pending' },
];

const statusConfig = {
  pending: { icon: <div className="h-4 w-4 rounded-full border-2 border-muted" />, label: 'Aguardando' },
  in_progress: { icon: <Loader2 className="h-4 w-4 animate-spin text-primary" />, label: 'Em andamento' },
  completed: { icon: <CheckCircle className="h-4 w-4 text-emerald-500" />, label: 'Concluído' },
  error: { icon: <XCircle className="h-4 w-4 text-red-500" />, label: 'Erro' },
};

export function PipelineMonitor() {
  const completedSteps = pipelineSteps.filter((s) => s.status === 'completed').length;
  const progress = (completedSteps / pipelineSteps.length) * 100;

  return (
    <div className="space-y-6">
      {/* Progress Bar */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle>Busca em Andamento</CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" className="h-9">
                <Pause className="mr-2 h-4 w-4" />
                Pausar
              </Button>
              <Button variant="outline" size="sm" className="h-9">
                <RotateCcw className="mr-2 h-4 w-4" />
                Recomeçar
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

      {/* Pipeline Steps */}
      <Card>
        <CardHeader>
          <CardTitle>Etapas da Busca</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {pipelineSteps.map((step) => {
              const config = statusConfig[step.status];
              return (
                <div
                  key={step.id}
                  className="flex items-start gap-4 rounded-lg border p-4"
                >
                  <div className="mt-0.5">{config.icon}</div>
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{step.name}</span>
                      {step.count && (
                        <Badge variant="secondary">{step.count}</Badge>
                      )}
                    </div>
                    {step.details && (
                      <p className="mt-1 text-sm text-muted-foreground">{step.details}</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Real-time Log */}
      <Card>
        <CardHeader>
          <CardTitle>Andamento em Tempo Real</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] overflow-y-auto rounded-lg bg-muted/50 p-4 font-mono text-sm">
            <div className="space-y-1">
              <p><span className="text-emerald-500">✓</span> Conectado ao Google Maps</p>
              <p><span className="text-blue-500">🔍</span> Buscando leads em Araraquara, SP...</p>
              <p><span className="text-emerald-500">✓</span> 29 estabelecimentos encontrados</p>
              <p><span className="text-blue-500">📋</span> Coletando informações...</p>
              <p><span className="text-emerald-500">✓</span> Tijuca Restaurante & Bar — coletado</p>
              <p><span className="text-emerald-500">✓</span> Restaurante Pau Seco — coletado</p>
              <p><span className="text-amber-500">⏳</span> KIBELANCHE — processando...</p>
              <p><span className="text-blue-500">🔒</span> Analisando site...</p>
              <p><span className="text-emerald-500">✓</span> Tijuca Restaurante & Bar</p>
              <p className="pl-4">Certificado SSL: ❌ Inexistente</p>
              <p className="pl-4">Segurança: ⚠️ 2 itens ausentes</p>
              <p className="pl-4">Arquivos expostos: ❌ /robots.txt</p>
              <p><span className="text-emerald-500">✓</span> Restaurante Pau Seco</p>
              <p className="pl-4">Certificado SSL: ❌ Inexistente</p>
              <p><span className="text-blue-500">🤖</span> Calculando aptidão...</p>
              <p><span className="text-emerald-500">✓</span> Tijuca — Aptidão: 74 (Apto)</p>
              <p><span className="text-emerald-500">✓</span> Pau Seco — Aptidão: 88 (Apto)</p>
              <p><span className="text-emerald-500">✓</span> Busca finalizada</p>
              <p className="font-bold">12 leads | 9 aptos | 3 inaptos</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}