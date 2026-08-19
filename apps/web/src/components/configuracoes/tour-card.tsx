'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { HelpCircle, RotateCcw } from 'lucide-react';
import { useOnboardingStore } from '@/stores/useOnboardingStore';
import { useUpdateOnboardingStatus } from '@/hooks/use-api';
import { toast } from 'sonner';

export function TourCard() {
  const { resetTour } = useOnboardingStore();
  const updateStatusMutation = useUpdateOnboardingStatus();

  const handleRestartTour = () => {
    resetTour();
    updateStatusMutation.mutate('NOT_STARTED');
    toast.success('Tutorial guiado reiniciado!');
  };

  return (
    <Card data-tour="configuracoes-tour-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <HelpCircle className="h-5 w-5 text-primary" />
          Tutorial Interativo
        </CardTitle>
        <CardDescription>
          Aprenda como utilizar as principais funcionalidades da plataforma com o tour passo a passo.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Você pode refazer o tutorial guiado a qualquer momento para relembrar o fluxo de trabalho e as recursos do sistema.
        </p>
        <Button onClick={handleRestartTour} variant="outline" className="gap-2">
          <RotateCcw className="h-4 w-4" />
          Refazer Tutorial Guiado
        </Button>
      </CardContent>
    </Card>
  );
}
