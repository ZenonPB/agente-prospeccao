'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowRight, Users, Target, Phone } from 'lucide-react';
import Link from 'next/link';

interface QuickAction {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  href: string;
  count?: number;
  color: string;
}

const quickActions: QuickAction[] = [
  {
    id: '1',
    title: 'Prosseguir com contatos',
    description: '12 leads aguardando sua mensagem',
    icon: <Target className="h-4 w-4" />,
    href: '/oportunidades',
    count: 12,
    color: 'bg-emerald-500',
  },
  {
    id: '2',
    title: 'Fazer follow-up',
    description: '3 leads sem resposta há 7+ dias',
    icon: <Phone className="h-4 w-4" />,
    href: '/vendas',
    count: 3,
    color: 'bg-amber-500',
  },
  {
    id: '3',
    title: 'Expandir busca',
    description: '1 campanha sem novos resultados',
    icon: <Users className="h-4 w-4" />,
    href: '/campanhas',
    count: 1,
    color: 'bg-blue-500',
  },
];

export function QuickActions() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>O que fazer agora</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {quickActions.map((action) => (
            <Link key={action.id} href={action.href}>
              <div className="group flex items-center justify-between rounded-lg border p-4 transition-all hover:border-primary hover:bg-muted/50">
                <div className="flex items-center gap-4">
                  <div className={`flex h-10 w-10 items-center justify-center rounded-full text-white ${action.color}`}>
                    {action.icon}
                  </div>
                  <div>
                    <p className="font-medium group-hover:text-primary">{action.title}</p>
                    <p className="text-sm text-muted-foreground">{action.description}</p>
                  </div>
                </div>
                <ArrowRight className="h-5 w-5 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-primary" />
              </div>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}