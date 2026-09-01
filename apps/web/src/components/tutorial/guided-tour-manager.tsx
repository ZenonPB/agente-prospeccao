'use client';

import { useEffect, useMemo, useRef, useCallback } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { driver, Driver } from 'driver.js';
import { Loader2, Compass } from 'lucide-react';
import { TOUR_STEPS, type TourStep } from '@/config/tour-steps';
import { useOnboardingStore } from '@/stores/useOnboardingStore';
import { useUserMe, useUpdateOnboardingStatus, useOrgMembership, useCampaigns } from '@/hooks/use-api';
import { toast } from 'sonner';
import './tour-styles.css';

function waitForElement(selector: string, timeout = 4000): Promise<HTMLElement | null> {
  return new Promise((resolve) => {
    const el = document.querySelector(selector) as HTMLElement | null;
    if (el && el.offsetWidth > 0 && el.offsetHeight > 0) {
      resolve(el);
      return;
    }

    const startTime = Date.now();
    const observer = new MutationObserver(() => {
      const target = document.querySelector(selector) as HTMLElement | null;
      if (target && target.offsetWidth > 0 && target.offsetHeight > 0) {
        observer.disconnect();
        resolve(target);
      } else if (Date.now() - startTime > timeout) {
        observer.disconnect();
        resolve(null);
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
    });

    setTimeout(() => {
      observer.disconnect();
      const fallback = document.querySelector(selector) as HTMLElement | null;
      resolve(fallback);
    }, timeout);
  });
}

export function GuidedTourManager() {
  const router = useRouter();
  const pathname = usePathname();
  const { data: userData } = useUserMe();
  const { data: membership } = useOrgMembership();
  const { mutate: updateStatus } = useUpdateOnboardingStatus();
  
  const {
    status,
    currentStepIndex,
    isActive,
    isWaitingForElement,
    startTour,
    nextStep,
    prevStep,
    skipTour,
    completeTour,
    setStatus,
    setIsWaitingForElement,
  } = useOnboardingStore();

  const driverRef = useRef<Driver | null>(null);
  const isNavigatingRef = useRef(false);

  const isConsultantOnly =
    membership?.membership?.sales_role === 'CONSULTOR' &&
    membership?.membership?.role !== 'OWNER' &&
    membership?.membership?.role !== 'ADMIN';

  // Rotas dinâmicas: o detalhe da primeira campanha (id real varia por org).
  const { data: campaignsData, isLoading: campaignsLoading } = useCampaigns({ limit: 1 });
  const firstCampaignId = campaignsData?.campaigns?.[0]?.id ?? null;
  const campaignsSettled = !campaignsLoading;

  const resolveRoute = useCallback(
    (step: TourStep): string | null => {
      if (step.routeResolver === 'first-campaign') {
        return firstCampaignId ? `/campanhas/${firstCampaignId}` : null;
      }
      return step.targetRoute;
    },
    [firstCampaignId],
  );

  const visibleSteps = useMemo(
    () =>
      TOUR_STEPS.filter((step) => {
        if (step.analystOnly && isConsultantOnly) return false;
        // Sem campanha (consultado e vazio), o passo dinâmico é pulado.
        if (step.routeResolver && campaignsSettled && resolveRoute(step) === null) return false;
        return true;
      }),
    [isConsultantOnly, campaignsSettled, resolveRoute],
  );

  // Sincroniza status inicial vindo do backend se o local storage não tiver registrado
  useEffect(() => {
    if (userData?.onboarding_status && status === 'NOT_STARTED') {
      if (userData.onboarding_status === 'COMPLETED' || userData.onboarding_status === 'DISMISSED') {
        setStatus(userData.onboarding_status);
      } else if (userData.onboarding_status === 'NOT_STARTED') {
        // Primeiro acesso: inicia o tutorial automaticamente
        startTour(0);
      }
    }
  }, [userData, status, setStatus, startTour]);

  // Instancia/gerencia driver.js
  useEffect(() => {
    if (!isActive || currentStepIndex < 0 || currentStepIndex >= visibleSteps.length) {
      if (driverRef.current) {
        driverRef.current.destroy();
        driverRef.current = null;
      }
      return;
    }

    const currentStep = visibleSteps[currentStepIndex];
    if (!currentStep) return;

    // Se estiver em outra rota, dispara a navegação antes de destacar. O
    // driver é destruído aqui para o overlay antigo não bloquear a nova página.
    const targetRoute = resolveRoute(currentStep);
    if (targetRoute === null) {
      // Rota dinâmica ainda resolvendo (campanhas carregando): aguarda.
      setIsWaitingForElement(true);
      return;
    }
    if (pathname !== targetRoute && !isNavigatingRef.current) {
      isNavigatingRef.current = true;
      setIsWaitingForElement(true);
      if (driverRef.current) {
        driverRef.current.destroy();
        driverRef.current = null;
      }
      router.push(targetRoute);
      return;
    }

    let isSubscribed = true;

    async function highlightStep() {
      setIsWaitingForElement(true);
      // Passos sem seletor (boas-vindas/encerramento) ficam centralizados.
      const element = currentStep.elementSelector
        ? await waitForElement(currentStep.elementSelector)
        : null;

      if (!isSubscribed) return;
      setIsWaitingForElement(false);
      isNavigatingRef.current = false;

      if (driverRef.current) {
        driverRef.current.destroy();
      }

      const isFirst = currentStepIndex === 0;
      const isLast = currentStepIndex === visibleSteps.length - 1;

      driverRef.current = driver({
        animate: true,
        smoothScroll: true,
        allowClose: true,
        overlayColor: 'rgba(0, 0, 0, 0.65)',
        stagePadding: 6,
        popoverClass: 'agente-tour-popover',
        onCloseClick: () => {
          skipTour();
          updateStatus('DISMISSED');
        },
        onDestroyStarted: () => {
          if (driverRef.current) {
            driverRef.current.destroy();
            driverRef.current = null;
          }
        },
        // O driver.js desabilita o botão anterior quando a instância tem um
        // único passo (é o nosso caso — um driver por etapa do tour). Como o
        // "Voltar" navega para outra etapa/rota do tour, re-habilitamos aqui
        // e injetamos a barra de progresso do tour.
        onPopoverRender: (popover) => {
          popover.previousButton.disabled = isFirst;
          popover.previousButton.classList.toggle('driver-popover-btn-disabled', isFirst);

          const pct = ((currentStepIndex + 1) / visibleSteps.length) * 100;
          let track = popover.wrapper.querySelector<HTMLDivElement>('.agente-tour-progress');
          if (!track) {
            track = document.createElement('div');
            track.className = 'agente-tour-progress';
            popover.wrapper.insertBefore(track, popover.footer);
          }
          track.innerHTML = `<span class="agente-tour-progress-fill" style="width:${pct}%"></span>`;
        },
        steps: [
          {
            element: element || undefined,
            popover: {
              title: currentStep.title,
              description: currentStep.description,
              side: currentStep.popoverSide || 'bottom',
              align: currentStep.popoverAlign || 'start',
              nextBtnText: isLast ? 'Concluir' : 'Próximo →',
              prevBtnText: isFirst ? '' : '← Voltar',
              progressText: `${currentStepIndex + 1} de ${visibleSteps.length}`,
              onNextClick: () => {
                if (isLast) {
                  completeTour();
                  updateStatus('COMPLETED');
                  if (driverRef.current) driverRef.current.destroy();
                  toast.success('Tour concluído! 🎉', {
                    description: 'Agora é com você — comece criando sua primeira busca.',
                  });
                } else {
                  nextStep();
                }
              },
              onPrevClick: () => {
                if (!isFirst) {
                  prevStep();
                }
              },
            },
          },
        ],
      });

      driverRef.current.drive(0);
    }

    highlightStep();

    return () => {
      isSubscribed = false;
    };
  }, [
    isActive,
    currentStepIndex,
    pathname,
    router,
    visibleSteps,
    resolveRoute,
    setIsWaitingForElement,
    nextStep,
    prevStep,
    completeTour,
    skipTour,
    updateStatus,
  ]);

  if (!isActive) return null;

  // Entre uma parada e outra (navegação de rota / espera de elemento) o
  // overlay do driver fica fora do ar — este indicador cobre o vácuo e
  // evita a sensação de tour " piscando ".
  if (isWaitingForElement) {
    return (
      <div
        className="animate-fade-in fixed bottom-6 left-1/2 z-[100001] flex -translate-x-1/2 items-center gap-2.5 rounded-full border bg-card px-4 py-2.5 shadow-[var(--shadow-lift)]"
        role="status"
        aria-live="polite"
      >
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        <span className="text-sm font-medium text-foreground">Preparando a próxima parada…</span>
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <Compass className="h-3.5 w-3.5" />
          Etapa {Math.min(currentStepIndex + 1, visibleSteps.length)} de {visibleSteps.length}
        </span>
      </div>
    );
  }

  return null;
}
