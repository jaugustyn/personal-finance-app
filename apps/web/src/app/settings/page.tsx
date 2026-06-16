"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { api, type PersonalRule, type UserProfile } from "@/lib/api";
import { useT, tCategory, tTransactionType } from "@/lib/i18n";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { CategorySelect } from "@/components/category-select";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const PROFILE_KEY = ["profile"] as const;
const RULES_KEY = ["personalRules"] as const;
const TRANSACTION_TYPES = [
  "purchase",
  "own_transfer",
  "person_transfer",
  "salary",
  "income",
  "refund",
  "cash_withdrawal",
  "debt_payment",
  "bank_fee",
  "savings_investment",
  "other",
] as const;

const CURRENCY_OPTIONS = [
  "PLN",
  "EUR",
  "USD",
  "GBP",
  "CHF",
  "NOK",
  "SEK",
  "CZK",
] as const;

export default function SettingsPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const profileQuery = useQuery<UserProfile>({
    queryKey: PROFILE_KEY,
    queryFn: () => api.profile(),
  });
  const rulesQuery = useQuery<PersonalRule[]>({
    queryKey: RULES_KEY,
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
      qc.invalidateQueries({ queryKey: RULES_KEY });
      setPattern("");
      setRuleCategory("");
      setRuleType("");
      setRuleMode("suggest_only");
      toast.success(t("toast.ruleAdded"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const patchRule = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<PersonalRule> }) =>
      api.patchPersonalRule(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: RULES_KEY }),
  });

  const deleteRule = useMutation({
    mutationFn: (id: number) => api.deletePersonalRule(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: RULES_KEY });
      toast.success(t("toast.deleted"));
    },
    onError: () => toast.error(t("toast.error")),
  });
  const ruleColumns: DataTableColumn<PersonalRule>[] = [
    {
      id: "pattern",
      header: t("settings.rulePattern"),
      sortValue: (rule) => rule.pattern,
      cell: (rule) => (
        <>
          <div className="font-medium">{rule.pattern}</div>
          <div className="text-xs text-muted-foreground">
            {rule.pattern_target} · priority {rule.priority}
          </div>
        </>
      ),
    },
    {
      id: "category",
      header: t("transactions.column.category"),
      sortValue: (rule) => rule.category ?? "",
      cell: (rule) =>
        rule.category ? tCategory(t, rule.category) : t("common.unknown"),
    },
    {
      id: "type",
      header: t("transactions.filterType"),
      sortValue: (rule) => rule.transaction_type ?? "",
      cell: (rule) =>
        rule.transaction_type
          ? tTransactionType(t, rule.transaction_type)
          : t("common.unknown"),
    },
    {
      id: "mode",
      header: t("settings.mode"),
      sortValue: (rule) => rule.mode,
      cell: (rule) => (
        <select
          value={rule.mode}
          onChange={(event) =>
            patchRule.mutate({
              id: rule.id,
              patch: {
                mode: event.target.value as "suggest_only" | "auto_apply",
              },
            })
          }
          className="h-8 rounded-md border border-input bg-transparent px-2 text-xs"
        >
          <option value="suggest_only">{t("settings.modeSuggest")}</option>
          <option value="auto_apply">{t("settings.modeAuto")}</option>
        </select>
      ),
    },
    {
      id: "active",
      header: t("settings.active"),
      sortValue: (rule) => (rule.active ? 1 : 0),
      cell: (rule) => (
        <input
          type="checkbox"
          checked={rule.active}
          onChange={(event) =>
            patchRule.mutate({
              id: rule.id,
              patch: { active: event.target.checked },
            })
          }
          className="h-4 w-4"
        />
      ),
    },
    {
      id: "actions",
      header: "",
      headerClassName: "w-16",
      className: "w-16",
      cell: (rule) => (
        <Button
          variant="ghost"
          size="icon"
          onClick={() => deleteRule.mutate(rule.id)}
          aria-label={t("common.delete")}
        >
          <Trash2 className="h-4 w-4 text-destructive" />
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("settings.title")}
        description={t("settings.subtitle")}
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("settings.profile")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {profileQuery.isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t("common.loading")}
            </div>
          ) : profileQuery.isError ? (
            <p className="text-sm text-destructive">{t("common.error")}</p>
          ) : profileQuery.data ? (
            <ProfileForm profile={profileQuery.data} />
          ) : (
            <p className="text-sm text-muted-foreground">{t("common.empty")}</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("settings.rules")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-xs text-muted-foreground">
            {t("settings.rulesHelp")}
          </p>
          <div className="grid gap-2 md:grid-cols-[1.5fr_1fr_1fr_1fr_1fr_auto]">
            <Input
              value={pattern}
              onChange={(event) => setPattern(event.target.value)}
              placeholder={t("settings.rulePattern")}
            />
            <Select
              value={patternTarget}
              onValueChange={(v) =>
                setPatternTarget(v as "merchant" | "title" | "both")
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="merchant">
                  {t("settings.targetMerchant")}
                </SelectItem>
                <SelectItem value="title">
                  {t("settings.targetTitle")}
                </SelectItem>
                <SelectItem value="both">{t("settings.targetBoth")}</SelectItem>
              </SelectContent>
            </Select>
            <CategorySelect
              value={ruleCategory}
              onChange={setRuleCategory}
              allLabel={t("settings.noCategory")}
              ariaLabel={t("transactions.column.category")}
              className="w-full"
            />
            <Select
              value={ruleType || "none"}
              onValueChange={(v) => setRuleType(v === "none" ? "" : v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">{t("settings.noType")}</SelectItem>
                {TRANSACTION_TYPES.map((type) => (
                  <SelectItem key={type} value={type}>
                    {tTransactionType(t, type)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={ruleMode}
              onValueChange={(v) =>
                setRuleMode(v as "suggest_only" | "auto_apply")
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="suggest_only">
                  {t("settings.modeSuggest")}
                </SelectItem>
                <SelectItem value="auto_apply">
                  {t("settings.modeAuto")}
                </SelectItem>
              </SelectContent>
            </Select>
            <Button
              disabled={!pattern.trim() || createRule.isPending}
              onClick={() => createRule.mutate()}
            >
              <Plus className="mr-2 h-4 w-4" />
              {t("common.add")}
            </Button>
          </div>
          <DataTable
            columns={ruleColumns}
            data={rulesQuery.data ?? []}
            rowKey={(rule) => rule.id}
            isLoading={rulesQuery.isLoading}
            initialSort={{ id: "pattern", dir: "asc" }}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function ProfileForm({ profile }: { profile: UserProfile }) {
  const { t } = useT();
  const qc = useQueryClient();
  const [baseCurrency, setBaseCurrency] = useState(profile.base_currency);
  const [salaryDay, setSalaryDay] = useState(
    profile.salary_day ? String(profile.salary_day) : "",
  );
  const [monthlyGoal] = useState(
    profile.monthly_savings_goal !== null
      ? String(profile.monthly_savings_goal)
      : "",
  );
  const [limits] = useState<Record<string, string>>(
    Object.fromEntries(
      Object.entries(profile.category_limits ?? {}).map(([key, value]) => [
        key,
        String(value),
      ]),
    ),
  );

  const saveProfile = useMutation({
    mutationFn: () =>
      api.patchProfile({
        base_currency: baseCurrency.trim().toUpperCase(),
        salary_day: salaryDay ? Number(salaryDay) : null,
        monthly_savings_goal: monthlyGoal ? Number(monthlyGoal) : null,
        category_limits: Object.fromEntries(
          Object.entries(limits)
            .filter(([, value]) => value.trim() !== "")
            .map(([key, value]) => [key, Number(value)]),
        ),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PROFILE_KEY });
      toast.success(t("toast.saved"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  return (
    <>
      <div className="grid gap-3 md:grid-cols-3">
        <label className="space-y-1 text-sm">
          <span>{t("settings.baseCurrency")}</span>
          <Select value={baseCurrency} onValueChange={setBaseCurrency}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CURRENCY_OPTIONS.map((code) => (
                <SelectItem key={code} value={code}>
                  {code}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <span className="block text-xs text-muted-foreground">
            {t("settings.baseCurrencyHelp")}
          </span>
        </label>
        <label className="space-y-1 text-sm">
          <span>{t("settings.salaryDay")}</span>
          <Input
            type="number"
            min={1}
            max={31}
            value={salaryDay}
            onChange={(event) => setSalaryDay(event.target.value)}
            placeholder={t("settings.salaryDayPlaceholder")}
          />
          <span className="block text-xs text-muted-foreground">
            {t("settings.salaryDayHelp")}
          </span>
        </label>
        <label className="space-y-1 text-sm">
          <span>{t("settings.monthlyGoal")}</span>
          <Input
            type="number"
            min={0}
            value={monthlyGoal}
            readOnly
            disabled
            className="cursor-not-allowed opacity-70"
          />
          <span className="block text-xs text-muted-foreground">
            {t("settings.monthlyGoalReadonly")}
          </span>
        </label>
      </div>
      <Button
        className="min-w-[120px]"
        onClick={() => saveProfile.mutate()}
        disabled={saveProfile.isPending}
      >
        {saveProfile.isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          t("common.save")
        )}
      </Button>
    </>
  );
}
