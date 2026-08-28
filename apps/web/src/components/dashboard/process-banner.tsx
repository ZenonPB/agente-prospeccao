'use client';

import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Target, Sparkles, MessageSquare, CalendarCheck, ArrowRight } from 'lucide-react';

const steps = [
  {
    step: '01',
    title: 'Crie sua busca',
    desc: 'Escolha cidade e segmento',
    href: '/campanhas/nova',
    icon: Target,
    badge: 'Você',
  },
  {
    step: '02',
    title: 'A IA avalia',
    desc: 'Cada empresa recebe uma nota e um motivo',
    href: '/oportunidades',
    icon: Sparkles,
    badge: 'Automático',
  },
  {
    step: '03',
    title: 'Faça o contato',
    desc: 'Mensagens prontas para e-mail e WhatsApp',
    href: '/oportunidades',
    icon: MessageSquare,
    badge: '1 clique',
  },
  {
    step: '04',
    title: 'Marque a reunião',
    desc: 'Acompanhe cada negociação no quadro do time',
    href: '/vendas',
    icon: CalendarCheck,
    badge: 'Conversão',
  },
];

export function ProcessBanner() {
  return (
    <Card className="relative overflow-hidden border-sidebar-border bg-gradient-to-r from-sidebar/95 via-sidebar to-sidebar/90 text-sidebar-foreground shadow-[var(--shadow-soft)]">
      {/* Auroras ambientes */}
      <div className="aurora-blob -right-20 -top-24 h-64 w-64 bg-sidebar-primary/20" />
      <div className="aurora-blob -bottom-24 -left-20 h-64 w-64 bg-accent/15 [animation-delay:-6s]" />

      <CardContent className="relative z-10 p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1.5 rounded-full bg-sidebar-primary/20 px-2.5 py-0.5 text-xs font-semibold text-sidebar-primary">
                <span className="radar-dot inline-block h-1.5 w-1.5 rounded-full bg-sidebar-primary" />
                Guia Comercial EJ
              </span>
              <span className="text-xs text-sidebar-foreground/60">
                Do primeiro clique à reunião marcada
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
          {steps.map((item, i) => (
            <Link key={item.step} href={item.href} className="group block animate-fade-up" style={{ animationDelay: `${120 + i * 80}ms` }}>
              <div className="flex h-full flex-col justify-between rounded-lg border border-sidebar-border bg-sidebar-accent/40 p-3.5 transition-all duration-300 group-hover:-translate-y-0.5 group-hover:border-sidebar-primary/50 group-hover:bg-sidebar-accent group-hover:shadow-lg">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-sidebar-accent text-sidebar-primary transition-colors duration-300 group-hover:bg-sidebar-primary group-hover:text-sidebar-primary-foreground">
                    <item.icon className="h-4 w-4 transition-transform duration-300 group-hover:scale-110" aria-hidden="true" />
                  </div>
                  <span className="font-mono text-xs font-bold text-sidebar-foreground/40">
                    {item.step}
                  </span>
                </div>
                <div className="mt-3">
                  <p className="text-sm font-semibold text-sidebar-foreground transition-colors group-hover:text-sidebar-primary">
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
