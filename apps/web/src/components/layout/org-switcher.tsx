"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { Check, ChevronsUpDown, Building2 } from "lucide-react";
import { useMyOrganizations } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
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
  const [open, setOpen] = useState(false);
  const [activeOrgId, setActiveOrgId] = useState<string | null>(() => readStoredOrgId());

  const organizations = useMemo(() => orgsData?.organizations || [], [orgsData]);

  useEffect(() => {
    if (!organizations.length) return;
    const stored = readStoredOrgId();
    const validIds = new Set(organizations.map((o) => o.id));
    if (stored && validIds.has(stored)) {
      setActiveOrgId(stored);
    } else {
      const firstId = organizations[0].id;
      setActiveOrgId(firstId);
      localStorage.setItem(ORG_STORAGE_KEY, firstId);
    }
  }, [organizations]);

  const activeOrg = useMemo(
    () => organizations.find((org) => org.id === activeOrgId),
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

  if (isLoading || !organizations.length) {
    return null;
  }

  if (organizations.length === 1 && !collapsed) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
        <Building2 className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span className="truncate">{activeOrg?.name || "Minha Organização"}</span>
      </div>
    );
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            aria-label={`Organização ativa: ${activeOrg?.name || "Selecione"}`}
            className={cn(
              "w-full justify-between",
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
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export function getActiveOrgId(): string | null {
  return readStoredOrgId();
}
