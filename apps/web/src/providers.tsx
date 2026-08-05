'use client';

import { ThemeProvider as NextThemesProvider } from 'next-themes';

export function ThemeProvider({ children, ...props }: React.ComponentProps<typeof NextThemesProvider>) {
  return (
    <NextThemesProvider 
      storageKey="app-theme" 
      themes={['light', 'dark', 'alpha']}
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}