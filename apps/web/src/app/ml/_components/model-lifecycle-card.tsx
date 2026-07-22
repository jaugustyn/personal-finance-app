"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArchiveRestore, CheckCircle2, FlaskConical, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { queryKeys } from "@/lib/query-keys";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/error-state";

function gateLevel(
  gates: Record<string, unknown>,
  t: ReturnType<typeof useT>["t"],
): string {
  const level = gates.level;
  if (level === "thesis_ready") return t("ml.lifecycle.gate.thesisReady");
  if (level === "technical") return t("ml.lifecycle.gate.technical");
  if (level === "rejected") return t("ml.lifecycle.gate.rejected");
  return t("ml.lifecycle.gate.unknown");
}

function modelStatus(
  status: string,
  t: ReturnType<typeof useT>["t"],
): string {
  if (status === "active") return t("ml.lifecycle.status.active");
  if (status === "candidate") return t("ml.lifecycle.status.candidate");
  if (status === "archived") return t("ml.lifecycle.status.archived");
  if (status === "rejected") return t("ml.lifecycle.status.rejected");
  return status;
}

export function ModelLifecycleCard() {
  const { t } = useT();
  const qc = useQueryClient();
  const versions = useQuery({
    queryKey: queryKeys.ml.modelVersions,
    queryFn: () => api.modelVersions(),
  });
  const activate = useMutation({
    mutationFn: (id: string) => api.activateModelVersion(id),
    onSuccess: () => {
      toast.success(t("ml.lifecycle.activated"));
      void qc.invalidateQueries({ queryKey: queryKeys.ml.all });
    },
    onError: (error) => showErrorToast(error, t("ml.lifecycle.activateFailed")),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FlaskConical className="h-4 w-4 text-primary" />
          {t("ml.lifecycle.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {versions.isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : versions.isError ? (
          <ErrorState
            variant="compact"
            onRetry={() => void versions.refetch()}
          />
        ) : versions.data?.length ? (
          versions.data.map((version) => (
            <div
              key={version.id}
              className="flex flex-col gap-2 rounded-md border p-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
                  <span>{version.estimator} · {version.feature_set}</span>
                  <Badge variant={version.status === "active" ? "default" : "outline"}>
                    {modelStatus(version.status, t)}
                  </Badge>
                  <Badge variant="secondary">{gateLevel(version.gates, t)}</Badge>
                </div>
                <p className="mt-1 truncate text-xs text-muted-foreground">
                  {version.id}
                </p>
              </div>
              {version.promotable && version.status !== "active" ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => activate.mutate(version.id)}
                  disabled={activate.isPending}
                >
                  {version.status === "archived" ? (
                    <ArchiveRestore className="h-4 w-4" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4" />
                  )}
                  {version.status === "archived"
                    ? t("ml.lifecycle.restore")
                    : t("ml.lifecycle.activate")}
                </Button>
              ) : null}
            </div>
          ))
        ) : (
          <p className="text-sm text-muted-foreground">
            {t("ml.lifecycle.empty")}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
