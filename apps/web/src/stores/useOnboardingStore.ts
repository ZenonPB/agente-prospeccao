import { create } from 'zustand';
import { OnboardingStatus } from '@/types';

const STORAGE_KEY = 'agente_onboarding_status_v1';
const STEP_STORAGE_KEY = 'agente_onboarding_current_step_v1';

interface OnboardingState {
  status: OnboardingStatus;
  currentStepIndex: number;
  isActive: boolean;
  isWaitingForElement: boolean;
  
  startTour: (fromStepIndex?: number) => void;
  nextStep: () => void;
  prevStep: () => void;
  skipTour: () => void;
  completeTour: () => void;
  resetTour: () => void;
  
  setStatus: (status: OnboardingStatus) => void;
  setStepIndex: (index: number) => void;
  setIsWaitingForElement: (waiting: boolean) => void;
}

const getInitialStatus = (): OnboardingStatus => {
  if (typeof window === 'undefined') return 'NOT_STARTED';
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === 'COMPLETED' || saved === 'DISMISSED' || saved === 'IN_PROGRESS' || saved === 'NOT_STARTED') {
    return saved as OnboardingStatus;
  }
  return 'NOT_STARTED';
};

const getInitialStep = (): number => {
  if (typeof window === 'undefined') return 0;
  const saved = localStorage.getItem(STEP_STORAGE_KEY);
  const parsed = saved ? parseInt(saved, 10) : 0;
  return isNaN(parsed) ? 0 : parsed;
};

export const useOnboardingStore = create<OnboardingState>((set, get) => ({
  status: getInitialStatus(),
  currentStepIndex: getInitialStep(),
  isActive: false,
  isWaitingForElement: false,

  startTour: (fromStepIndex = 0) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, 'IN_PROGRESS');
      localStorage.setItem(STEP_STORAGE_KEY, String(fromStepIndex));
    }
    set({
      status: 'IN_PROGRESS',
      currentStepIndex: fromStepIndex,
      isActive: true,
      isWaitingForElement: false,
    });
  },

  nextStep: () => {
    const nextIndex = get().currentStepIndex + 1;
    if (typeof window !== 'undefined') {
      localStorage.setItem(STEP_STORAGE_KEY, String(nextIndex));
    }
    set({ currentStepIndex: nextIndex, isWaitingForElement: false });
  },

  prevStep: () => {
    const prevIndex = Math.max(0, get().currentStepIndex - 1);
    if (typeof window !== 'undefined') {
      localStorage.setItem(STEP_STORAGE_KEY, String(prevIndex));
    }
    set({ currentStepIndex: prevIndex, isWaitingForElement: false });
  },

  skipTour: () => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, 'DISMISSED');
      localStorage.removeItem(STEP_STORAGE_KEY);
    }
    set({
      status: 'DISMISSED',
      isActive: false,
      isWaitingForElement: false,
    });
  },

  completeTour: () => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, 'COMPLETED');
      localStorage.removeItem(STEP_STORAGE_KEY);
    }
    set({
      status: 'COMPLETED',
      isActive: false,
      isWaitingForElement: false,
    });
  },

  resetTour: () => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, 'NOT_STARTED');
      localStorage.setItem(STEP_STORAGE_KEY, '0');
    }
    set({
      status: 'NOT_STARTED',
      currentStepIndex: 0,
      isActive: true,
      isWaitingForElement: false,
    });
  },

  setStatus: (status) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, status);
    }
    set({ status });
  },

  setStepIndex: (index) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STEP_STORAGE_KEY, String(index));
    }
    set({ currentStepIndex: index });
  },

  setIsWaitingForElement: (isWaitingForElement) => set({ isWaitingForElement }),
}));
