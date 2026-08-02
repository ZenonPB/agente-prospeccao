'use client';

import { cn } from '@/lib/utils';
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '@/components/ui/tooltip';
import type { SalesRole } from '@/types';

const ROLE_META: Record<SalesRole, { label: string; className: string; description: string }> = {
  CONSULTOR: {
    label: 'Consultor',
    className: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300',
    description: 'Opera o próprio funil e pode se auto-atribuir leads não atribuídos.',
  },
  ANALYST: {
    label: 'Analista',
    className: 'bg-sky-100 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300',
    description: 'Enxerga todos os leads da organização e acessa relatórios BI.',
  },
  MANAGER: {
    label: 'Gestor',
    className: 'bg-violet-100 text-violet-700 dark:bg-violet-950/60 dark:text-violet-300',
    description: 'Acesso total, relatórios BI e gestão de papéis da equipe.',
  },
};

export function SalesRoleBadge({
  role,
  showLabel = true,
  className,
}: {
  role?: SalesRole | string | null;
  showLabel?: boolean;
  className?: string;
}) {
  const meta = ROLE_META[(role as SalesRole) || 'CONSULTOR'] || ROLE_META.CONSULTOR;

  const badge = (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
        meta.className,
        className
      )}
    >
      {showLabel ? meta.label : null}
    </span>
  );

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger render={badge} />
        <TooltipContent>{meta.description}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
