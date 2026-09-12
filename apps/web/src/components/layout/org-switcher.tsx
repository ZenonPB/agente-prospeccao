"use client";

import { useState, useCallback, useEffect, useMemo, useSyncExternalStore } from "react";
import { Check, ChevronsUpDown, Building2, Plus, Loader2 } from "lucide-react";
import { useMyOrganizations, useCreateOrganization } from "@/hooks/use-api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import {
  getActiveOrganizationId,
  getServerActiveOrganizationId,
  setActiveOrganizationId,
  subscribeToActiveOrganization,
} from "@/lib/active-organization";
import { useRouter } from "next/navigation";
import type { SalesRole } from "@/types";

const SALES_ROLE_LABELS: Record<SalesRole, string> = {
  CONSULTOR: "Consultor",
  ANALYST: "Analista",
  MANAGER: "Gestor",
};

const ORG_ROLE_LABELS: Record<string, string> = {
  OWNER: "Proprietário",
  ADMIN: "Administrador",
  MEMBER: "Membro",
};

export function OrgSwitcher({ collapsed = false }: { collapsed?: boolean }) {
  const router = useRouter();
  const { data: orgsData, isLoading } = useMyOrganizations();
  const createOrg = useCreateOrganization();
  const [open, setOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const activeOrgId = useSyncExternalStore(
    subscribeToActiveOrganization,
    getActiveOrganizationId,
    getServerActiveOrganizationId,
  );

  const organizations = useMemo(() => orgsData?.organizations || [], [orgsData]);
  const activeOrg = useMemo(
    () => organizations.find((org) => org.id === activeOrgId) ?? organizations[0],
    [organizations, activeOrgId],
  );

  useEffect(() => {
    // Membership pode ser revogada em outra sessão enquanto um id antigo ficou
    // persistido no navegador. Normaliza para uma membership válida para que a
    // UI nunca mostre um workspace enquanto a API envia o header de outro.
    const fallbackId = organizations[0]?.id;
    if (!fallbackId) return;
    const hasValidActiveOrg = organizations.some((org) => org.id === activeOrgId);
    if (!hasValidActiveOrg) setActiveOrganizationId(fallbackId);
  }, [activeOrgId, organizations]);

  const handleSelectOrg = useCallback(
    (orgId: string) => {
      const selected = organizations.find((org) => org.id === orgId);
      if (!selected || activeOrg?.id === orgId) {
        setOpen(false);
        return;
      }

      setActiveOrganizationId(orgId);
      setOpen(false);
      toast.success(`Workspace alterado para ${selected.name}.`);
      router.refresh();
    },
    [activeOrg?.id, organizations, router],
  );

  const handleCreateOrg = async () => {
    const normalizedName = name.trim();
    if (!normalizedName) return;

    try {
      const created = await createOrg.mutateAsync({ name: normalizedName });
      setCreateOpen(false);
      setName("");
      setActiveOrganizationId(created.id);
      toast.success("Organização criada e selecionada.");
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao criar organização.");
    }
  };

  if (isLoading || !organizations.length) {
    return null;
  }

  const singleOrganizationTrigger = organizations.length === 1 && !collapsed ? (
    <div className="flex items-center gap-2 px-3 py-2 text-sm text-sidebar-foreground/70">
      <Building2 className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className="truncate">{activeOrg?.name || "Minha Organização"}</span>
      <Button
        variant="ghost"
        size="icon"
        className="ml-auto h-6 w-6"
        onClick={() => setCreateOpen(true)}
        aria-label="Criar novo workspace"
      >
        <Plus className="h-4 w-4" aria-hidden="true" />
      </Button>
    </div>
  ) : null;

  return (
    <>
      {singleOrganizationTrigger ?? (
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger
            render={
              <Button
                variant="ghost"
                role="combobox"
                aria-expanded={open}
                aria-label={`Organização ativa: ${activeOrg?.name || "Selecione"}`}
                className={cn(
                  "w-full justify-between border border-sidebar-border bg-sidebar-accent/50 text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground",
                  collapsed && "w-10 justify-center p-0",
                )}
              />
            }
          >
            {collapsed ? (
              <Building2 className="h-4 w-4 shrink-0" aria-hidden="true" />
            ) : (
              <>
                <span className="truncate text-left">
                  {activeOrg?.name || "Selecione..."}
                </span>
                <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" aria-hidden="true" />
              </>
            )}
          </PopoverTrigger>
          <PopoverContent className="w-[260px] p-0" align="start">
            <Command>
              <CommandList>
                <CommandEmpty>Nenhuma organização encontrada.</CommandEmpty>
                <CommandGroup heading="Workspaces">
                  {organizations.map((org) => {
                    const isActive = activeOrg?.id === org.id;
                    return (
                      <CommandItem
                        key={org.id}
                        value={`${org.name} ${org.id}`}
                        onSelect={() => handleSelectOrg(org.id)}
                        aria-current={isActive ? "true" : undefined}
                      >
                        <Check
                          className={cn(
                            "mr-2 h-4 w-4",
                            isActive ? "opacity-100" : "opacity-0",
                          )}
                          aria-hidden="true"
                        />
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-medium">{org.name}</p>
                          <p className="truncate text-xs text-muted-foreground">
                            {ORG_ROLE_LABELS[org.role] || "Membro"} · {SALES_ROLE_LABELS[org.sales_role] || org.sales_role}
                          </p>
                        </div>
                      </CommandItem>
                    );
                  })}
                  <CommandItem
                    value="__create__"
                    onSelect={() => setCreateOpen(true)}
                    className="border-t border-border/60 text-muted-foreground"
                  >
                    <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
                    Criar organização
                  </CommandItem>
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-[420px]">
          <DialogHeader>
            <DialogTitle>Criar organização</DialogTitle>
            <DialogDescription>
              Crie um workspace independente. Campanhas, leads, equipe e relatórios ficam isolados dos demais.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="new-org-name">Nome do workspace</Label>
            <Input
              id="new-org-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Ex.: Vendas Samuel e Zenon"
              autoComplete="organization"
              onKeyDown={(event) => {
                if (event.key === "Enter" && !createOrg.isPending) {
                  void handleCreateOrg();
                }
              }}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => void handleCreateOrg()}
              disabled={createOrg.isPending || !name.trim()}
            >
              {createOrg.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : null}
              {createOrg.isPending ? "Criando..." : "Criar workspace"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
