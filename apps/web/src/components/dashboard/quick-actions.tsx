'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowRight, Users, Target, Phone } from 'lucide-react';
import Link from 'next/link';
import { useLeadStats, useCampaigns } from '@/hooks/use-api';

export function QuickActions() {
  const { data: stats } = useLeadStats();
  const { data: campaignsData } = useCampaigns();

  const qualifiedCount = stats?.qualified_count || 0;
  const pendingFollowUp = (stats?.by_status?.CONTATADO || 0) + (stats?.by_status?.RESPONDIDO || 0);
  const activeCampaigns = campaignsData?.campaigns?.filter(c => c.status === 'ACTIVE').length || 0;

  const actions = [
    {
      id: 'qualified',
      title: 'Prosseguir com contatos',
      description: qualifiedCount > 0
        ? `${qualifiedCount} lead${qualifiedCount !== 1 ? 's' : ''} aguardando mensagem`
        : 'Nenhum lead apto no momento',
      icon: <Target className="h-4 w-4" />,
      href: '/oportunidades',
      count: qualifiedCount,
      color: 'bg-emerald-500',
    },
    {
      id: 'followup',
      title: 'Fazer follow-up',
      description: pendingFollowUp > 0
        ? `${pendingFollowUp} lead${pendingFollowUp !== 1 ? 's' : ''} em acompanhamento`
        : 'Nenhum contato em andamento',
      icon: <Phone className="h-4 w-4" />,
      href: '/vendas',
      count: pendingFollowUp,
      color: 'bg-amber-500',
    },
    {
      id: 'campaigns',
      title: 'Expandir busca',
      description: activeCampaigns > 0
        ? `${activeCampaigns} campanha${activeCampaigns !== 1 ? 's' : ''} ativa${activeCampaigns !== 1 ? 's' : ''}`
        : 'Nenhuma campanha ativa',
      icon: <Users className="h-4 w-4" />,
      href: '/campanhas',
      count: activeCampaigns,
      color: 'bg-blue-500',
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>O que fazer agora</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {actions.map((action) => (
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
