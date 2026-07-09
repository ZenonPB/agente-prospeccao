import { LeadList } from '@/components/oportunidades/lead-list';

export default function OportunidadesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Oportunidades</h2>
        <p className="text-muted-foreground">
          Leads qualificados prontos para prospecção
        </p>
      </div>

      <LeadList />
    </div>
  );
}