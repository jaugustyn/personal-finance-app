"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArchiveRestore,
  CheckCircle2,
  ChevronDown,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useFormatters, useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { queryKeys } from "@/lib/query-keys";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/error-state";
import { estimatorName } from "../_lib/ml-format";

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
  const { formatDateTime } = useFormatters();
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
    <details className="group overflow-hidden rounded-lg border bg-card">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3.5 [&::-webkit-details-marker]:hidden">
        <span className="font-medium text-foreground">
          {t("ml.lifecycle.title")}
        </span>
        <span className="flex items-center gap-2">
          {versions.data?.length ? (
            <Badge variant="muted">{versions.data.length}</Badge>
          ) : null}
          <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180" />
        </span>
      </summary>

      <div className="border-t p-4">
        {versions.isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : versions.isError ? (
          <ErrorState
            variant="compact"
            onRetry={() => void versions.refetch()}
          />
        ) : versions.data?.length ? (
          <div className="divide-y overflow-hidden rounded-md border">
            {versions.data.map((version) => (
              <div
                key={version.id}
                className="flex flex-col gap-3 px-3 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
                    <span>
                      {estimatorName(version.estimator)} · {version.feature_set}
                    </span>
                    <Badge
                      variant={
                        version.status === "active" ? "default" : "outline"
                      }
                    >
                      {modelStatus(version.status, t)}
                    </Badge>
                    <Badge variant="secondary">
                      {gateLevel(version.gates, t)}
                    </Badge>
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground">
                    {formatDateTime(version.created_at)} · {version.id.slice(0, 8)}
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
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            {t("ml.lifecycle.empty")}
          </p>
        )}
      </div>
    </details>
  );
}
