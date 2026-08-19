"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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
} from "@/components/ui/alert-dialog";
import { KeyRound, Eye, EyeOff, Loader2, Save, Trash2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import {
  useOrgMembership,
  useOrgSecrets,
  usePutOrgSecret,
  useDeleteOrgSecret,
} from "@/hooks/use-api";

const KEYS = [
  {
    key_name: "GOOGLE_API_KEY",
    label: "Google Places (Busca de Empresas)",
    description: "Usada na busca de empresas pelo mapa e verificação de informações.",
    placeholder: "AIza…",
  },
  {
    key_name: "GROQ_API_KEY",
    label: "Inteligência Artificial (Groq)",
    description: "Usada para qualificar os clientes, criar mensagens e gerar sugestões.",
    placeholder: "gsk_…",
  },
] as const;

type KeyName = (typeof KEYS)[number]["key_name"];

export function OrgSecretsCard() {
  const { data: membership } = useOrgMembership();
  const orgId = membership?.organization?.id;
  const myRole = membership?.membership?.role;
  const canManage = myRole === "OWNER" || myRole === "ADMIN";

  const { data: secretsData, isLoading, refetch } = useOrgSecrets(orgId);
  const putSecret = usePutOrgSecret();
  const deleteSecret = useDeleteOrgSecret();

  const [values, setValues] = useState<Partial<Record<KeyName, string>>>({});
  const [show, setShow] = useState<Partial<Record<KeyName, boolean>>>({});
  const [pendingKey, setPendingKey] = useState<KeyName | null>(null);

  const configuredMap: Partial<Record<KeyName, boolean>> = {};
  for (const s of secretsData?.secrets || []) {
    configuredMap[s.key_name as KeyName] = s.configured;
  }

  const handleSave = async (keyName: KeyName) => {
    if (!orgId) return;
    const value = values[keyName]?.trim();
    if (!value) {
      toast.error("Informe o valor da chave antes de salvar.");
      return;
    }
    setPendingKey(keyName);
    try {
      await putSecret.mutateAsync({ orgId, keyName, value });
      toast.success(`${labelFor(keyName)} salva com sucesso.`);
      setValues((prev) => ({ ...prev, [keyName]: "" }));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao salvar a chave.");
    } finally {
      setPendingKey(null);
    }
  };

  const handleRemove = async (keyName: KeyName) => {
    if (!orgId) return;
    setPendingKey(keyName);
    try {
      await deleteSecret.mutateAsync({ orgId, keyName });
      toast.success(`${labelFor(keyName)} removida — voltou a usar o pool global.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao remover a chave.");
    } finally {
      setPendingKey(null);
    }
  };

  if (!canManage) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="h-5 w-5 text-muted-foreground" />
            Chaves de Inteligência e Buscas (API)
          </CardTitle>
          <CardDescription>
            Apenas o administrador da conta pode cadastrar chaves próprias de acesso.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
            <ShieldCheck className="h-4 w-4 shrink-0" />
            Fale com um administrador para configurar as chaves da sua organização.
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="h-5 w-5 text-muted-foreground" />
          Chaves de Inteligência e Buscas (API)
        </CardTitle>
        <CardDescription>
          Insira suas próprias chaves de acesso caso prefira utilizar seus limites diretos do Google e da Inteligência Artificial.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {isLoading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="space-y-2">
                <div className="h-4 w-40 animate-pulse rounded bg-muted" />
                <div className="h-9 w-full animate-pulse rounded bg-muted" />
              </div>
            ))}
          </div>
        ) : (
          KEYS.map((key) => {
            const isConfigured = !!configuredMap[key.key_name];
            const isPending = pendingKey === key.key_name;
            const currentValue = values[key.key_name] || "";
            return (
              <div key={key.key_name} className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <Label className="flex items-center gap-2 text-sm font-medium">
                      {key.label}
                      {isConfigured ? (
                        <Badge variant="secondary" className="gap-1">
                          <ShieldCheck className="h-3 w-3" />
                          Configurada
                        </Badge>
                      ) : (
                        <Badge variant="outline">Pool global</Badge>
                      )}
                    </Label>
                    <p className="mt-0.5 text-xs text-muted-foreground">{key.description}</p>
                  </div>
                </div>

                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <div className="relative flex-1">
                    <Input
                      type={show[key.key_name] ? "text" : "password"}
                      value={currentValue}
                      onChange={(e) =>
                        setValues((prev) => ({ ...prev, [key.key_name]: e.target.value }))
                      }
                      placeholder={key.placeholder}
                      autoComplete="off"
                      disabled={isPending}
                      aria-label={`Valor da chave ${key.label}`}
                    />
                    {currentValue && (
                      <button
                        type="button"
                        onClick={() =>
                          setShow((prev) => ({ ...prev, [key.key_name]: !prev[key.key_name] }))
                        }
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:text-foreground"
                        aria-label={show[key.key_name] ? "Ocultar chave" : "Mostrar chave"}
                      >
                        {show[key.key_name] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      onClick={() => handleSave(key.key_name)}
                      disabled={isPending || !currentValue.trim()}
                    >
                      {isPending ? (
                        <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                      ) : (
                        <Save className="mr-1.5 h-4 w-4" />
                      )}
                      {isConfigured ? "Atualizar" : "Salvar"}
                    </Button>

                    {isConfigured && (
                      <AlertDialog>
                        <AlertDialogTrigger
                          render={
                            <Button variant="outline" size="sm" disabled={isPending}>
                              <Trash2 className="mr-1.5 h-4 w-4" />
                              Remover
                            </Button>
                          }
                        />
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Remover chave {key.label}?</AlertDialogTitle>
                            <AlertDialogDescription>
                              A organização volta a usar a chave do pool global.
                              A chave removida não pode ser recuperada.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancelar</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => handleRemove(key.key_name)}
                              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            >
                              {isPending ? (
                                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                              ) : (
                                <Trash2 className="mr-1.5 h-4 w-4" />
                              )}
                              Remover
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}

        <button
          type="button"
          onClick={() => refetch()}
          className="text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          Recarregar status das chaves
        </button>
      </CardContent>
    </Card>
  );
}

function labelFor(keyName: KeyName): string {
  return KEYS.find((k) => k.key_name === keyName)?.label ?? keyName;
}
