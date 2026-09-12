'use client';

import { ThemeProvider } from "@/components/theme-provider";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  ACTIVE_ORGANIZATION_CHANGED_EVENT,
  isActiveOrganizationStorageEvent,
} from "@/lib/active-organization";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SessionProvider } from "next-auth/react";
import type { Session } from "next-auth";
import { useEffect, useState } from "react";

function WorkspaceQueryBoundary({
  queryClient,
  children,
}: {
  queryClient: QueryClient;
  children: React.ReactNode;
}) {
  useEffect(() => {
    let generation = 0;

    const resetWorkspaceQueries = () => {
      generation += 1;
      const currentGeneration = generation;

      void (async () => {
        // Evita que uma resposta iniciada no workspace anterior seja gravada
        // no cache depois da troca. Em seguida, remove os dados visíveis e
        // refaz apenas as queries que continuam montadas.
        await queryClient.cancelQueries();
        if (currentGeneration !== generation) return;
        await queryClient.resetQueries(undefined, { cancelRefetch: true });
      })();
    };

    const handleStorage = (event: StorageEvent) => {
      if (isActiveOrganizationStorageEvent(event)) {
        resetWorkspaceQueries();
      }
    };

    window.addEventListener(ACTIVE_ORGANIZATION_CHANGED_EVENT, resetWorkspaceQueries);
    window.addEventListener("storage", handleStorage);

    return () => {
      generation += 1;
      window.removeEventListener(ACTIVE_ORGANIZATION_CHANGED_EVENT, resetWorkspaceQueries);
      window.removeEventListener("storage", handleStorage);
    };
  }, [queryClient]);

  return children;
}

export function Providers({ children, session }: { children: React.ReactNode; session?: Session | null }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  }));

  return (
    <SessionProvider session={session}>
      <QueryClientProvider client={queryClient}>
        <WorkspaceQueryBoundary queryClient={queryClient}>
          <ThemeProvider
            defaultTheme="alpha"
            storageKey="app-theme"
          >
            <TooltipProvider>
              {children}
            </TooltipProvider>
          </ThemeProvider>
        </WorkspaceQueryBoundary>
      </QueryClientProvider>
    </SessionProvider>
  );
}
