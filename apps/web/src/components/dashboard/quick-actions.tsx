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
}

const quickActions: QuickAction[] = [
  {
    id: '1',
    title: 'Leads qualificados aguardando contato',
    description: 'Iniciar prospecção ativa',
    icon: <Target className="h-4 w-4" />,
    href: '/oportunidades',
    count: 12,
  },
  {
    id: '2',
    title: 'Follow-ups pendentes',
    description: 'Leads sem resposta há 7+ dias',
    icon: <Phone className="h-4 w-4" />,
    href: '/pipeline',
    count: 3,
  },
  {
    id: '3',
    title: 'Campanha sem novos leads',
    description: 'Considerar expandir região',
    icon: <Users className="h-4 w-4" />,
    href: '/campanhas',
    count: 1,
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
              <div className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-muted">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
                    {action.icon}
                  </div>
                  <div>
                    <p className="text-sm font-medium">
                      {action.title}
                      {action.count && (
                        <span className="ml-2 text-xs text-muted-foreground">
                          ({action.count})
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-muted-foreground">{action.description}</p>
                  </div>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
              </div>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}