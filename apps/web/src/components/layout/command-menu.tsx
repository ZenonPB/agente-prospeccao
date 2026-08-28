'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  LayoutDashboard,
  Megaphone,
  Target,
  DollarSign,
  BarChart3,
  Settings,
  Users,
  Layers,
  Plus,
  CornerDownLeft,
} from 'lucide-react';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from '@/components/ui/command';
import { useOrgMembership } from '@/hooks/use-api';

interface CommandPage {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  keywords: string;
  analystOnly?: boolean;
}

const pages: CommandPage[] = [
  { name: 'Visão geral', href: '/dashboard', icon: LayoutDashboard, keywords: 'inicio home dashboard resumo' },
  { name: 'Campanhas', href: '/campanhas', icon: Megaphone, keywords: 'busca coleta prospeccao' },
  { name: 'Nova campanha', href: '/campanhas/nova', icon: Plus, keywords: 'criar busca nova prospeccao' },
  { name: 'Oportunidades', href: '/oportunidades', icon: Target, keywords: 'leads lista contatos' },
  { name: 'Negociações', href: '/vendas', icon: DollarSign, keywords: 'kanban vendas funnel pipeline' },
  { name: 'Relatórios', href: '/relatorios', icon: BarChart3, keywords: 'bi numeros resultados analise', analystOnly: true },
  { name: 'Vertentes', href: '/configuracoes/vertentes', icon: Layers, keywords: 'criterios scoring avaliacao ia' },
  { name: 'Equipe', href: '/configuracoes/membros', icon: Users, keywords: 'membros convites pessoas time' },
  { name: 'Configurações', href: '/configuracoes', icon: Settings, keywords: 'ajustes organizacao integracoes' },
];

/**
 * Paleta de comandos (Ctrl/⌘+K): atalho para quem já conhece o sistema —
 * pula direto para qualquer página ou ação sem passar pelo menu.
 */
export function CommandMenu() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const { data: membership } = useOrgMembership();

  const canViewAnalytics =
    membership?.membership?.role === 'OWNER' ||
    membership?.membership?.role === 'ADMIN' ||
    membership?.membership?.sales_role === 'ANALYST' ||
    membership?.membership?.sales_role === 'MANAGER';

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    const openMenu = () => setOpen(true);
    document.addEventListener('keydown', down);
    window.addEventListener('open-command-menu', openMenu);
    return () => {
      document.removeEventListener('keydown', down);
      window.removeEventListener('open-command-menu', openMenu);
    };
  }, []);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  const visiblePages = pages.filter((p) => !p.analystOnly || canViewAnalytics);

  return (
    <CommandDialog
      open={open}
      onOpenChange={setOpen}
      title="Ir para"
      description="Digite o destino ou a ação desejada"
    >
      <CommandInput placeholder="Para onde vamos? Digite um destino…" />
      <CommandList>
        <CommandEmpty>Nada encontrado. Tente outro termo.</CommandEmpty>
        <CommandGroup heading="Páginas">
          {visiblePages.map((page) => (
            <CommandItem
              key={page.href}
              value={`${page.name} ${page.keywords}`}
              onSelect={() => go(page.href)}
            >
              <page.icon className="text-muted-foreground" />
              {page.name}
              <CommandShortcut>{page.href}</CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Ações rápidas">
          <CommandItem value="nova campanha criar busca" onSelect={() => go('/campanhas/nova')}>
            <Plus className="text-muted-foreground" />
            Criar uma nova busca de prospecção
            <CornerDownLeft className="ml-auto size-3 text-muted-foreground" />
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}