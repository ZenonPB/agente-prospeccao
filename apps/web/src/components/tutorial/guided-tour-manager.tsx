'use client';

import { useEffect, useMemo, useRef } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { driver, Driver } from 'driver.js';
import { TOUR_STEPS } from '@/config/tour-steps';
import { useOnboardingStore } from '@/stores/useOnboardingStore';
import { useUserMe, useUpdateOnboardingStatus, useOrgMembership } from '@/hooks/use-api';
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

  const visibleSteps = useMemo(
    () => TOUR_STEPS.filter((step) => !step.analystOnly || !isConsultantOnly),
    [isConsultantOnly],
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
    if (pathname !== currentStep.targetRoute && !isNavigatingRef.current) {
      isNavigatingRef.current = true;
      setIsWaitingForElement(true);
      if (driverRef.current) {
        driverRef.current.destroy();
        driverRef.current = null;
      }
      router.push(currentStep.targetRoute);
      return;
    }

    let isSubscribed = true;

    async function highlightStep() {
      setIsWaitingForElement(true);
      const element = await waitForElement(currentStep.elementSelector);

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
        // "Voltar" navega para outra etapa/rota do tour, re-habilitamos aqui.
        onPopoverRender: (popover) => {
          popover.previousButton.disabled = isFirst;
          popover.previousButton.classList.toggle('driver-popover-btn-disabled', isFirst);
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
    setIsWaitingForElement,
    nextStep,
    prevStep,
    completeTour,
    skipTour,
    updateStatus,
  ]);

  if (!isActive) return null;

  return null;
}
