'use client';

import { useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import {
  CheckCircle2,
  CircleAlert,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  RefreshCw,
  Save,
  ShieldCheck,
  Share2,
  Trash2,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  useDeleteOrgSecret,
  useOrgMembership,
  useOrgSecrets,
  usePutOrgSecret,
} from '@/hooks/use-api';
import {
  providerDiagnosticsApi,
  type ProviderDiagnosticItem,
  type ProviderDiagnosticsResponse,
} from '@/lib/provider-diagnostics-api';

const KEYS = [
  {
    key_name: 'GOOGLE_API_KEY',
    provider: 'google',
    label: 'Busca de empresas',
    description: 'Encontra empresas, endereços, avaliações e sites pelo Google.',
    placeholder: 'Cole a chave do Google…',
  },
  {
    key_name: 'GROQ_API_KEY',
    provider: 'groq',
    label: 'Inteligência artificial',
    description: 'Analisa leads, ajuda a criar campanhas e gera sugestões comerciais.',
    placeholder: 'Cole a chave da IA…',
  },
  {
    key_name: 'HUNTER_API_KEY',
    provider: 'hunter',
    label: 'Busca de decisores',
    description: 'Procura contatos e e-mails profissionais quando necessário.',
    placeholder: 'Cole a chave de contatos…',
  },
] as const;

type KeyName = (typeof KEYS)[number]['key_name'];

const STATUS_COPY: Record<ProviderDiagnosticItem['status'], { label: string; detail: string; ok: boolean }> = {
  ok: { label: 'Funcionando', detail: 'A conexão respondeu corretamente.', ok: true },
  invalid_key: { label: 'Chave recusada', detail: 'Revise a chave ou as permissões no serviço.', ok: false },
  quota_limited: { label: 'Limite atingido', detail: 'A chave existe, mas o serviço recusou por limite de uso.', ok: false },
  unavailable: { label: 'Serviço indisponível', detail: 'O serviço externo está com erro temporário.', ok: false },
  rejected: { label: 'Configuração recusada', detail: 'O serviço respondeu, mas não aceitou esta configuração.', ok: false },
  timeout: { label: 'Demorou demais', detail: 'A conexão não respondeu dentro do tempo esperado.', ok: false },
  unreachable: { label: 'Sem conexão', detail: 'Não foi possível chegar ao serviço externo.', ok: false },
  not_configured: { label: 'Não configurado', detail: 'Nenhuma chave disponível para este serviço.', ok: false },
};

export function OrgSecretsCard() {
  const { data: membership } = useOrgMembership();
  const orgId = membership?.organization?.id;
  const myRole = membership?.membership?.role;
  const canManage = myRole === 'OWNER' || myRole === 'ADMIN';

  const { data: secretsData, isLoading, refetch } = useOrgSecrets(orgId);
  const putSecret = usePutOrgSecret();
  const deleteSecret = useDeleteOrgSecret();

  const [values, setValues] = useState<Partial<Record<KeyName, string>>>({});
  const [show, setShow] = useState<Partial<Record<KeyName, boolean>>>({});
  const [pendingKey, setPendingKey] = useState<KeyName | null>(null);
  const [testing, setTesting] = useState(false);
  const [diagnostics, setDiagnostics] = useState<ProviderDiagnosticsResponse | null>(null);

  const configuredMap: Partial<Record<KeyName, boolean>> = {};
  for (const secret of secretsData?.secrets || []) {
    configuredMap[secret.key_name as KeyName] = secret.configured;
  }

  const diagnosticByProvider = Object.fromEntries(
    (diagnostics?.providers ?? []).map((item) => [item.provider, item]),
  ) as Partial<Record<(typeof KEYS)[number]['provider'], ProviderDiagnosticItem>>;

  const handleSave = async (keyName: KeyName) => {
    if (!orgId) return;
    const value = values[keyName]?.trim();
    if (!value) return toast.error('Cole a chave antes de salvar.');
    setPendingKey(keyName);
    try {
      await putSecret.mutateAsync({ orgId, keyName, value });
      setValues((previous) => ({ ...previous, [keyName]: '' }));
      setDiagnostics(null);
      toast.success(`${labelFor(keyName)} atualizada.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível salvar a chave.');
    } finally {
      setPendingKey(null);
    }
  };

  const handleRemove = async (keyName: KeyName) => {
    if (!orgId) return;
    setPendingKey(keyName);
    try {
      await deleteSecret.mutateAsync({ orgId, keyName });
      setDiagnostics(null);
      toast.success(`${labelFor(keyName)} removida.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível remover a chave.');
    } finally {
      setPendingKey(null);
    }
  };

  const testConnections = async () => {
    if (!orgId) return;
    setTesting(true);
    try {
      const result = await providerDiagnosticsApi.test(orgId);
      setDiagnostics(result);
      if (result.ready_for_basic_prospecting) {
        toast.success('Busca de empresas e inteligência artificial estão prontas para uso.');
      } else {
        toast.warning('Há uma conexão essencial que precisa de atenção.');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Não foi possível testar as conexões.');
    } finally {
      setTesting(false);
    }
  };

  if (!canManage) {
    return (
      <Card data-tour="configuracoes-chaves">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><KeyRound className="h-5 w-5" />Conexões de busca e IA</CardTitle>
          <CardDescription>Seu administrador cuida destas conexões. Você não precisa configurar nada para começar a usar.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
            <ShieldCheck className="h-4 w-4 shrink-0" />Configurações protegidas para administradores.
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-tour="configuracoes-chaves">
      <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1.5">
          <CardTitle className="flex items-center gap-2"><KeyRound className="h-5 w-5" />Conexões de busca e IA</CardTitle>
          <CardDescription>
            Configure apenas o que sua equipe usa. As chaves ficam protegidas e nunca voltam a aparecer na tela depois de salvas.
          </CardDescription>
        </div>
        <Button variant="outline" onClick={() => void testConnections()} disabled={testing || isLoading} className="shrink-0">
          {testing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
          {testing ? 'Testando…' : 'Testar conexões'}
        </Button>
      </CardHeader>
      <CardContent className="space-y-6">
        {diagnostics ? (
          <div className={`rounded-xl border p-4 ${diagnostics.ready_for_basic_prospecting ? 'bg-emerald-500/5' : 'bg-amber-500/5'}`} role="status">
            <div className="flex items-start gap-2">
              {diagnostics.ready_for_basic_prospecting ? <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-600" /> : <CircleAlert className="mt-0.5 h-5 w-5 text-amber-600" />}
              <div>
                <p className="font-medium">{diagnostics.ready_for_basic_prospecting ? 'Pronto para prospectar' : 'Revise as conexões essenciais'}</p>
                <p className="mt-1 text-sm text-muted-foreground">O Google e a inteligência artificial precisam estar funcionando. A busca de decisores é complementar.</p>
              </div>
            </div>
          </div>
        ) : null}

        {isLoading ? (
          <div className="space-y-3">{[1, 2, 3].map((item) => <div key={item} className="h-20 animate-pulse rounded-xl bg-muted" />)}</div>
        ) : (
          KEYS.map((key) => {
            const isConfigured = !!configuredMap[key.key_name];
            const isPending = pendingKey === key.key_name;
            const currentValue = values[key.key_name] || '';
            const diagnostic = diagnosticByProvider[key.provider];
            const statusCopy = diagnostic ? STATUS_COPY[diagnostic.status] : null;
            return (
              <div key={key.key_name} className="rounded-xl border p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <Label className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                      {key.label}
                      {isConfigured ? <Badge variant="secondary">Chave da equipe</Badge> : <Badge variant="outline"><Share2 className="mr-1 h-3 w-3" />Configuração compartilhada</Badge>}
                      {statusCopy ? <Badge variant={statusCopy.ok ? 'secondary' : 'outline'}>{statusCopy.label}</Badge> : null}
                    </Label>
                    <p className="mt-1 text-xs text-muted-foreground">{key.description}</p>
                    {statusCopy ? <p className="mt-1 text-xs text-muted-foreground">{statusCopy.detail}</p> : null}
                  </div>
                </div>

                <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
                  <div className="relative flex-1">
                    <Input
                      type={show[key.key_name] ? 'text' : 'password'}
                      value={currentValue}
                      onChange={(event) => setValues((previous) => ({ ...previous, [key.key_name]: event.target.value }))}
                      placeholder={isConfigured ? 'Cole uma nova chave somente para substituir a atual' : key.placeholder}
                      autoComplete="new-password"
                      disabled={isPending}
                      aria-label={`Nova chave para ${key.label}`}
                    />
                    {currentValue ? (
                      <button
                        type="button"
                        onClick={() => setShow((previous) => ({ ...previous, [key.key_name]: !previous[key.key_name] }))}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        aria-label={show[key.key_name] ? 'Ocultar chave digitada' : 'Mostrar chave digitada'}
                      >
                        {show[key.key_name] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    ) : null}
                  </div>
                  <Button size="sm" onClick={() => void handleSave(key.key_name)} disabled={isPending || !currentValue.trim()}>
                    {isPending ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Save className="mr-1.5 h-4 w-4" />}
                    {isConfigured ? 'Substituir' : 'Salvar'}
                  </Button>
                  {isConfigured ? (
                    <AlertDialog>
                      <AlertDialogTrigger render={<Button variant="outline" size="sm" disabled={isPending}><Trash2 className="mr-1.5 h-4 w-4" />Remover</Button>} />
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Remover a conexão própria de {key.label}?</AlertDialogTitle>
                          <AlertDialogDescription>A organização voltará a usar a configuração compartilhada, quando ela existir.</AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancelar</AlertDialogCancel>
                          <AlertDialogAction onClick={() => void handleRemove(key.key_name)} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">Remover</AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  ) : null}
                </div>
              </div>
            );
          })
        )}

        <button type="button" onClick={() => void refetch()} className="text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline">
          Atualizar informações desta seção
        </button>
      </CardContent>
    </Card>
  );
}

function labelFor(keyName: KeyName): string {
  return KEYS.find((key) => key.key_name === keyName)?.label ?? keyName;
}
