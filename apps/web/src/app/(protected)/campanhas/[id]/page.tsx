'use client';

import { useParams, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useCampaign, useLeads } from '@/hooks/use-api';
import { CampaignPipeline } from '@/components/campanhas/campaign-pipeline';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowLeft, MapPin } from 'lucide-react';

const statusConfig: Record<string, { label: string; color: string }> = {
  ACTIVE: { label: 'Em andamento', color: 'bg-emerald-100 text-emerald-700' },
  PAUSED: { label: 'Pausada', color: 'bg-amber-100 text-amber-700' },
  COMPLETED: { label: 'Concluída', color: 'bg-blue-100 text-blue-700' },
  ARCHIVED: { label: 'Arquivada', color: 'bg-gray-100 text-gray-700' },
};

export default function CampaignDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const campaignId = params.id as string;
  const autoStart = searchParams.get('start') === 'true';

  const { data: campaign, isLoading } = useCampaign(campaignId);
  const { data: leadsData } = useLeads({ campaign_id: campaignId });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Carregando campanha...</p>
      </div>
    );
  }

  if (!campaign) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Campanha não encontrada</p>
        <Link href="/campanhas">
          <Button variant="link">Voltar para campanhas</Button>
        </Link>
      </div>
    );
  }

  const leads = leadsData?.leads || [];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Link href="/campanhas">
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <div>
              <h2 className="text-2xl font-bold tracking-tight">{campaign.name}</h2>
              <p className="text-sm text-muted-foreground flex items-center gap-1">
                {campaign.target_service && <span>{campaign.target_service}</span>}
                {campaign.target_segment && <><span>•</span><span>{campaign.target_segment}</span></>}
                {campaign.target_city && (
                  <><span>•</span><MapPin className="h-3 w-3" /><span>{campaign.target_city}{campaign.target_state ? `, ${campaign.target_state}` : ''}</span></>
                )}
              </p>
            </div>
          </div>
        </div>
        <Badge className={statusConfig[campaign.status]?.color}>
          {statusConfig[campaign.status]?.label || campaign.status}
        </Badge>
      </div>

      <CampaignPipeline
        campaignId={campaign.id}
        campaignName={campaign.name}
        autoStart={autoStart}
      />

      <Card>
        <CardHeader>
          <CardTitle>Leads da Campanha ({leads.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {leads.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              Nenhum lead encontrado ainda. Inicie a coleta para começar.
            </p>
          ) : (
            <div className="divide-y">
              {leads.map((lead) => (
                <div key={lead.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="font-medium">{lead.company_name}</p>
                    <p className="text-sm text-muted-foreground">
                      {lead.city}{lead.state ? `, ${lead.state}` : ''}
                      {lead.website && <span> • {lead.website}</span>}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {lead.qualification_score != null && (
                      <Badge className={lead.qualification_score >= 60 ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}>
                        {lead.qualification_score}
                      </Badge>
                    )}
                    <Link href={`/oportunidades/${lead.id}`}>
                      <Button variant="ghost" size="sm">Detalhes</Button>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
