'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Megaphone, Target, DollarSign, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useOrgMembership } from '@/hooks/use-api';

const ITEMS = [
  { href: '/dashboard', label: 'Visão', icon: LayoutDashboard },
  { href: '/campanhas', label: 'Campanhas', icon: Megaphone },
  { href: '/oportunidades', label: 'Oportunidades', icon: Target },
  { href: '/vendas', label: 'Negociações', icon: DollarSign },
  { href: '/relatorios', label: 'Relatórios', icon: BarChart3, analystOnly: true },
];

export function MobileBottomNav() {
  const pathname = usePathname();
  const { data: membership } = useOrgMembership();

  const canViewAnalytics =
    membership?.membership?.role === 'OWNER' ||
    membership?.membership?.role === 'ADMIN' ||
    membership?.membership?.sales_role === 'ANALYST' ||
    membership?.membership?.sales_role === 'MANAGER';

  const items = ITEMS.filter((item) => !item.analystOnly || canViewAnalytics);

  return (
    <nav
      aria-label="Navegação principal mobile"
      className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
    >
      <ul className="flex items-stretch justify-around">
        {items.map((item) => {
          const isActive =
            pathname === item.href || pathname.startsWith(item.href + '/');
          return (
            <li key={item.href} className="min-w-0 flex-1">
              <Link
                href={item.href}
                className={cn(
                  'flex min-h-[64px] min-w-[44px] flex-col items-center justify-center gap-1 px-1 py-2 text-xs font-medium transition-colors',
                  isActive
                    ? 'text-primary'
                    : 'text-muted-foreground hover:text-foreground',
                )}
                aria-current={isActive ? 'page' : undefined}
              >
                <item.icon className="h-5 w-5" aria-hidden="true" />
                <span className="truncate">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}