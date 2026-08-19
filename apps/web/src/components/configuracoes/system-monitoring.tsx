"use client";

import { useState } from "react";
import { useOrgMembership, useWebhookLogs, useJobLogs } from "@/hooks/use-api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Activity, Radio, CheckCircle2, XCircle, Clock, AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export function SystemMonitoringPanel() {
  const { data: orgData } = useOrgMembership();
  const orgId = orgData?.organization?.id;
  const [activeTab, setActiveTab] = useState<"webhooks" | "jobs">("webhooks");

  const {
    data: webhookLogs,
    isLoading: loadingWebhooks,
    refetch: refetchWebhooks,
    isRefetching: refetchingWebhooks,
  } = useWebhookLogs(orgId, 50);

  const {
    data: jobLogs,
    isLoading: loadingJobs,
    refetch: refetchJobs,
    isRefetching: refetchingJobs,
  } = useJobLogs(orgId, 50);

  if (!orgId) return null;

  return (
    <Card className="border shadow-sm">
      <CardHeader className="flex flex-row items-center justify-between pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-primary" />
            <CardTitle className="text-lg font-semibold">Monitoramento de Notificações e Tarefas da IA</CardTitle>
          </div>
          <CardDescription className="mt-1 text-xs">
            Acompanhe o envio automático de notificações para outros sistemas e o andamento das buscas em segundo plano.
          </CardDescription>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => (activeTab === "webhooks" ? refetchWebhooks() : refetchJobs())}
          disabled={refetchingWebhooks || refetchingJobs}
          className="gap-2 text-xs"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refetchingWebhooks || refetchingJobs ? "animate-spin" : ""}`} />
          Atualizar
        </Button>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as "webhooks" | "jobs")}>
          <TabsList className="grid w-full grid-cols-2 mb-4">
            <TabsTrigger value="webhooks" className="gap-2 text-xs">
              <Radio className="h-3.5 w-3.5" />
              Notificações Enviadas
              {webhookLogs && webhookLogs.length > 0 && (
                <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">
                  {webhookLogs.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="jobs" className="gap-2 text-xs">
              <Clock className="h-3.5 w-3.5" />
              Tarefas de Busca e Análise
              {jobLogs && jobLogs.length > 0 && (
                <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">
                  {jobLogs.length}
                </Badge>
              )}
            </TabsTrigger>
          </TabsList>

          {/* Webhooks Tab */}
          <TabsContent value="webhooks">
            {loadingWebhooks ? (
              <p className="py-6 text-center text-xs text-muted-foreground">Carregando histórico de notificações...</p>
            ) : !webhookLogs || webhookLogs.length === 0 ? (
              <div className="py-8 text-center border rounded-lg bg-muted/20">
                <Radio className="mx-auto h-8 w-8 text-muted-foreground/50 mb-2" />
                <p className="text-sm font-medium">Nenhuma notificação enviada ainda</p>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
                  Configure um link de notificação acima para avisar seus sistemas quando um novo cliente for encontrado.
                </p>
              </div>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {webhookLogs.map((log) => (
                  <div key={log.id} className="flex flex-col gap-2 p-3 rounded-lg border bg-card text-xs">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {log.success ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                        ) : (
                          <XCircle className="h-4 w-4 text-destructive shrink-0" />
                        )}
                        <span className="font-mono font-semibold text-primary">{log.event_type}</span>
                        <Badge variant={log.success ? "default" : "destructive"} className="text-[10px]">
                          {log.status_code ? `HTTP ${log.status_code}` : log.success ? "200 OK" : "FALHA"}
                        </Badge>
                      </div>
                      <span className="text-[11px] text-muted-foreground">
                        {log.created_at ? new Date(log.created_at).toLocaleString("pt-BR") : "—"}
                      </span>
                    </div>
                    <p className="font-mono text-[11px] text-muted-foreground truncate">{log.target_url}</p>
                    {log.error_message && (
                      <p className="text-[11px] text-destructive bg-destructive/10 p-2 rounded font-mono">
                        Erro: {log.error_message}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          {/* Jobs Tab */}
          <TabsContent value="jobs">
            {loadingJobs ? (
              <p className="py-6 text-center text-xs text-muted-foreground">Carregando tarefas em segundo plano...</p>
            ) : !jobLogs || jobLogs.length === 0 ? (
              <div className="py-8 text-center border rounded-lg bg-muted/20">
                <Clock className="mx-auto h-8 w-8 text-muted-foreground/50 mb-2" />
                <p className="text-sm font-medium">Nenhuma tarefa realizada ainda</p>
                <p className="text-xs text-muted-foreground mt-1">
                  As buscas, análises de sites e avaliações por IA aparecerão aqui durante a execução.
                </p>
              </div>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {jobLogs.map((job) => (
                  <div key={job.id} className="flex flex-col gap-2 p-3 rounded-lg border bg-card text-xs">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {job.status === "COMPLETED" ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                        ) : job.status === "FAILED" ? (
                          <XCircle className="h-4 w-4 text-destructive shrink-0" />
                        ) : (
                          <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
                        )}
                        <span className="font-semibold">{job.job_type || "JOB"}</span>
                        <Badge
                          variant={job.status === "COMPLETED" ? "default" : job.status === "FAILED" ? "destructive" : "secondary"}
                          className="text-[10px]"
                        >
                          {job.status}
                        </Badge>
                      </div>
                      <span className="text-[11px] text-muted-foreground">
                        {job.created_at ? new Date(job.created_at).toLocaleString("pt-BR") : "—"}
                      </span>
                    </div>
                    {job.error_message && (
                      <p className="text-[11px] text-destructive bg-destructive/10 p-2 rounded font-mono">
                        {job.error_message}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
