"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";

interface ConfirmOptions {
  title: string;
  description?: string;
  details?: ReadonlyArray<{ label: string; value: string }>;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
}

type ConfirmFn = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = React.createContext<ConfirmFn | null>(null);

/**
 * Imperative confirmation dialog. Replaces window.confirm with an accessible,
 * theme-aware modal. Usage: `const confirm = useConfirm(); if (await confirm({...}))`.
 */
export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const { t } = useT();
  const [options, setOptions] = React.useState<ConfirmOptions | null>(null);
  const resolverRef = React.useRef<((value: boolean) => void) | null>(null);

  const confirm = React.useCallback<ConfirmFn>((opts) => {
    setOptions(opts);
    return new Promise<boolean>((resolve) => {
      resolverRef.current = resolve;
    });
  }, []);

  const close = (result: boolean) => {
    resolverRef.current?.(result);
    resolverRef.current = null;
    setOptions(null);
  };

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Dialog
        open={options !== null}
        onOpenChange={(open) => !open && close(false)}
      >
        <DialogContent
          className={options?.details?.length ? "max-w-xl" : "max-w-md"}
        >
          {options && (
            <>
              <DialogHeader>
                <DialogTitle>{options.title}</DialogTitle>
                {options.description && !options.details?.length && (
                  <DialogDescription>{options.description}</DialogDescription>
                )}
              </DialogHeader>
              {options.details?.length ? (
                <dl className="space-y-3 text-sm">
                  {options.details.map((detail) => (
                    <div
                      key={detail.label}
                      className="grid gap-1 sm:grid-cols-[7rem_minmax(0,1fr)] sm:gap-4"
                    >
                      <dt className="text-muted-foreground">{detail.label}</dt>
                      <dd className="min-w-0 break-words font-medium text-foreground">
                        {detail.value}
                      </dd>
                    </div>
                  ))}
                </dl>
              ) : null}
              {options.description && options.details?.length ? (
                <DialogDescription>
                  {options.description}
                </DialogDescription>
              ) : null}
              <DialogFooter>
                <Button variant="outline" onClick={() => close(false)}>
                  {options.cancelLabel ?? t("common.cancel")}
                </Button>
                <Button
                  variant={options.destructive ? "destructive" : "default"}
                  onClick={() => close(true)}
                >
                  {options.confirmLabel ?? t("common.confirm")}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const ctx = React.useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm must be used within ConfirmProvider");
  return ctx;
}
