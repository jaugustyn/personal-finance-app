"use client";

import * as React from "react";
import { Loader2, LockKeyhole } from "lucide-react";
import { toast } from "sonner";
import { api, type AppLockStatus } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import {
  APP_LOCK_MIN_CODE_LENGTH,
  useAppLock,
} from "@/components/app-lock-provider";
import { HelpTooltip } from "@/components/help-tooltip";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
      if (
        newCode.length < APP_LOCK_MIN_CODE_LENGTH ||
        newCode.length > 128
      ) {
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
    if (!firstSetup && currentCode.length < APP_LOCK_MIN_CODE_LENGTH) {
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
    if (currentCode.length < APP_LOCK_MIN_CODE_LENGTH) {
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

  const isDisabling = !enabled && appLock.status.enabled;
  const currentCodeField = appLock.status.enabled ? (
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
        minLength={APP_LOCK_MIN_CODE_LENGTH}
        maxLength={128}
        disabled={pending}
      />
    </div>
  ) : null;
  const timeoutField = (
    <div className="space-y-2">
      <Label htmlFor="app-lock-timeout">
        {t("settings.appLockTimeout")}
      </Label>
      <Select
        value={String(timeout)}
        onValueChange={(value) =>
          setTimeoutMinutes(Number(value) as TimeoutMinutes)
        }
        disabled={pending}
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
  );
  const newCodeField = (
    <div className="space-y-2">
      {appLock.status.enabled ? (
        <HelpTooltip content={t("settings.appLockLeaveCode")}>
          <Label htmlFor="app-lock-new-code">
            {t("settings.appLockNewCode")}
          </Label>
        </HelpTooltip>
      ) : (
        <HelpTooltip content={t("settings.appLockCodeLength")}>
          <Label htmlFor="app-lock-new-code">{t("appLock.code")}</Label>
        </HelpTooltip>
      )}
      <Input
        id="app-lock-new-code"
        type="password"
        autoComplete="new-password"
        value={newCode}
        onChange={(event) => setNewCode(event.target.value)}
        minLength={
          appLock.status.enabled ? undefined : APP_LOCK_MIN_CODE_LENGTH
        }
        maxLength={128}
        disabled={pending}
      />
    </div>
  );
  const repeatCodeField = (
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
  );

  return (
    <Card className="w-full max-w-2xl">
      <CardContent className="p-0">
        <div className="flex min-h-16 items-center justify-between gap-4 p-5">
          <HelpTooltip content={t("settings.appLockHelp")}>
            <Label
              htmlFor="app-lock-enabled"
              className="flex items-center gap-2 text-base text-foreground"
            >
              <LockKeyhole className="h-4 w-4 text-primary" />
              {t("settings.appLock")}
            </Label>
          </HelpTooltip>
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

        {enabled && (
          <div className="border-t p-5">
            <div className="grid gap-4 md:grid-cols-2">
              {appLock.status.enabled ? (
                <>
                  {currentCodeField}
                  {timeoutField}
                  {newCodeField}
                  {repeatCodeField}
                </>
              ) : (
                <>
                  {newCodeField}
                  {repeatCodeField}
                  {timeoutField}
                </>
              )}
            </div>

            {error && (
              <p className="mt-4 text-sm text-destructive">{error}</p>
            )}

            <div className="mt-5 flex justify-end">
              <Button onClick={() => void save()} disabled={pending}>
                {pending && <Loader2 className="h-4 w-4 animate-spin" />}
                {appLock.status.enabled
                  ? t("settings.appLockSave")
                  : t("settings.appLockEnable")}
              </Button>
            </div>
          </div>
        )}

        {isDisabling && (
          <div className="border-t p-5">
            <div className="max-w-sm">{currentCodeField}</div>
            {error && (
              <p className="mt-4 text-sm text-destructive">{error}</p>
            )}
            <div className="mt-5 flex justify-end">
              <Button
                variant="outline"
                onClick={() => void disable()}
                disabled={pending}
              >
                {pending && <Loader2 className="h-4 w-4 animate-spin" />}
                {t("settings.appLockDisable")}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
