"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot } from "lucide-react";
import { toast } from "sonner";

import { HelpTooltip } from "@/components/help-tooltip";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  api,
  type AssistantSettings,
  type AssistantSettingsInput,
} from "@/lib/api";
import { useT } from "@/lib/i18n";
import { queryKeys } from "@/lib/query-keys";
import { showErrorToast } from "@/lib/toasts";

function statusFor(
  settings: AssistantSettings,
  t: ReturnType<typeof useT>["t"],
) {
  if (!settings.configuration_enabled) {
    return {
      label: t("settings.assistantStatusConfigurationDisabled"),
      variant: "muted" as const,
      help: t("settings.assistantConfigurationDisabledHelp"),
    };
  }
  if (!settings.user_enabled) {
    return {
      label: t("settings.assistantStatusDisabled"),
      variant: "muted" as const,
      help: t("settings.assistantDeterministicHelp"),
    };
  }
  if (!settings.ollama_available) {
    return {
      label: t("settings.assistantStatusUnavailable"),
      variant: "warning" as const,
      help: t("settings.assistantUnavailableHelp"),
    };
  }
  return {
    label: t("settings.assistantStatusAvailable"),
    variant: "success" as const,
    help: t("settings.assistantHybridHelp"),
  };
}

export function AssistantSettingsCard() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: queryKeys.profile.assistant,
    queryFn: () => api.assistantSettings(),
  });
  const update = useMutation({
    mutationFn: (payload: AssistantSettingsInput) =>
      api.updateAssistantSettings(payload),
    onSuccess: (settings) => {
      queryClient.setQueryData(queryKeys.profile.assistant, settings);
      toast.success(t("settings.assistantSaved"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  if (query.isLoading) {
    return (
      <Card className="max-w-3xl">
        <CardContent className="flex min-h-16 items-center justify-between gap-4 p-5">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-5 w-9 rounded-full" />
        </CardContent>
      </Card>
    );
  }

  if (query.isError || !query.data) {
    return (
      <Card className="max-w-3xl">
        <CardContent className="flex items-center justify-between gap-4 p-5">
          <p className="text-sm text-destructive">
            {t("settings.assistantLoadError")}
          </p>
          <button
            type="button"
            className="text-sm font-medium text-primary underline-offset-4 hover:underline"
            onClick={() => void query.refetch()}
          >
            {t("common.retry")}
          </button>
        </CardContent>
      </Card>
    );
  }

  const settings = query.data;
  const status = statusFor(settings, t);
  const modelEnabled =
    settings.configuration_enabled && settings.user_enabled;
  const selectedModelAvailable = settings.available_models.includes(
    settings.model,
  );
  return (
    <Card className="max-w-3xl">
      <CardContent className="p-0">
        <div className="flex min-h-16 items-center justify-between gap-4 p-5">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <HelpTooltip content={t("settings.assistantLocalModelHelp")}>
              <Label
                htmlFor="assistant-llm-enabled"
                className="flex items-center gap-2 text-base text-foreground"
              >
                <Bot className="h-4 w-4 text-primary" />
                {t("settings.assistantLocalModel")}
              </Label>
            </HelpTooltip>
            <HelpTooltip content={status.help}>
              <Badge variant={status.variant}>{status.label}</Badge>
            </HelpTooltip>
          </div>
          <Switch
            id="assistant-llm-enabled"
            checked={modelEnabled}
            onCheckedChange={(enabled) => update.mutate({ enabled })}
            disabled={!settings.configuration_enabled || update.isPending}
          />
        </div>

        {modelEnabled && (
          <div className="grid gap-2 border-t p-5 sm:grid-cols-[8rem_minmax(0,1fr)] sm:items-center">
            <HelpTooltip content={t("settings.assistantModelHelp")}>
              <Label htmlFor="assistant-llm-model">
                {t("settings.assistantModel")}
              </Label>
            </HelpTooltip>
            <Select
              value={settings.model}
              onValueChange={(model) =>
                update.mutate({ enabled: true, model })
              }
              disabled={
                update.isPending || settings.available_models.length === 0
              }
            >
              <SelectTrigger id="assistant-llm-model" className="w-full sm:max-w-md">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {!selectedModelAvailable && (
                  <SelectItem value={settings.model} disabled>
                    {settings.model}
                  </SelectItem>
                )}
                {settings.available_models.map((model) => (
                  <SelectItem key={model} value={model} indicatorPosition="right">
                    {model}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
