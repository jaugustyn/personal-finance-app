"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArchiveRestore, CheckCircle2, FlaskConical, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { showErrorToast } from "@/lib/toasts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function gateLevel(gates: Record<string, unknown>): string {
  const level = gates.level;
  if (level === "thesis_ready") return "gotowy do magisterki";
  if (level === "technical") return "spełnia bramki";
  if (level === "rejected") return "nie spełnia bramek";
  return "brak oceny";
}

function modelStatus(status: string): string {
  if (status === "active") return "aktywny";
  if (status === "candidate") return "kandydat";
  if (status === "archived") return "archiwalny";
  if (status === "rejected") return "odrzucony";
  return status;
}

export function ModelLifecycleCard() {
  const qc = useQueryClient();
  const versions = useQuery({
    queryKey: ["mlModelVersions"],
    queryFn: () => api.modelVersions(),
  });
  const activate = useMutation({
    mutationFn: (id: string) => api.activateModelVersion(id),
    onSuccess: () => {
      toast.success("Wersja modelu została aktywowana.");
      void qc.invalidateQueries({ queryKey: ["mlModelVersions"] });
      void qc.invalidateQueries({ queryKey: ["mlDashboard"] });
    },
    onError: (error) => showErrorToast(error, "Nie udało się aktywować modelu"),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FlaskConical className="h-4 w-4 text-primary" />
          Wersje modeli
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {versions.isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : versions.isError ? (
          <p className="text-sm text-destructive">Nie udało się pobrać wersji.</p>
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
                    {modelStatus(version.status)}
                  </Badge>
                  <Badge variant="secondary">{gateLevel(version.gates)}</Badge>
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
                  {version.status === "archived" ? "Przywróć" : "Aktywuj"}
                </Button>
              ) : null}
            </div>
          ))
        ) : (
          <p className="text-sm text-muted-foreground">
            Brak kandydatów. Trening nie aktywuje modelu automatycznie.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
