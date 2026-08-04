"use client";

import { useState, useEffect } from "react";
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

const ORG_STORAGE_KEY = "active_organization_id";

export function OrgSwitcher({ collapsed = false }: { collapsed?: boolean }) {
  const router = useRouter();
  const { data: orgsData, isLoading } = useMyOrganizations();
  const [open, setOpen] = useState(false);
  const [activeOrgId, setActiveOrgId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(ORG_STORAGE_KEY);
      if (stored) {
        setActiveOrgId(stored);
      } else if (orgsData?.organizations?.length) {
        const firstOrg = orgsData.organizations[0];
        setActiveOrgId(firstOrg.id);
        localStorage.setItem(ORG_STORAGE_KEY, firstOrg.id);
      }
    }
  }, [orgsData]);

  const organizations = orgsData?.organizations || [];
  const activeOrg = organizations.find((org) => org.id === activeOrgId);

  const handleSelectOrg = (orgId: string) => {
    setActiveOrgId(orgId);
    localStorage.setItem(ORG_STORAGE_KEY, orgId);
    setOpen(false);
    router.refresh();
  };

  if (isLoading || !organizations.length) {
    return null;
  }

  if (organizations.length === 1 && !collapsed) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
        <Building2 className="h-4 w-4 shrink-0" />
        <span className="truncate">{activeOrg?.name || "Minha Organização"}</span>
      </div>
    );
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn(
            "w-full justify-between",
            collapsed && "w-10 p-0 justify-center"
          )}
        >
          {collapsed ? (
            <Building2 className="h-4 w-4 shrink-0" />
          ) : (
            <>
              <span className="truncate text-left">
                {activeOrg?.name || "Selecione..."}
              </span>
              <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
            </>
          )}
        </Button>
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
                  />
                  <div className="flex flex-col">
                    <span className="font-medium">{org.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {org.role === "OWNER" ? "Proprietário" : org.role === "ADMIN" ? "Administrador" : "Membro"} · {org.sales_role}
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
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ORG_STORAGE_KEY);
}
