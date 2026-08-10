"use client";

import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useT, type TranslationKey } from "@/lib/i18n";

interface AppHelpDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const START_STEPS = [
  ["help.start.account.title", "help.start.account.description"],
  ["help.start.transactions.title", "help.start.transactions.description"],
  ["help.start.types.title", "help.start.types.description"],
  ["help.start.categories.title", "help.start.categories.description"],
] as const satisfies ReadonlyArray<readonly [TranslationKey, TranslationKey]>;

const TIPS = [
  ["help.tip.order.title", "help.tip.order.description"],
  ["help.tip.suggestions.title", "help.tip.suggestions.description"],
  ["help.tip.import.title", "help.tip.import.description"],
  ["help.tip.transfers.title", "help.tip.transfers.description"],
  ["help.tip.currencies.title", "help.tip.currencies.description"],
  ["help.tip.assets.title", "help.tip.assets.description"],
] as const satisfies ReadonlyArray<readonly [TranslationKey, TranslationKey]>;

export function AppHelpDialog({ open, onOpenChange }: AppHelpDialogProps) {
  const { t } = useT();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100vh-2rem)] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t("help.title")}</DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          <section>
            <h3 className="text-sm font-semibold">{t("help.start.title")}</h3>
            <ol className="mt-4 grid gap-x-8 gap-y-5 sm:grid-cols-2">
              {START_STEPS.map(([titleKey, descriptionKey], index) => (
                <li
                  key={titleKey}
                  className="grid grid-cols-[1.75rem_minmax(0,1fr)] gap-3"
                >
                  <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-xs font-semibold text-primary">
                    {index + 1}
                  </span>
                  <div>
                    <h4 className="text-sm font-medium">{t(titleKey)}</h4>
                    <p className="mt-1 text-sm leading-5 text-muted-foreground">
                      {t(descriptionKey)}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <section className="border-t border-border pt-5">
            <h3 className="text-sm font-semibold">{t("help.tips.title")}</h3>
            <dl className="mt-4 grid gap-x-8 gap-y-4 sm:grid-cols-2">
              {TIPS.map(([titleKey, descriptionKey]) => (
                <div key={titleKey}>
                  <dt className="text-sm font-medium">{t(titleKey)}</dt>
                  <dd className="mt-1 text-sm leading-5 text-muted-foreground">
                    {t(descriptionKey)}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">
              {t("common.close")}
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
