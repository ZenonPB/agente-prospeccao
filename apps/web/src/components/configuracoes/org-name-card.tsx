"use client";

import { useState } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Loader2, Building2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { useOrgMembership, useRenameOrganization } from "@/hooks/use-api";

export function OrgNameCard() {
  const { data: membership } = useOrgMembership();
  const rename = useRenameOrganization();
  const org = membership?.organization;
  const myRole = membership?.membership?.role;
  const canManage = myRole === "OWNER" || myRole === "ADMIN";

  // Inicialização lazy; card remontado via key={org.id} para refletir renomeio.
  const [name, setName] = useState(() => org?.name ?? "");
  const [pending, setPending] = useState(false);

  const handleSave = async () => {
    if (!org?.id || !name.trim()) return;
    setPending(true);
    try {
      await rename.mutateAsync({ orgId: org.id, name: name.trim() });
      toast.success("Nome da organização atualizado.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao renomear organização.");
    } finally {
      setPending(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Building2 className="h-5 w-5 text-muted-foreground" />
          Organização
        </CardTitle>
        <CardDescription>
          Nome exibido no seletor e cabeçalhos
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <Label htmlFor="org-name">Nome da organização</Label>
            <Input
              id="org-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ex.: AlphaMec"
              disabled={!canManage}
              className="max-w-xs"
            />
          </div>
          {canManage ? (
            <Button size="sm" onClick={handleSave} disabled={pending || !name.trim()}>
              {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Salvar
            </Button>
          ) : (
            <ShieldCheck className="h-5 w-5 shrink-0 text-muted-foreground" />
          )}
        </div>
        {!canManage && (
          <p className="text-xs text-muted-foreground">
            Apenas o dono ou um administrador pode renomear a organização.
          </p>
        )}
      </CardContent>
    </Card>
  );
}