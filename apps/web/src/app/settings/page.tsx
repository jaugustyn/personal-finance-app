"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Bot,
  ListChecks,
  Plus,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { api, type PersonalRule } from "@/lib/api";
import { useT, tCategory, tTransactionType } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { Card, CardContent } from "@/components/ui/card";
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
import { AssistantSettingsCard } from "@/components/assistant-settings";
import { useConfirm } from "@/components/confirm-dialog";
import { HelpTooltip } from "@/components/help-tooltip";
import {
  pageTabsListClassName,
  pageTabTriggerClassName,
} from "@/components/page-tabs";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
    <div className="space-y-5">
      <PageHeader title={t("settings.title")} />

      <Tabs defaultValue="security" className="space-y-5">
        <TabsList className={pageTabsListClassName}>
          <TabsTrigger
            value="security"
            className={pageTabTriggerClassName}
          >
            <ShieldCheck className="h-4 w-4" />
            {t("settings.tabSecurity")}
          </TabsTrigger>
          <TabsTrigger
            value="assistant"
            className={pageTabTriggerClassName}
          >
            <Bot className="h-4 w-4" />
            {t("settings.tabAssistant")}
          </TabsTrigger>
          <TabsTrigger
            value="rules"
            className={pageTabTriggerClassName}
          >
            <ListChecks className="h-4 w-4" />
            {t("settings.tabRules")}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="security">
          <AppLockSettings />
        </TabsContent>

        <TabsContent value="assistant">
          <AssistantSettingsCard />
        </TabsContent>

        <TabsContent value="rules" className="space-y-5">
          <Card className="w-full max-w-6xl">
            <CardContent className="p-5">
              <HelpTooltip content={t("settings.rulesHelp")}>
                <h2 className="inline-flex items-center gap-2 text-base font-semibold text-foreground">
                  <ListChecks className="h-4 w-4 text-primary" />
                  {t("settings.addRule")}
                </h2>
              </HelpTooltip>
              <form
                className="mt-5"
                onSubmit={(event) => {
                  event.preventDefault();
                  createRule.mutate();
                }}
              >
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-12">
                  <div className="space-y-2 md:col-span-2 xl:col-span-4">
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
                  <div className="space-y-2 xl:col-span-2">
                    <Label htmlFor="rule-target">
                      {t("settings.ruleTarget")}
                    </Label>
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
                  <div className="space-y-2 xl:col-span-2">
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
                  <div className="space-y-2 xl:col-span-2">
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
                  <div className="space-y-2 xl:col-span-2">
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
                        <SelectItem
                          value="suggest_only"
                          indicatorPosition="right"
                        >
                          {t("settings.modeSuggest")}
                        </SelectItem>
                        <SelectItem
                          value="auto_apply"
                          indicatorPosition="right"
                        >
                          {t("settings.modeAuto")}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="mt-4 flex justify-end">
                  <Button
                    type="submit"
                    disabled={!pattern.trim() || createRule.isPending}
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    {t("settings.addRule")}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold">
                {t("settings.savedRules")}
              </h2>
              <Badge variant="muted">{rulesQuery.data?.length ?? 0}</Badge>
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
          </section>
        </TabsContent>
      </Tabs>
    </div>
  );
}
