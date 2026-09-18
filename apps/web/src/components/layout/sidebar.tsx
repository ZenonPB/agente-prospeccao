'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  Megaphone,
  Target,
  Search as SearchIcon,
  DollarSign,
  Settings,
  Users,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  Layers,
  HelpCircle,
  Database,
  DatabaseZap,
  Radar,
  Route,
  PlugZap,
  TrendingUp,
  BriefcaseBusiness,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAppStore } from '@/stores/useAppStore';
import { useOrgMembership } from '@/hooks/use-api';
import { OrgSwitcher } from './org-switcher';
import { BrandLogo } from './brand-logo';

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  analystOnly?: boolean;
  exact?: boolean;
}
interface NavGroup { label: string; items: NavItem[]; }

const navGroups: NavGroup[] = [
  { label: 'Hoje', items: [{ name: 'Resumo', href: '/dashboard', icon: LayoutDashboard }] },
  {
    label: 'Prospecção e vendas',
    items: [
      { name: 'Minha carteira', href: '/crm', icon: BriefcaseBusiness, exact: true },
      { name: 'Encontrar novos clientes', href: '/campanhas', icon: Megaphone },
      { name: 'Pesquisar na base', href: '/buscar', icon: SearchIcon },
      { name: 'Oportunidades', href: '/oportunidades', icon: Target },
      { name: 'Próximos contatos', href: '/sequences', icon: Route },
      { name: 'Negociações', href: '/vendas', icon: DollarSign },
    ],
  },
  {
    label: 'Análise e melhoria',
    items: [
      { name: 'Monitorar oportunidades', href: '/monitoramento', icon: Radar, analystOnly: true },
      { name: 'O que está funcionando', href: '/inteligencia-comercial', icon: TrendingUp, analystOnly: true },
      { name: 'Resultados', href: '/relatorios', icon: BarChart3, analystOnly: true },
      { name: 'Qualidade dos dados', href: '/data-health', icon: DatabaseZap, analystOnly: true },
      { name: 'Base de empresas', href: '/base-empresas', icon: Database, analystOnly: true },
    ],
  },
  {
    label: 'Administração',
    items: [
      { name: 'Serviços e soluções', href: '/configuracoes/vertentes', icon: Layers },
      { name: 'Equipe', href: '/configuracoes/membros', icon: Users },
      { name: 'Integrações', href: '/integracoes', icon: PlugZap, analystOnly: true },
      { name: 'Configurações', href: '/configuracoes', icon: Settings, exact: true },
    ],
  },
  { label: 'Ajuda', items: [{ name: 'Como usar', href: '/ajuda', icon: HelpCircle }] },
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
    .map((group) => ({ ...group, items: group.items.filter((item) => !item.analystOnly || canViewAnalytics) }))
    .filter((group) => group.items.length > 0);

  return (
    <>
      {sidebarOpen && <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={toggleSidebar} />}
      <div className={cn(
        'fixed inset-y-0 left-0 z-50 flex flex-col border-r bg-sidebar text-sidebar-foreground transition-all duration-300 lg:relative',
        sidebarOpen ? 'w-64' : 'w-16',
        'lg:translate-x-0',
        !sidebarOpen && 'max-lg:-translate-x-full',
      )}>
        <div className="flex h-16 items-center gap-2.5 border-b border-sidebar-border px-4">
          {sidebarOpen ? (
            <Link href="/dashboard" className="flex items-center gap-2.5 overflow-hidden">
              <BrandLogo className="h-7 w-7 text-sidebar-primary" />
              <span className="truncate text-[15px] font-semibold tracking-tight text-sidebar-foreground">Prospect.ai</span>
            </Link>
          ) : (
            <Link href="/dashboard" className="mx-auto"><BrandLogo className="h-7 w-7 text-sidebar-primary" /></Link>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className={cn('ml-auto h-9 w-9 shrink-0 text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground', !sidebarOpen && 'ml-0')}
            aria-label={sidebarOpen ? 'Recolher menu' : 'Expandir menu'}
          >
            {sidebarOpen ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </Button>
        </div>
        <div className="border-b border-sidebar-border p-2"><OrgSwitcher collapsed={!sidebarOpen} /></div>
        <nav className="flex-1 space-y-4 overflow-y-auto p-2" aria-label="Navegação principal">
          {visibleGroups.map((group) => (
            <div key={group.label} className="space-y-0.5">
              {sidebarOpen && <p className="px-3 pb-1 text-[11px] font-medium uppercase tracking-wider text-sidebar-foreground/40">{group.label}</p>}
              {group.items.map((item) => {
                const isActive = item.exact ? pathname === item.href : pathname === item.href || pathname.startsWith(item.href + '/');
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={cn(
                      'group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                      sidebarOpen ? 'pl-3' : 'justify-center',
                      isActive ? 'bg-sidebar-accent text-sidebar-accent-foreground' : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground',
                    )}
                    aria-current={isActive ? 'page' : undefined}
                    title={sidebarOpen ? undefined : item.name}
                  >
                    {isActive && <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-sidebar-primary animate-scale-in" />}
                    <item.icon className={cn('h-5 w-5 shrink-0 transition-transform duration-300 group-hover:scale-110', isActive ? 'text-sidebar-primary' : 'text-sidebar-foreground/60 group-hover:text-sidebar-foreground')} />
                    {sidebarOpen ? <span className="truncate">{item.name}</span> : <span className="sr-only">{item.name}</span>}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="border-t border-sidebar-border p-4">
          {sidebarOpen ? (
            <p className="text-xs leading-relaxed text-sidebar-foreground/45">Dúvida? Abra <Link href="/ajuda" className="font-medium text-sidebar-foreground/70 hover:text-sidebar-foreground">Como usar</Link>.</p>
          ) : (
            <Link href="/ajuda" className="mx-auto flex h-8 w-8 items-center justify-center rounded-md text-sidebar-foreground/55 hover:bg-sidebar-accent" aria-label="Abrir ajuda"><HelpCircle className="h-4 w-4" /></Link>
          )}
        </div>
      </div>
    </>
  );
}
