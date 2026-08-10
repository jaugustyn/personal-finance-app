"use client";

import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Bot,
  BookOpenText,
  ListChecks,
  Plus,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { api, type PersonalRule } from "@/lib/api";
import { useT, tCategory, tTransactionType } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { CategorySelect } from "@/components/category-select";
import { TransactionTypeFilterSelect } from "@/components/transaction-type-filter-select";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { AppLockSettings } from "@/components/app-lock-settings";
import { AppHelpDialog } from "@/components/app-help-dialog";
import { AssistantSettings } from "@/components/assistant-settings";
import { useConfirm } from "@/components/confirm-dialog";
import { HelpTooltip } from "@/components/help-tooltip";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { queryKeys } from "@/lib/query-keys";

export default function SettingsPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const rulesQuery = useQuery<PersonalRule[]>({
    queryKey: queryKeys.profile.rules,
    queryFn: () => api.personalRules(),
  });

  const [pattern, setPattern] = useState("");
  const [patternTarget, setPatternTarget] = useState<
    "merchant" | "title" | "both"
  >("merchant");
  const [ruleCategory, setRuleCategory] = useState("");
  const [ruleType, setRuleType] = useState("");
  const [ruleMode, setRuleMode] = useState<"suggest_only" | "auto_apply">(
    "suggest_only",
  );
  const [ruleDialogOpen, setRuleDialogOpen] = useState(false);
  const [helpDialogOpen, setHelpDialogOpen] = useState(false);

  const createRule = useMutation({
    mutationFn: () =>
      api.createPersonalRule({
        pattern: pattern.trim(),
        pattern_target: patternTarget,
        category: ruleCategory || null,
        transaction_type: ruleType || null,
        is_transfer: null,
        mode: ruleMode,
        confidence: ruleMode === "auto_apply" ? 1.0 : 0.95,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.profile.all });
      setPattern("");
      setRuleCategory("");
      setRuleType("");
      setRuleMode("suggest_only");
      setRuleDialogOpen(false);
      toast.success(t("toast.ruleAdded"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const patchRule = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<PersonalRule> }) =>
      api.patchPersonalRule(id, patch),
    onSuccess: () =>
      void qc.invalidateQueries({ queryKey: queryKeys.profile.all }),
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const deleteRule = useMutation({
    mutationFn: (id: number) => api.deletePersonalRule(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.profile.all });
      toast.success(t("toast.deleted"));
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const confirmRuleDeletion = async (rule: PersonalRule) => {
    const accepted = await confirm({
      title: t("settings.deleteRuleTitle"),
      description: t("settings.deleteRuleDescription"),
      details: [
        {
          label: t("settings.rulePatternLabel"),
          value: rule.pattern,
        },
      ],
      confirmLabel: t("settings.deleteRule"),
      destructive: true,
    });
    if (accepted) deleteRule.mutate(rule.id);
  };

  const targetLabel = (target: PersonalRule["pattern_target"]) => {
    if (target === "merchant") return t("settings.targetMerchant");
    if (target === "title") return t("settings.targetTitle");
    return t("settings.targetBoth");
  };

  const ruleColumns: DataTableColumn<PersonalRule>[] = [
    {
      id: "pattern",
      header: t("settings.rulePattern"),
      sortValue: (rule) => rule.pattern,
      cell: (rule) => (
        <>
          <div className="font-medium">{rule.pattern}</div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            {targetLabel(rule.pattern_target)}
          </div>
        </>
      ),
    },
    {
      id: "category",
      header: t("transactions.column.category"),
      sortValue: (rule) => rule.category ?? "",
      cell: (rule) =>
        rule.category ? (
          tCategory(t, rule.category)
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      id: "type",
      header: t("transactions.filterType"),
      sortValue: (rule) => rule.transaction_type ?? "",
      cell: (rule) =>
        rule.transaction_type ? (
          tTransactionType(t, rule.transaction_type)
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      id: "mode",
      header: t("settings.mode"),
      sortValue: (rule) => rule.mode,
      cell: (rule) => (
        <Select
          value={rule.mode}
          onValueChange={(value) =>
            patchRule.mutate({
              id: rule.id,
              patch: {
                mode: value as "suggest_only" | "auto_apply",
              },
            })
          }
          disabled={patchRule.isPending}
        >
          <SelectTrigger className="h-8 min-w-[11rem] text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="suggest_only" indicatorPosition="right">
              {t("settings.modeSuggest")}
            </SelectItem>
            <SelectItem value="auto_apply" indicatorPosition="right">
              {t("settings.modeAuto")}
            </SelectItem>
          </SelectContent>
        </Select>
      ),
    },
    {
      id: "active",
      header: t("settings.active"),
      align: "center",
      headerClassName: "w-24",
      className: "w-24",
      sortValue: (rule) => (rule.active ? 1 : 0),
      cell: (rule) => (
        <Switch
          checked={rule.active}
          onCheckedChange={(checked) =>
            patchRule.mutate({
              id: rule.id,
              patch: { active: checked },
            })
          }
          disabled={patchRule.isPending}
          aria-label={`${t("settings.active")}: ${rule.pattern}`}
        />
      ),
    },
    {
      id: "actions",
      header: "",
      align: "center",
      headerClassName: "w-14",
      className: "w-14",
      cell: (rule) => (
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-muted-foreground hover:text-destructive"
          disabled={deleteRule.isPending}
          onClick={() => void confirmRuleDeletion(rule)}
          aria-label={`${t("settings.deleteRule")}: ${rule.pattern}`}
          title={t("settings.deleteRule")}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-8">
      <PageHeader title={t("settings.title")} />

      <div className="w-full divide-y divide-border/70 overflow-hidden rounded-xl border border-border/70 bg-card">
        <SettingsSection
          title={t("settings.tabSecurity")}
          icon={<ShieldCheck className="h-5 w-5" />}
        >
          <AppLockSettings />
        </SettingsSection>

        <SettingsSection
          title={t("settings.tabAssistant")}
          icon={<Bot className="h-5 w-5" />}
        >
          <AssistantSettings />
        </SettingsSection>

        <SettingsSection
          title={t("settings.tabRules")}
          help={t("settings.rulesHelp")}
          icon={<ListChecks className="h-5 w-5" />}
        >
          <div className="max-w-6xl space-y-3">
            <div className="flex min-h-9 flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold">
                  {t("settings.savedRules")}
                </h3>
                <Badge variant="muted">{rulesQuery.data?.length ?? 0}</Badge>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setRuleDialogOpen(true)}
              >
                <Plus className="h-4 w-4" />
                {t("settings.addRule")}
              </Button>
            </div>
            {rulesQuery.isError ? (
              <ErrorState
                description={t("settings.rulesLoadError")}
                onRetry={() => rulesQuery.refetch()}
              />
            ) : (
              <DataTable
                columns={ruleColumns}
                data={rulesQuery.data ?? []}
                rowKey={(rule) => rule.id}
                isLoading={rulesQuery.isLoading}
                initialSort={{ id: "pattern", dir: "asc" }}
                pagination={{ mode: "client" }}
                emptyTitle={t("settings.rulesEmpty")}
                emptyDescription={t("settings.rulesEmptyHelp")}
              />
            )}
          </div>
        </SettingsSection>

        <SettingsSection
          title={t("settings.tabHelp")}
          icon={<BookOpenText className="h-5 w-5" />}
        >
          <Button
            variant="outline"
            size="sm"
            onClick={() => setHelpDialogOpen(true)}
          >
            {t("help.open")}
          </Button>
        </SettingsSection>
      </div>

      <Dialog open={ruleDialogOpen} onOpenChange={setRuleDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t("settings.addRule")}</DialogTitle>
          </DialogHeader>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              createRule.mutate();
            }}
          >
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="rule-pattern">
                  {t("settings.rulePatternLabel")}
                </Label>
                <Input
                  id="rule-pattern"
                  value={pattern}
                  onChange={(event) => setPattern(event.target.value)}
                  placeholder={t("settings.rulePattern")}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="rule-target">{t("settings.ruleTarget")}</Label>
                <Select
                  value={patternTarget}
                  onValueChange={(v) =>
                    setPatternTarget(v as "merchant" | "title" | "both")
                  }
                >
                  <SelectTrigger id="rule-target">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="merchant" indicatorPosition="right">
                      {t("settings.targetMerchant")}
                    </SelectItem>
                    <SelectItem value="title" indicatorPosition="right">
                      {t("settings.targetTitle")}
                    </SelectItem>
                    <SelectItem value="both" indicatorPosition="right">
                      {t("settings.targetBoth")}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="rule-category">
                  {t("transactions.column.category")}
                </Label>
                <CategorySelect
                  id="rule-category"
                  value={ruleCategory}
                  onChange={setRuleCategory}
                  allLabel={t("settings.noCategory")}
                  ariaLabel={t("transactions.column.category")}
                  className="w-full"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="rule-transaction-type">
                  {t("transactions.filterType")}
                </Label>
                <TransactionTypeFilterSelect
                  id="rule-transaction-type"
                  value={ruleType}
                  onChange={setRuleType}
                  allLabel={t("settings.noType")}
                  ariaLabel={t("transactions.filterType")}
                  className="w-full"
                />
              </div>
              <div className="space-y-2">
                <HelpTooltip content={t("settings.modeHelp")}>
                  <Label htmlFor="rule-mode">{t("settings.mode")}</Label>
                </HelpTooltip>
                <Select
                  value={ruleMode}
                  onValueChange={(v) =>
                    setRuleMode(v as "suggest_only" | "auto_apply")
                  }
                >
                  <SelectTrigger id="rule-mode">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="suggest_only" indicatorPosition="right">
                      {t("settings.modeSuggest")}
                    </SelectItem>
                    <SelectItem value="auto_apply" indicatorPosition="right">
                      {t("settings.modeAuto")}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter className="mt-5">
              <Button
                type="button"
                variant="outline"
                onClick={() => setRuleDialogOpen(false)}
              >
                {t("common.cancel")}
              </Button>
              <Button
                type="submit"
                disabled={!pattern.trim() || createRule.isPending}
              >
                <Plus className="h-4 w-4" />
                {t("settings.addRule")}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AppHelpDialog open={helpDialogOpen} onOpenChange={setHelpDialogOpen} />
    </div>
  );
}

function SettingsSection({
  title,
  icon,
  help,
  children,
}: {
  title: string;
  icon: ReactNode;
  help?: string;
  children: ReactNode;
}) {
  const heading = (
    <h2 className="inline-flex items-center gap-2.5 text-sm font-medium leading-5 text-muted-foreground">
      <span className="flex h-5 w-5 shrink-0 items-center justify-center text-primary">
        {icon}
      </span>
      {title}
    </h2>
  );

  return (
    <section className="px-6 py-8 sm:px-7">
      <div>
        {help ? <HelpTooltip content={help}>{heading}</HelpTooltip> : heading}
      </div>
      <div className="mt-6 min-w-0">{children}</div>
    </section>
  );
}
