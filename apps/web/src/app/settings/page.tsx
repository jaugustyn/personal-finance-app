"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { api, type CategoryDef, type PersonalRule, type UserProfile } from "@/lib/api";
import { useCategories } from "@/hooks/use-categories";
import { useT, tCategory, tTransactionType } from "@/lib/i18n";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const PROFILE_KEY = ["profile"] as const;
const RULES_KEY = ["personalRules"] as const;
const TRANSACTION_TYPES = [
  "purchase",
  "own_transfer",
  "person_transfer",
  "salary",
  "refund",
  "cash_withdrawal",
  "bank_fee",
  "savings_investment",
  "other",
] as const;

export default function SettingsPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const { data: categories = [] } = useCategories();
  const profileQuery = useQuery<UserProfile>({
    queryKey: PROFILE_KEY,
    queryFn: () => api.profile(),
  });
  const rulesQuery = useQuery<PersonalRule[]>({
    queryKey: RULES_KEY,
    queryFn: () => api.personalRules(),
  });

  const [pattern, setPattern] = useState("");
  const [patternTarget, setPatternTarget] = useState<"merchant" | "title" | "both">(
    "merchant",
  );
  const [ruleCategory, setRuleCategory] = useState("");
  const [ruleType, setRuleType] = useState("");
  const [ruleTransfer, setRuleTransfer] = useState(false);
  const [ruleMode, setRuleMode] = useState<"suggest_only" | "auto_apply">(
    "suggest_only",
  );

  const sortedCategories = useMemo(
    () =>
      [...categories].sort((a, b) => {
        if (a.is_system !== b.is_system) return a.is_system ? -1 : 1;
        return a.name.localeCompare(b.name);
      }),
    [categories],
  );

  const createRule = useMutation({
    mutationFn: () =>
      api.createPersonalRule({
        pattern: pattern.trim(),
        pattern_target: patternTarget,
        category: ruleCategory || null,
        transaction_type: ruleType || null,
        is_transfer: ruleTransfer || null,
        mode: ruleMode,
        confidence: ruleMode === "auto_apply" ? 1.0 : 0.95,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: RULES_KEY });
      setPattern("");
      setRuleCategory("");
      setRuleType("");
      setRuleTransfer(false);
      setRuleMode("suggest_only");
    },
  });

  const patchRule = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<PersonalRule> }) =>
      api.patchPersonalRule(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: RULES_KEY }),
  });

  const deleteRule = useMutation({
    mutationFn: (id: number) => api.deletePersonalRule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: RULES_KEY }),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("settings.title")}
        </h1>
        <p className="text-sm text-muted-foreground">
          {t("settings.subtitle")}
        </p>
      </div>

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
            <ProfileForm
              profile={profileQuery.data}
              categories={sortedCategories}
            />
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
          <div className="grid gap-2 md:grid-cols-[1.5fr_1fr_1fr_1fr_1fr_auto]">
            <Input
              value={pattern}
              onChange={(event) => setPattern(event.target.value)}
              placeholder={t("settings.rulePattern")}
            />
            <select
              value={patternTarget}
              onChange={(event) =>
                setPatternTarget(event.target.value as "merchant" | "title" | "both")
              }
              className="h-9 rounded-md border border-input bg-transparent px-2 text-sm"
            >
              <option value="merchant">{t("settings.targetMerchant")}</option>
              <option value="title">{t("settings.targetTitle")}</option>
              <option value="both">{t("settings.targetBoth")}</option>
            </select>
            <select
              value={ruleCategory}
              onChange={(event) => setRuleCategory(event.target.value)}
              className="h-9 rounded-md border border-input bg-transparent px-2 text-sm"
            >
              <option value="">{t("settings.noCategory")}</option>
              {sortedCategories.map((category) => (
                <option key={category.id} value={category.name}>
                  {category.is_system ? tCategory(t, category.name) : category.name}
                </option>
              ))}
            </select>
            <select
              value={ruleType}
              onChange={(event) => setRuleType(event.target.value)}
              className="h-9 rounded-md border border-input bg-transparent px-2 text-sm"
            >
              <option value="">{t("settings.noType")}</option>
              {TRANSACTION_TYPES.map((type) => (
                <option key={type} value={type}>
                  {tTransactionType(t, type)}
                </option>
              ))}
            </select>
            <select
              value={ruleMode}
              onChange={(event) =>
                setRuleMode(event.target.value as "suggest_only" | "auto_apply")
              }
              className="h-9 rounded-md border border-input bg-transparent px-2 text-sm"
            >
              <option value="suggest_only">{t("settings.modeSuggest")}</option>
              <option value="auto_apply">{t("settings.modeAuto")}</option>
            </select>
            <Button
              disabled={!pattern.trim() || createRule.isPending}
              onClick={() => createRule.mutate()}
            >
              <Plus className="mr-2 h-4 w-4" />
              {t("common.add")}
            </Button>
          </div>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={ruleTransfer}
              onChange={(event) => setRuleTransfer(event.target.checked)}
              className="h-4 w-4"
            />
            {t("settings.markTransfer")}
          </label>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("settings.rulePattern")}</TableHead>
                <TableHead>{t("transactions.column.category")}</TableHead>
                <TableHead>{t("transactions.filterType")}</TableHead>
                <TableHead>{t("settings.mode")}</TableHead>
                <TableHead>{t("settings.active")}</TableHead>
                <TableHead className="w-16" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {(rulesQuery.data ?? []).map((rule) => (
                <TableRow key={rule.id}>
                  <TableCell>
                    <div className="font-medium">{rule.pattern}</div>
                    <div className="text-xs text-muted-foreground">
                      {rule.pattern_target} · priority {rule.priority}
                    </div>
                  </TableCell>
                  <TableCell>
                    {rule.category ? tCategory(t, rule.category) : t("common.unknown")}
                  </TableCell>
                  <TableCell>
                    {rule.transaction_type
                      ? tTransactionType(t, rule.transaction_type)
                      : t("common.unknown")}
                  </TableCell>
                  <TableCell>
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
                  </TableCell>
                  <TableCell>
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
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => deleteRule.mutate(rule.id)}
                      aria-label={t("common.delete")}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function ProfileForm({
  profile,
  categories,
}: {
  profile: UserProfile;
  categories: CategoryDef[];
}) {
  const { t } = useT();
  const qc = useQueryClient();
  const [baseCurrency, setBaseCurrency] = useState(profile.base_currency);
  const [salaryDay, setSalaryDay] = useState(
    profile.salary_day ? String(profile.salary_day) : "",
  );
  const [monthlyGoal, setMonthlyGoal] = useState(
    profile.monthly_savings_goal !== null
      ? String(profile.monthly_savings_goal)
      : "",
  );
  const [limits, setLimits] = useState<Record<string, string>>(
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
    onSuccess: () => qc.invalidateQueries({ queryKey: PROFILE_KEY }),
  });

  return (
    <>
      <div className="grid gap-3 md:grid-cols-3">
        <label className="space-y-1 text-sm">
          <span>{t("settings.baseCurrency")}</span>
          <Input
            value={baseCurrency}
            onChange={(event) => setBaseCurrency(event.target.value)}
            maxLength={3}
          />
        </label>
        <label className="space-y-1 text-sm">
          <span>{t("settings.salaryDay")}</span>
          <Input
            type="number"
            min={1}
            max={31}
            value={salaryDay}
            onChange={(event) => setSalaryDay(event.target.value)}
          />
        </label>
        <label className="space-y-1 text-sm">
          <span>{t("settings.monthlyGoal")}</span>
          <Input
            type="number"
            min={0}
            value={monthlyGoal}
            onChange={(event) => setMonthlyGoal(event.target.value)}
          />
        </label>
      </div>
      <div className="grid gap-3 md:grid-cols-4">
        {categories
          .filter((category) => category.is_system)
          .map((category) => (
            <label key={category.id} className="space-y-1 text-sm">
              <span>{tCategory(t, category.name)}</span>
              <Input
                type="number"
                min={0}
                value={limits[category.name] ?? ""}
                onChange={(event) =>
                  setLimits((prev) => ({
                    ...prev,
                    [category.name]: event.target.value,
                  }))
                }
                placeholder="0"
              />
            </label>
          ))}
      </div>
      <Button onClick={() => saveProfile.mutate()} disabled={saveProfile.isPending}>
        {saveProfile.isPending && (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        )}
        {t("common.save")}
      </Button>
    </>
  );
}
