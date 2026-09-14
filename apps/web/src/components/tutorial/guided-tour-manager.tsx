'use client';

import { useCallback, useEffect, useMemo, useRef } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { driver, Driver } from 'driver.js';
import { Compass, Loader2 } from 'lucide-react';
import { TOUR_STEPS, type TourStep } from '@/config/tour-steps';
import { useOnboardingStore } from '@/stores/useOnboardingStore';
import { useCampaigns, useOrgMembership, useUpdateOnboardingStatus, useUserMe } from '@/hooks/use-api';
import { toast } from 'sonner';
import './tour-styles.css';

function waitForElement(selector: string, timeout = 3500): Promise<HTMLElement | null> {
  return new Promise((resolve) => {
    const initial = document.querySelector(selector) as HTMLElement | null;
    if (initial && initial.offsetWidth > 0 && initial.offsetHeight > 0) return resolve(initial);

    const startedAt = Date.now();
    const observer = new MutationObserver(() => {
      const target = document.querySelector(selector) as HTMLElement | null;
      if (target && target.offsetWidth > 0 && target.offsetHeight > 0) {
        observer.disconnect();
        resolve(target);
      } else if (Date.now() - startedAt > timeout) {
        observer.disconnect();
        resolve(null);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true, attributes: true });
    setTimeout(() => {
      observer.disconnect();
      const fallback = document.querySelector(selector) as HTMLElement | null;
      resolve(fallback && fallback.offsetWidth > 0 ? fallback : null);
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
    pauseTour,
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

  const { data: campaignsData, isLoading: campaignsLoading } = useCampaigns({ limit: 1 });
  const firstCampaignId = campaignsData?.campaigns?.[0]?.id ?? null;
  const campaignsSettled = !campaignsLoading;

  const resolveRoute = useCallback((step: TourStep): string | null => {
    if (step.routeResolver === 'first-campaign') return firstCampaignId ? `/campanhas/${firstCampaignId}` : null;
    return step.targetRoute;
  }, [firstCampaignId]);

  const visibleSteps = useMemo(() => TOUR_STEPS.filter((step) => {
    if (step.analystOnly && isConsultantOnly) return false;
    if (step.routeResolver && campaignsSettled && resolveRoute(step) === null) return false;
    return true;
  }), [campaignsSettled, isConsultantOnly, resolveRoute]);

  useEffect(() => {
    if (!userData?.onboarding_status || status !== 'NOT_STARTED') return;
    if (userData.onboarding_status === 'COMPLETED' || userData.onboarding_status === 'DISMISSED') {
      setStatus(userData.onboarding_status);
      return;
    }
    if (userData.onboarding_status === 'NOT_STARTED') {
      startTour(0);
      updateStatus('IN_PROGRESS');
    }
  }, [setStatus, startTour, status, updateStatus, userData]);

  useEffect(() => {
    if (!isActive || currentStepIndex < 0 || currentStepIndex >= visibleSteps.length) {
      driverRef.current?.destroy();
      driverRef.current = null;
      return;
    }

    const currentStep = visibleSteps[currentStepIndex];
    if (!currentStep) return;
    const targetRoute = resolveRoute(currentStep);
    if (targetRoute === null) {
      setIsWaitingForElement(true);
      return;
    }
    if (pathname !== targetRoute && !isNavigatingRef.current) {
      isNavigatingRef.current = true;
      setIsWaitingForElement(true);
      driverRef.current?.destroy();
      driverRef.current = null;
      router.push(targetRoute);
      return;
    }

    let subscribed = true;
    const highlightStep = async () => {
      setIsWaitingForElement(true);
      const element = currentStep.elementSelector ? await waitForElement(currentStep.elementSelector) : null;
      if (!subscribed) return;
      setIsWaitingForElement(false);
      isNavigatingRef.current = false;
      driverRef.current?.destroy();

      const isFirst = currentStepIndex === 0;
      const isLast = currentStepIndex === visibleSteps.length - 1;
      driverRef.current = driver({
        animate: true,
        smoothScroll: true,
        allowClose: true,
        overlayColor: 'rgba(0, 0, 0, 0.68)',
        stagePadding: 8,
        popoverClass: 'agente-tour-popover',
        onCloseClick: () => {
          pauseTour();
          updateStatus('IN_PROGRESS');
          driverRef.current?.destroy();
          driverRef.current = null;
          toast.info('Tutorial pausado', { description: 'Você pode continuar de onde parou pela Central de ajuda, Configurações ou menu do perfil.' });
        },
        onDestroyStarted: () => {
          driverRef.current?.destroy();
          driverRef.current = null;
        },
        onPopoverRender: (popover) => {
          popover.previousButton.disabled = isFirst;
          popover.previousButton.classList.toggle('driver-popover-btn-disabled', isFirst);
          let chapter = popover.wrapper.querySelector<HTMLDivElement>('.agente-tour-chapter');
          if (!chapter) {
            chapter = document.createElement('div');
            chapter.className = 'agente-tour-chapter';
            popover.wrapper.insertBefore(chapter, popover.title);
          }
          chapter.textContent = currentStep.chapter;

          const pct = ((currentStepIndex + 1) / visibleSteps.length) * 100;
          let track = popover.wrapper.querySelector<HTMLDivElement>('.agente-tour-progress');
          if (!track) {
            track = document.createElement('div');
            track.className = 'agente-tour-progress';
            popover.wrapper.insertBefore(track, popover.footer);
          }
          track.innerHTML = `<span class="agente-tour-progress-fill" style="width:${pct}%"></span>`;
        },
        steps: [{
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
              if (!isLast) return nextStep();
              completeTour();
              updateStatus('COMPLETED');
              driverRef.current?.destroy();
              driverRef.current = null;
              toast.success('Tutorial concluído', { description: 'Quando precisar, você pode refazê-lo ou revisar o fluxo na Central de ajuda.' });
            },
            onPrevClick: () => { if (!isFirst) prevStep(); },
          },
        }],
      });
      driverRef.current.drive(0);
    };

    void highlightStep();
    return () => { subscribed = false; };
  }, [
    completeTour,
    currentStepIndex,
    isActive,
    nextStep,
    pathname,
    pauseTour,
    prevStep,
    resolveRoute,
    router,
    setIsWaitingForElement,
    updateStatus,
    visibleSteps,
  ]);

  if (!isActive) return null;
  if (isWaitingForElement) {
    const step = visibleSteps[Math.min(currentStepIndex, Math.max(visibleSteps.length - 1, 0))];
    return (
      <div className="animate-fade-in fixed bottom-6 left-1/2 z-[100001] flex max-w-[calc(100vw-2rem)] -translate-x-1/2 items-center gap-2.5 rounded-full border bg-card px-4 py-2.5 shadow-[var(--shadow-lift)]" role="status" aria-live="polite">
        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
        <span className="truncate text-sm font-medium text-foreground">Abrindo {step?.chapter?.toLowerCase() ?? 'a próxima etapa'}…</span>
        <span className="hidden items-center gap-1 text-xs text-muted-foreground sm:flex"><Compass className="h-3.5 w-3.5" />{Math.min(currentStepIndex + 1, visibleSteps.length)} de {visibleSteps.length}</span>
      </div>
    );
  }
  return null;
}
