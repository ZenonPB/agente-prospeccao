import { PipelineMonitor } from '@/components/pipeline/pipeline-monitor';

export default function PipelinePage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Pipeline</h2>
        <p className="text-muted-foreground">
          Acompanhe o processamento dos leads em tempo real
        </p>
      </div>

      <PipelineMonitor />
    </div>
  );
}