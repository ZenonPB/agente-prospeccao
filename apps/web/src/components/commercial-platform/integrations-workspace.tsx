'use client';

import { FormEvent, useState } from 'react';
import { CheckCircle2, FlaskConical, Loader2, PlugZap, RefreshCw, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  useCertifyCRMConnection,
  useCRMConnections,
  useCRMCertifications,
  useCRMHealth,
  useCRMSyncRuns,
  usePullCRMChanges,
  useSaveCRMConnection,
} from '@/hooks/use-commercial-platform';
import type { CRMProvider, CRMSyncMode } from '@/lib/commercial-platform-api';

const PROVIDER_LABELS: Record<CRMProvider, string> = {
  pipedrive: 'Pipedrive',
  hubspot: 'HubSpot',
  salesforce: 'Salesforce',
};
const MODE_LABELS: Record<CRMSyncMode, string> = {
  manual: 'Somente quando solicitado',
  realtime: 'Atualização contínua',
  scheduled: 'Atualização periódica',
};

function message(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function formatDate(value?: string | null) {
  if (!value) return 'Ainda não executado';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Data indisponível' : date.toLocaleString('pt-BR');
}

export function IntegrationsWorkspace() {
  const connections = useCRMConnections();
  const runs = useCRMSyncRuns();
  const certifications = useCRMCertifications();
  const save = useSaveCRMConnection();
  const health = useCRMHealth();
  const certify = useCertifyCRMConnection();
  const pull = usePullCRMChanges();
  const [provider, setProvider] = useState<CRMProvider>('pipedrive');
  const [mode, setMode] = useState<CRMSyncMode>('manual');
  const [token, setToken] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [enabled, setEnabled] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await save.mutateAsync({
        provider,
        sync_mode: mode,
        token: token.trim() || undefined,
        base_url: baseUrl.trim() || undefined,
        enabled,
      });
      setToken('');
      toast.success('Integração salva com segurança.');
    } catch (error) {
      toast.error(message(error, 'Não foi possível salvar a integração.'));
    }
  }

  if (connections.isLoading) {
    return <div className="flex min-h-48 items-center justify-center text-muted-foreground" role="status"><Loader2 className="mr-2 size-5 animate-spin" aria-hidden="true" />Carregando integrações...</div>;
  }
  if (connections.isError) {
    return <EmptyState title="Não foi possível carregar as integrações" description="Tente novamente em alguns instantes." />;
  }

  return (
    <div className="space-y-6">
      <Card className="border-dashed">
        <CardContent className="flex gap-3 p-5">
          <ShieldCheck className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
          <div>
            <p className="font-medium">Credenciais protegidas e validação sem escrita</p>
            <p className="mt-1 text-sm text-muted-foreground">A chave informada é criptografada e nunca volta para a tela. A certificação usa somente autenticação e leitura para validar uma conta real sem criar ou alterar registros no CRM.</p>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Conectar sistema comercial</CardTitle>
            <CardDescription>Centralize empresas, contatos e oportunidades sem copiar dados manualmente entre ferramentas.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={submit}>
              <div className="space-y-2">
                <Label>Sistema</Label>
                <Select value={provider} onValueChange={(value) => { if (value) setProvider(value as CRMProvider); }}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>{Object.entries(PROVIDER_LABELS).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Forma de atualização</Label>
                <Select value={mode} onValueChange={(value) => { if (value) setMode(value as CRMSyncMode); }}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>{Object.entries(MODE_LABELS).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="crm-token">Chave de acesso</Label>
                <Input id="crm-token" type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Informe apenas para cadastrar ou substituir" />
                <p className="text-xs text-muted-foreground">Deixe vazio para manter a chave que já está cadastrada.</p>
              </div>
              {provider === 'salesforce' ? (
                <div className="space-y-2">
                  <Label htmlFor="crm-url">Endereço da sua instância Salesforce</Label>
                  <Input id="crm-url" type="url" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://suaempresa.my.salesforce.com" required />
                </div>
              ) : null}
              <label className="flex cursor-pointer items-start gap-3 rounded-lg border p-3">
                <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} className="mt-1 size-4" />
                <span><span className="block font-medium">Ativar integração</span><span className="block text-sm text-muted-foreground">Nenhuma troca de dados ocorre enquanto estiver desativada.</span></span>
              </label>
              <Button type="submit" disabled={save.isPending}>{save.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <PlugZap className="size-4" aria-hidden="true" />}Salvar integração</Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Integrações configuradas</CardTitle><CardDescription>Valide a conta real antes de sincronizar dados e mantenha a evidência da certificação.</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {(connections.data?.items.length ?? 0) === 0 ? <EmptyState title="Nenhuma integração configurada" description="Conecte o sistema comercial usado pela equipe quando quiser sincronizar os dados." /> : connections.data?.items.map((connection) => {
              const latestCertification = certifications.data?.items.find((item) => item.connection_id === connection.id);
              return (
                <article key={connection.id} className="rounded-xl border p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div><h3 className="font-medium">{PROVIDER_LABELS[connection.provider]}</h3><p className="mt-1 text-sm text-muted-foreground">{MODE_LABELS[connection.sync_mode]} · última atualização: {formatDate(connection.last_sync_at)}</p></div>
                    <Badge variant={connection.enabled ? 'outline' : 'secondary'}>{connection.enabled ? 'Ativa' : 'Desativada'}</Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                    {connection.last_health_status === 'ok' ? <span className="flex items-center gap-1"><CheckCircle2 className="size-4 text-primary" aria-hidden="true" />Conexão verificada</span> : <span>Conexão ainda não verificada</span>}
                    {latestCertification ? <span className="flex items-center gap-1"><FlaskConical className="size-4" aria-hidden="true" />Certificação real: {latestCertification.status === 'PASSED' ? 'aprovada' : 'falhou'} · {formatDate(latestCertification.created_at)}</span> : <span>Conta real ainda não certificada</span>}
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" disabled={!connection.enabled || health.isPending} onClick={() => void health.mutateAsync(connection.id).then(() => toast.success('Conexão verificada.')).catch((error) => toast.error(message(error, 'Não foi possível verificar a conexão.')))}>Verificar conexão</Button>
                    <Button size="sm" variant="outline" disabled={!connection.enabled || certify.isPending} onClick={() => void certify.mutateAsync(connection.id).then((result) => result.status === 'PASSED' ? toast.success('Conta real certificada em modo somente leitura.') : toast.error('A certificação encontrou uma falha. Consulte o histórico.')).catch((error) => toast.error(message(error, 'Não foi possível certificar a conta.')))}><FlaskConical className="size-4" aria-hidden="true" />Certificar conta real</Button>
                    <Button size="sm" variant="outline" disabled={!connection.enabled || pull.isPending} onClick={() => void pull.mutateAsync(connection.id).then((result) => toast.success(`${result.processed} alteração(ões) revisadas.`)).catch((error) => toast.error(message(error, 'Não foi possível buscar alterações.')))}><RefreshCw className="size-4" aria-hidden="true" />Buscar alterações</Button>
                  </div>
                </article>
              );
            })}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Evidências de certificação</CardTitle><CardDescription>Cada execução comprova autenticação e leitura contra a conta configurada sem criar ou alterar registros no provedor.</CardDescription></CardHeader>
        <CardContent>
          {(certifications.data?.items.length ?? 0) === 0 ? <EmptyState title="Nenhuma conta real certificada" description="Depois de configurar uma credencial válida, use “Certificar conta real”. A ausência de certificação não é tratada como aprovação." /> : <div className="space-y-2">{certifications.data?.items.slice(0, 12).map((run) => <div key={run.id} className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="font-medium">{PROVIDER_LABELS[run.provider]}</p><p className="text-sm text-muted-foreground">{formatDate(run.created_at)} · adapter {run.adapter_version} · {run.checks.length} verificação(ões)</p></div><Badge variant={run.status === 'PASSED' ? 'secondary' : 'destructive'}>{run.status === 'PASSED' ? 'Certificada' : 'Falhou'}</Badge></div>)}</div>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Histórico de sincronização</CardTitle><CardDescription>Execuções ficam registradas para identificar falhas ou dados que exigem revisão.</CardDescription></CardHeader>
        <CardContent>
          {(runs.data?.items.length ?? 0) === 0 ? <EmptyState title="Nenhuma sincronização registrada" description="O histórico aparecerá depois da primeira atualização." /> : <div className="space-y-2">{runs.data?.items.slice(0, 12).map((run) => <div key={run.id} className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="font-medium">{run.direction === 'inbound' ? 'Dados recebidos' : 'Dados enviados'}</p><p className="text-sm text-muted-foreground">{formatDate(run.started_at)} · {run.succeeded} concluído(s) · {run.conflicts} para revisão</p></div><Badge variant={run.status === 'COMPLETED' ? 'secondary' : run.status === 'FAILED' ? 'destructive' : 'outline'}>{run.status === 'COMPLETED' ? 'Concluída' : run.status === 'FAILED' ? 'Falhou' : 'Parcial'}</Badge></div>)}</div>}
        </CardContent>
      </Card>
    </div>
  );
}
