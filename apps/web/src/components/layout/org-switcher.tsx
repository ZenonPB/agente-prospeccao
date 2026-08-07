"use client";

import { useState, useCallback, useMemo } from "react";
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
import { useRouter } from "next/navigation";
import type { SalesRole } from "@/types";

const ORG_STORAGE_KEY = "active_organization_id";
const ORG_STORAGE_VERSION = "org_storage_v1";

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

function readStoredOrgId(): string | null {
  if (typeof window === "undefined") return null;
  const version = localStorage.getItem(ORG_STORAGE_VERSION);
  if (version !== "1") {
    localStorage.removeItem(ORG_STORAGE_KEY);
    localStorage.setItem(ORG_STORAGE_VERSION, "1");
    return null;
  }
  return localStorage.getItem(ORG_STORAGE_KEY);
}

export function OrgSwitcher({ collapsed = false }: { collapsed?: boolean }) {
  const router = useRouter();
  const { data: orgsData, isLoading } = useMyOrganizations();
  const createOrg = useCreateOrganization();
  const [open, setOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [activeOrgId, setActiveOrgId] = useState<string | null>(() => readStoredOrgId());

  const organizations = useMemo(() => orgsData?.organizations || [], [orgsData]);

  // Item 4.10: sem setState em effect — a org ativa é derivada em render.
  // Se o id persistido não estiver entre as orgs carregadas (ou ainda não
  // houver orgs), cai na primeira org. A persistência em localStorage só
  // acontece quando o usuário escolhe explicitamente (handleSelectOrg).
  const activeOrg = useMemo(
    () => organizations.find((org) => org.id === activeOrgId) ?? organizations[0],
    [organizations, activeOrgId],
  );

  const handleSelectOrg = useCallback(
    (orgId: string) => {
      setActiveOrgId(orgId);
      localStorage.setItem(ORG_STORAGE_KEY, orgId);
      setOpen(false);
      router.refresh();
    },
    [router],
  );

  const handleCreateOrg = async () => {
    if (!name.trim()) return;
    try {
      const created = await createOrg.mutateAsync({ name: name.trim() });
      setCreateOpen(false);
      setName("");
      handleSelectOrg(created.id);
      toast.success("Organização criada.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Erro ao criar organização.");
    }
  };

  if (isLoading || !organizations.length) {
    return null;
  }

  if (organizations.length === 1 && !collapsed) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-sm text-sidebar-foreground/70">
        <Building2 className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span className="truncate">{activeOrg?.name || "Minha Organização"}</span>
        <Button
          variant="ghost"
          size="icon"
          className="ml-auto h-6 w-6"
          onClick={() => setCreateOpen(true)}
          aria-label="Criar organização"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    );
  }

  return (
    <>
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
              collapsed && "w-10 p-0 justify-center"
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
      <PopoverContent className="w-[240px] p-0" align="start">
        <Command>
          <CommandList>
            <CommandEmpty>Nenhuma organização encontrada.</CommandEmpty>
            <CommandGroup>
              {organizations.map((org) => (
                <CommandItem
                  key={org.id}
                  value={org.id}
                  onSelect={() => handleSelectOrg(org.id)}
                >
                  <Check
                    className={cn(
                      "mr-2 h-4 w-4",
                      activeOrgId === org.id ? "opacity-100" : "opacity-0"
                    )}
                    aria-hidden="true"
                  />
                  <div className="flex flex-col">
                    <span className="font-medium">{org.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {ORG_ROLE_LABELS[org.role] || "Membro"} · {SALES_ROLE_LABELS[org.sales_role] || org.sales_role}
                    </span>
                  </div>
                </CommandItem>
              ))}
              <CommandItem
                value="__create__"
                onSelect={() => {
                  setCreateOpen(true);
                }}
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

    <Dialog open={createOpen} onOpenChange={setCreateOpen}>
      <DialogContent className="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>Criar organização</DialogTitle>
          <DialogDescription>
            Crie um workspace dedicado (ex.: o da empresa). Você vira proprietário.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="new-org-name">Nome</Label>
          <Input
            id="new-org-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ex.: AlphaMec"
            onKeyDown={(e) => {
              if (e.key === "Enter") handleCreateOrg();
            }}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setCreateOpen(false)}>
            Cancelar
          </Button>
          <Button onClick={handleCreateOrg} disabled={createOrg.isPending || !name.trim()}>
            {createOrg.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Criar
          </Button>
        </DialogFooter>
      </DialogContent>
      </Dialog>
    </>
  );
}

export function getActiveOrgId(): string | null {
  return readStoredOrgId();
}
