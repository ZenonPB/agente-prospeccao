'use client';

import { ThemeProvider } from "@/components/theme-provider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SessionProvider } from "next-auth/react";
import type { Session } from "next-auth";
import { useState } from "react";

export function Providers({ children, session }: { children: React.ReactNode; session?: Session | null }) {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <SessionProvider session={session}>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider
          defaultTheme="alpha"
          storageKey="app-theme"
        >
          <TooltipProvider>
            {children}
          </TooltipProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </SessionProvider>
  );
}