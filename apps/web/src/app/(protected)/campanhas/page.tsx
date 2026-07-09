import { CampaignList } from '@/components/campanhas/campaign-list';

export default function CampanhasPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Campanhas</h2>
        <p className="text-muted-foreground">
          Gerencie suas campanhas de prospecção
        </p>
      </div>

      <CampaignList />
    </div>
  );
}