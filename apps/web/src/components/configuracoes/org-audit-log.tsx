"use client";

import { useState } from "react";
import { ScrollText, RefreshCw, ShieldAlert } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useOrgAuditLog } from "@/hooks/use-api";
import type { OrgAuditEvent } from "@/types";

const EVENT_META: Record<OrgAuditEvent, { label: string; badge: string }> = {
  ORG_CREATED: { label: "Organização criada", badge: "" },
  ORG_RENAMED: { label: "Organização renomeada", badge: "" },
  ORG_SETTINGS_UPDATED: { label: "Configurações alteradas", badge: "" },
  MEMBER_ROLE_CHANGED: { label: "Papel de venda alterado", badge: "text-amber-600 border-amber-200 bg-amber-50" },
  MEMBER_REMOVED: { label: "Membro removido", badge: "text-destructive border-destructive/20 bg-destructive/5" },
  MEMBER_LEFT: { label: "Membro saiu da organização", badge: "text-destructive border-destructive/20 bg-destructive/5" },
  OWNER_TRANSFERRED: { label: "Dono transferido", badge: "text-amber-600 border-amber-200 bg-amber-50" },
  INVITE_CREATED: { label: "Convite criado", badge: "text-sky-600 border-sky-200 bg-sky-50" },
  INVITE_ACCEPTED: { label: "Convite aceito", badge: "text-sky-600 border-sky-200 bg-sky-50" },
  INVITE_REVOKED: { label: "Convite revogado", badge: "text-sky-600 border-sky-200 bg-sky-50" },
  SECRET_SET: { label: "Chave de API configurada", badge: "text-violet-600 border-violet-200 bg-violet-50" },
  SECRET_DELETED: { label: "Chave de API removida", badge: "text-violet-600 border-violet-200 bg-violet-50" },
  SALES_TARGET_UPSERTED: { label: "Meta de vendas salva", badge: "" },
  SALES_TARGET_DELETED: { label: "Meta de vendas removida", badge: "" },
};

const TARGET_LABELS: Record<string, string> = {
  member: "Membro",
  invite: "Convite",
  secret: "Chave",
  target: "Meta",
  org: "Organização",
};

function formatWhen(iso?: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function targetHumanized(targetType?: string | null, targetId?: string | null): string {
  const prefix = targetType ? `${TARGET_LABELS[targetType] ?? targetType}` : "";
  if (!targetId) return prefix;
  return prefix ? `${prefix} · ${targetId}` : targetId;
}

export function OrgAuditLog({ orgId }: { orgId: string }) {
  const [event, setEvent] = useState<string>("");
  const { data, isLoading, isError, error, refetch } = useOrgAuditLog(orgId, event || undefined);

  const entries = data?.entries || [];

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="flex items-center gap-2">
            <ScrollText className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            Auditoria de acessos
          </CardTitle>
          <CardDescription>
            Registro de quem criou convite, mudou papel, removeu membro, alterou chave ou meta.
            Valores de chave nunca são exibidos.
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <Select value={event} onValueChange={(value) => setEvent(value ?? "")}>
            <SelectTrigger size="sm" className="w-52">
              <SelectValue>
                {(value) =>
                  value ? (EVENT_META[value as OrgAuditEvent]?.label ?? value) : "Todos os eventos"
                }
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">Todos os eventos</SelectItem>
              {(Object.keys(EVENT_META) as OrgAuditEvent[]).map((ev) => (
                <SelectItem key={ev} value={ev}>
                  {EVENT_META[ev].label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" size="icon" className="h-9 w-9" onClick={() => refetch()} aria-label="Recarregar auditoria">
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : isError ? (
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <ShieldAlert className="h-8 w-8 text-destructive" aria-hidden="true" />
            <p className="text-sm font-medium">Não foi possível carregar a auditoria</p>
            <p className="text-xs text-muted-foreground">
              {error instanceof Error ? error.message : "Tente novamente mais tarde"}
            </p>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              Tentar novamente
            </Button>
          </div>
        ) : entries.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Nenhum evento registrado{event ? " para este filtro" : " ainda"}.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Quando</TableHead>
                <TableHead>Evento</TableHead>
                <TableHead>Quem</TableHead>
                <TableHead>Detalhe</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.map((entry) => {
                const meta = EVENT_META[entry.event];
                const who = entry.actor_name || entry.actor_email || "Sistema";
                const target = targetHumanized(entry.target_type, entry.target_id);
                return (
                  <TableRow key={entry.id}>
                    <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                      {formatWhen(entry.created_at)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={`font-normal ${meta?.badge ?? ""}`}>
                        {meta?.label ?? entry.event}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm">{who}</span>
                      {entry.actor_email && entry.actor_name ? (
                        <p className="text-xs text-muted-foreground">{entry.actor_email}</p>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-muted-foreground">{entry.detail || target || "—"}</span>
                      {entry.detail && target ? (
                        <p className="text-xs text-muted-foreground">{target}</p>
                      ) : null}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}