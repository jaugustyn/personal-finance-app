"use client";

import * as React from "react";
import { Loader2, LockKeyhole } from "lucide-react";
import { toast } from "sonner";
import { api, type AppLockStatus } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { useAppLock } from "@/components/app-lock-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

const TIMEOUTS = [5, 15, 30, 60] as const;
type TimeoutMinutes = (typeof TIMEOUTS)[number];

export function AppLockSettings() {
  const { t } = useT();
  const appLock = useAppLock();
  const [desiredEnabled, setDesiredEnabled] = React.useState<boolean | null>(
    null,
  );
  const [timeoutDraft, setTimeoutMinutes] =
    React.useState<TimeoutMinutes | null>(null);
  const [currentCode, setCurrentCode] = React.useState("");
  const [newCode, setNewCode] = React.useState("");
  const [repeatCode, setRepeatCode] = React.useState("");
  const [error, setError] = React.useState("");
  const [pending, setPending] = React.useState(false);

  const enabled = desiredEnabled ?? appLock.status.enabled;
  const timeout =
    timeoutDraft ?? (appLock.status.timeout_minutes as TimeoutMinutes);

  const resetSecrets = () => {
    setCurrentCode("");
    setNewCode("");
    setRepeatCode("");
    setError("");
  };

  const validateNewCode = (required: boolean) => {
    if (required || newCode) {
      if (newCode.length < 6 || newCode.length > 128) {
        setError(t("settings.appLockCodeLength"));
        return false;
      }
      if (newCode !== repeatCode) {
        setError(t("settings.appLockCodesMismatch"));
        return false;
      }
    }
    setError("");
    return true;
  };

  const finish = (next: AppLockStatus, message: string) => {
    appLock.applyStatus(next, true);
    setDesiredEnabled(null);
    setTimeoutMinutes(null);
    resetSecrets();
    toast.success(message);
  };

  const save = async () => {
    const firstSetup = !appLock.status.enabled;
    if (!validateNewCode(firstSetup)) return;
    if (!firstSetup && currentCode.length < 6) {
      setError(t("settings.appLockCodeLength"));
      return;
    }
    setPending(true);
    try {
      if (firstSetup) {
        finish(
          await api.setupAppLock({
            code: newCode,
            timeout_minutes: timeout,
          }),
          t("settings.appLockEnabledToast"),
        );
      } else {
        finish(
          await api.updateAppLock({
            enabled: true,
            current_code: currentCode,
            timeout_minutes: timeout,
            new_code: newCode || null,
          }),
          t("toast.saved"),
        );
      }
    } catch (caught) {
      showErrorToast(caught, t("toast.error"));
    } finally {
      setPending(false);
    }
  };

  const disable = async () => {
    if (currentCode.length < 6) {
      setError(t("settings.appLockCodeLength"));
      return;
    }
    setPending(true);
    try {
      finish(
        await api.updateAppLock({
          enabled: false,
          current_code: currentCode,
          timeout_minutes: timeout,
        }),
        t("settings.appLockDisabledToast"),
      );
    } catch (caught) {
      showErrorToast(caught, t("toast.error"));
    } finally {
      setPending(false);
    }
  };

  const showForm = enabled || appLock.status.enabled;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <LockKeyhole className="h-4 w-4 text-primary" />
          {t("settings.appLock")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-center justify-between gap-4">
          <div className="space-y-1">
            <Label htmlFor="app-lock-enabled">
              {t("settings.appLockEnabled")}
            </Label>
            <p className="text-xs text-muted-foreground">
              {t("settings.appLockHelp")}
            </p>
          </div>
          <Switch
            id="app-lock-enabled"
            checked={enabled}
            onCheckedChange={(checked) => {
              setDesiredEnabled(checked);
              resetSecrets();
            }}
            disabled={pending}
          />
        </div>

        {showForm && (
          <div className="grid max-w-3xl gap-4 border-t pt-5 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="app-lock-timeout">
                {t("settings.appLockTimeout")}
              </Label>
              <Select
                value={String(timeout)}
                onValueChange={(value) =>
                  setTimeoutMinutes(Number(value) as TimeoutMinutes)
                }
                disabled={!enabled || pending}
              >
                <SelectTrigger id="app-lock-timeout">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TIMEOUTS.map((value) => (
                    <SelectItem key={value} value={String(value)}>
                      {t("settings.appLockMinutes", { count: value })}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {appLock.status.enabled && (
              <div className="space-y-2">
                <Label htmlFor="app-lock-current-code">
                  {t("settings.appLockCurrentCode")}
                </Label>
                <Input
                  id="app-lock-current-code"
                  type="password"
                  autoComplete="current-password"
                  value={currentCode}
                  onChange={(event) => setCurrentCode(event.target.value)}
                  maxLength={128}
                  disabled={pending}
                />
              </div>
            )}

            {enabled && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="app-lock-new-code">
                    {appLock.status.enabled
                      ? t("settings.appLockNewCode")
                      : t("appLock.code")}
                  </Label>
                  <Input
                    id="app-lock-new-code"
                    type="password"
                    autoComplete="new-password"
                    value={newCode}
                    onChange={(event) => setNewCode(event.target.value)}
                    minLength={appLock.status.enabled ? undefined : 6}
                    maxLength={128}
                    disabled={pending}
                  />
                  {appLock.status.enabled && (
                    <p className="text-xs text-muted-foreground">
                      {t("settings.appLockLeaveCode")}
                    </p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="app-lock-repeat-code">
                    {t("settings.appLockRepeatCode")}
                  </Label>
                  <Input
                    id="app-lock-repeat-code"
                    type="password"
                    autoComplete="new-password"
                    value={repeatCode}
                    onChange={(event) => setRepeatCode(event.target.value)}
                    maxLength={128}
                    disabled={pending || (!newCode && appLock.status.enabled)}
                  />
                </div>
              </>
            )}
          </div>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}

        {enabled && (
          <Button onClick={() => void save()} disabled={pending}>
            {pending && <Loader2 className="h-4 w-4 animate-spin" />}
            {appLock.status.enabled
              ? t("settings.appLockSave")
              : t("settings.appLockEnable")}
          </Button>
        )}
        {!enabled && appLock.status.enabled && (
          <Button
            variant="outline"
            onClick={() => void disable()}
            disabled={pending}
          >
            {pending && <Loader2 className="h-4 w-4 animate-spin" />}
            {t("settings.appLockDisable")}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
