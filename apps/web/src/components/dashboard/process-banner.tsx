'use client';

import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Target, Sparkles, MessageSquare, CalendarCheck, ArrowRight } from 'lucide-react';

const steps = [
  {
    step: '01',
    title: 'Criar Busca',
    desc: 'Escolha cidade e segmento',
    href: '/campanhas/nova',
    icon: Target,
    badge: 'Início',
  },
  {
    step: '02',
    title: 'Qualificação IA',
    desc: 'IA descobre dores e nota 0-100',
    href: '/oportunidades',
    icon: Sparkles,
    badge: 'Automático',
  },
  {
    step: '03',
    title: 'Abordar Leads',
    desc: 'E-mails e WhatsApp com 1 clique',
    href: '/oportunidades',
    icon: MessageSquare,
    badge: 'Outreach',
  },
  {
    step: '04',
    title: 'Fechar Reunião',
    desc: 'Kanban comercial da equipe',
    href: '/vendas',
    icon: CalendarCheck,
    badge: 'Conversão',
  },
];

export function ProcessBanner() {
  return (
    <Card className="relative overflow-hidden border-sidebar-border bg-gradient-to-r from-sidebar/95 via-sidebar to-sidebar/90 text-sidebar-foreground shadow-sm">
      {/* Background ambient lighting */}
      <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-sidebar-primary/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-20 -left-20 h-64 w-64 rounded-full bg-accent/15 blur-3xl" />

      <CardContent className="relative z-10 p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-sidebar-primary/20 px-2.5 py-0.5 text-xs font-semibold text-sidebar-primary">
                Guia Comercial EJ
              </span>
              <span className="text-xs text-sidebar-foreground/60">
                Fluxo de prospecção inteligente
              </span>
            </div>
            <h3 className="font-heading text-lg font-semibold tracking-tight text-sidebar-foreground sm:text-xl">
              Como transformar buscas em reuniões marcadas
            </h3>
          </div>
          <Link href="/campanhas/nova">
            <Button size="sm" className="bg-sidebar-primary text-sidebar-primary-foreground hover:bg-sidebar-primary/90">
              Nova Busca Rápida
              <ArrowRight className="ml-1.5 h-4 w-4" />
            </Button>
          </Link>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((item) => (
            <Link key={item.step} href={item.href} className="group block">
              <div className="flex h-full flex-col justify-between rounded-lg border border-sidebar-border bg-sidebar-accent/40 p-3.5 transition-all group-hover:border-sidebar-primary/50 group-hover:bg-sidebar-accent">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-sidebar-accent text-sidebar-primary group-hover:bg-sidebar-primary group-hover:text-sidebar-primary-foreground transition-colors">
                    <item.icon className="h-4 w-4" aria-hidden="true" />
                  </div>
                  <span className="font-mono text-xs font-bold text-sidebar-foreground/40">
                    {item.step}
                  </span>
                </div>
                <div className="mt-3">
                  <p className="text-sm font-semibold text-sidebar-foreground group-hover:text-sidebar-primary transition-colors">
                    {item.title}
                  </p>
                  <p className="mt-0.5 text-xs text-sidebar-foreground/60">
                    {item.desc}
                  </p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
