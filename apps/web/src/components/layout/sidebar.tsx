'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  Megaphone,
  Target,
  DollarSign,
  Settings,
  Users,
  BarChart3,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAppStore } from '@/stores/useAppStore';
import { useOrgMembership } from '@/hooks/use-api';
import { OrgSwitcher } from './org-switcher';
import { BrandMark } from './brand-mark';

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  analystOnly?: boolean;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    label: 'Visão',
    items: [{ name: 'Visão Geral', href: '/dashboard', icon: LayoutDashboard }],
  },
  {
    label: 'Operação',
    items: [
      { name: 'Campanhas', href: '/campanhas', icon: Megaphone },
      { name: 'Oportunidades', href: '/oportunidades', icon: Target },
      { name: 'Negociações', href: '/vendas', icon: DollarSign },
    ],
  },
  {
    label: 'Inteligência',
    items: [{ name: 'Relatórios', href: '/relatorios', icon: BarChart3, analystOnly: true }],
  },
  {
    label: 'Gestão',
    items: [
      { name: 'Equipe', href: '/configuracoes/membros', icon: Users },
      { name: 'Configurações', href: '/configuracoes', icon: Settings },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, toggleSidebar } = useAppStore();
  const { data: membership } = useOrgMembership();

  const canViewAnalytics =
    membership?.membership?.role === 'OWNER' ||
    membership?.membership?.role === 'ADMIN' ||
    membership?.membership?.sales_role === 'ANALYST' ||
    membership?.membership?.sales_role === 'MANAGER';

  const visibleGroups = navGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => !item.analystOnly || canViewAnalytics),
    }))
    .filter((group) => group.items.length > 0);

  return (
    <>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={toggleSidebar} />
      )}

      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex flex-col border-r bg-sidebar text-sidebar-foreground transition-all duration-300 lg:relative",
          sidebarOpen ? "w-64" : "w-16",
          "lg:translate-x-0",
          !sidebarOpen && "max-lg:-translate-x-full",
        )}
      >
        {/* Brand */}
        <div className="flex h-16 items-center gap-2.5 border-b border-sidebar-border px-4">
          {sidebarOpen && (
            <Link href="/dashboard" className="flex items-center gap-2.5 overflow-hidden">
              <BrandMark className="h-7 w-7 shrink-0 text-sidebar-primary" />
              <span className="truncate text-[15px] font-semibold tracking-tight text-sidebar-foreground">
                Agente Prospecção
              </span>
            </Link>
          )}
          {!sidebarOpen && (
            <Link href="/dashboard" className="mx-auto">
              <BrandMark className="h-7 w-7 text-sidebar-primary" />
            </Link>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className={cn(
              "ml-auto h-9 w-9 shrink-0 text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
              !sidebarOpen && "ml-0",
            )}
            aria-label={sidebarOpen ? 'Recolher menu' : 'Expandir menu'}
          >
            {sidebarOpen ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </Button>
        </div>

        {/* Org Switcher */}
        <div className="border-b border-sidebar-border p-2">
          <OrgSwitcher collapsed={!sidebarOpen} />
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-4 overflow-y-auto p-2">
          {visibleGroups.map((group) => (
            <div key={group.label} className="space-y-0.5">
              {sidebarOpen && (
                <p className="px-3 pb-1 text-[11px] font-medium uppercase tracking-wider text-sidebar-foreground/40">
                  {group.label}
                </p>
              )}
              {group.items.map((item) => {
                const isActive =
                  pathname === item.href || pathname.startsWith(item.href + '/');
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={cn(
                      "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                      sidebarOpen ? "pl-3" : "justify-center",
                      isActive
                        ? "bg-sidebar-accent text-sidebar-accent-foreground"
                        : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
                    )}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    {/* Sinal da página ativa */}
                    {isActive && (
                      <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-sidebar-primary" />
                    )}
                    <item.icon
                      className={cn(
                        "h-5 w-5 shrink-0",
                        isActive ? "text-sidebar-primary" : "text-sidebar-foreground/60 group-hover:text-sidebar-foreground",
                      )}
                    />
                    {sidebarOpen && <span className="truncate">{item.name}</span>}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="border-t border-sidebar-border p-4">
          {sidebarOpen && (
            <p className="text-xs text-sidebar-foreground/40">
              Inteligência comercial para sua empresa
            </p>
          )}
        </div>
      </div>
    </>
  );
}
