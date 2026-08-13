"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useSyncExternalStore,
} from "react";

const THEMES = ["light", "dark", "alpha"];

interface ThemeContextValue {
  theme: string;
  setTheme: (theme: string) => void;
  resolvedTheme: string;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "light",
  setTheme: () => {},
  resolvedTheme: "light",
});

function readStoredTheme(storageKey: string, defaultTheme: string): string {
  if (typeof window === "undefined") return defaultTheme;
  try {
    const stored = window.localStorage.getItem(storageKey);
    return stored && THEMES.includes(stored) ? stored : defaultTheme;
  } catch {
    return defaultTheme;
  }
}

function applyThemeClass(theme: string, defaultTheme: string) {
  const root = document.documentElement;
  root.classList.remove(...THEMES);
  root.classList.add(THEMES.includes(theme) ? theme : defaultTheme);
}

interface ThemeProviderProps {
  children: React.ReactNode;
  defaultTheme?: string;
  storageKey?: string;
}

/**
 * Provider de tema próprio (light / dark / alpha), sem dependência externa.
 * O html recebe a classe do tema ativo (`.dark` / `.alpha`); o anti-flash é
 * injetado como script inline SSR no layout raiz.
 */
export function ThemeProvider({
  children,
  defaultTheme = "light",
  storageKey = "theme",
}: ThemeProviderProps) {
  const listenersRef = useRef(new Set<() => void>());
  const currentRef = useRef(defaultTheme);

  const setTheme = useCallback(
    (theme: string) => {
      const next = THEMES.includes(theme) ? theme : defaultTheme;
      currentRef.current = next;
      try {
        window.localStorage.setItem(storageKey, next);
      } catch {
        // localStorage indisponível — segue sem persistir.
      }
      applyThemeClass(next, defaultTheme);
      listenersRef.current.forEach((listener) => listener());
    },
    [defaultTheme, storageKey],
  );

  const subscribe = useCallback((listener: () => void) => {
    listenersRef.current.add(listener);
    return () => {
      listenersRef.current.delete(listener);
    };
  }, []);

  const getSnapshot = useCallback(() => currentRef.current, []);
  const getServerSnapshot = useCallback(() => defaultTheme, [defaultTheme]);

  const theme = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  useEffect(() => {
    setTheme(readStoredTheme(storageKey, defaultTheme));
  }, [setTheme, storageKey, defaultTheme]);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === storageKey) {
        setTheme(readStoredTheme(storageKey, defaultTheme));
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [setTheme, storageKey, defaultTheme]);

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, setTheme, resolvedTheme: theme }),
    [theme, setTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}