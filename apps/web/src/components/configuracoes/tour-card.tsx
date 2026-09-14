'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { BookOpen, Play, RotateCcw } from 'lucide-react';
import { useOnboardingStore } from '@/stores/useOnboardingStore';
import { useUpdateOnboardingStatus } from '@/hooks/use-api';
import { TOUR_STEPS } from '@/config/tour-steps';
import { toast } from 'sonner';

export function TourCard() {
  const { status, currentStepIndex, startTour, resetTour } = useOnboardingStore();
  const updateStatus = useUpdateOnboardingStatus();
  const canResume = status === 'IN_PROGRESS' && currentStepIndex > 0;
  const progress = Math.min(currentStepIndex + 1, TOUR_STEPS.length);

  const handleStart = () => {
    if (canResume) {
      startTour(currentStepIndex);
      updateStatus.mutate('IN_PROGRESS');
      return;
    }
    resetTour();
    updateStatus.mutate('IN_PROGRESS');
    toast.success('Tutorial iniciado. Você pode pausar e continuar depois.');
  };

  const handleRestart = () => {
    resetTour();
    updateStatus.mutate('IN_PROGRESS');
    toast.success('Tutorial reiniciado do começo.');
  };

  return (
    <Card data-tour="configuracoes-tour-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><BookOpen className="h-5 w-5 text-primary" />Tutorial passo a passo</CardTitle>
        <CardDescription>
          Passe pelas áreas reais do sistema enquanto aprende o fluxo recomendado da AlphaMec.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-xl border bg-muted/30 p-4 text-sm">
          <p className="font-medium">
            {canResume ? `Você parou perto da etapa ${progress}.` : status === 'COMPLETED' ? 'Tutorial concluído.' : 'Leva poucos minutos e pode ser pausado.'}
          </p>
          <p className="mt-1 text-muted-foreground">Ele mostra onde buscar clientes, revisar leads, trabalhar a carteira, registrar vendas, acompanhar resultados e configurar a plataforma.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={handleStart} className="gap-2"><Play className="h-4 w-4" />{canResume ? 'Continuar de onde parei' : status === 'COMPLETED' ? 'Fazer novamente' : 'Começar tutorial'}</Button>
          {canResume ? <Button onClick={handleRestart} variant="outline" className="gap-2"><RotateCcw className="h-4 w-4" />Recomeçar</Button> : null}
        </div>
      </CardContent>
    </Card>
  );
}
