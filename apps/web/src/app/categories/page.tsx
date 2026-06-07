"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Trash2, Plus, Loader2, AlertCircle, Check, X } from "lucide-react";
import { api, type CategoryDef } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/page-header";
import { useConfirm } from "@/components/confirm-dialog";
import { useT, tCategory } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { CATEGORIES_QUERY_KEY } from "@/hooks/use-categories";

interface CategoryGroup {
  parent: CategoryDef;
}

export default function CategoriesPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { data: cats = [], isLoading } = useQuery<CategoryDef[]>({
    queryKey: CATEGORIES_QUERY_KEY,
    queryFn: () => api.listCategories(),
  });

  const [newName, setNewName] = useState("");
  const [newColor, setNewColor] = useState("#888888");
  const [error, setError] = useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: (payload: {
      name: string;
      color: string;
      parent: string | null;
    }) => api.createCategory(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY });
      setNewName("");
      setError(null);
      toast.success(t("toast.categoryAdded"));
    },
    onError: (err: Error) => {
      setError(
        err.message.includes("409") ? t("categories.duplicate") : err.message,
      );
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteCategory(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY });
      toast.success(t("toast.deleted"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const patchMut = useMutation({
    mutationFn: ({ id, color }: { id: number; color: string }) =>
      api.patchCategoryDef(id, { color }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY });
      toast.success(t("toast.saved"));
    },
    onError: () => toast.error(t("toast.error")),
  });

  const onDelete = async (cat: CategoryDef) => {
    const ok = await confirm({
      title: t("categories.deleteConfirm", { name: tCategory(t, cat.name) }),
      destructive: true,
    });
    if (ok) deleteMut.mutate(cat.id);
  };

  const submit = () => {
    const name = newName.trim();
    if (!name) return;
    createMut.mutate({
      name,
      color: newColor,
      parent: null,
    });
  };

  // Subcategories remain in the backend catalog but are hidden in this screen
  // until there is a concrete review workflow for them.
  const groups = useMemo(() => {
    return cats
      .filter((c) => !c.parent)
      .sort((a, b) => {
        if (a.is_system !== b.is_system) return a.is_system ? -1 : 1;
        return a.name.localeCompare(b.name);
      })
      .map((parent) => ({ parent }));
  }, [cats]);

  return (
    <div className="space-y-6">
      <PageHeader title={t("categories.title")} />

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{t("categories.addNew")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-2">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">
                {t("categories.name")}
              </label>
              <Input
                value={newName}
                onChange={(e) => {
                  setNewName(e.target.value);
                  setError(null);
                }}
                placeholder={t("categories.name")}
                className="w-48"
                onKeyDown={(e) => {
                  if (e.key === "Enter") submit();
                }}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">
                {t("categories.color")}
              </label>
              <div className="flex items-center gap-2">
                <label
                  className="relative inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-md ring-1 ring-border"
                  style={{ backgroundColor: newColor }}
                  title={t("categories.color")}
                >
                  <input
                    type="color"
                    value={newColor}
                    onChange={(e) => setNewColor(e.target.value)}
                    className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                    aria-label={t("categories.color")}
                  />
                </label>
                <Input
                  value={newColor}
                  onChange={(e) => {
                    let v = e.target.value.trim();
                    if (v && !v.startsWith("#")) v = `#${v}`;
                    setNewColor(v);
                  }}
                  placeholder="#3b82f6"
                  className="w-28 font-mono"
                  spellCheck={false}
                />
              </div>
            </div>
            <Button
              onClick={submit}
              disabled={!newName.trim() || createMut.isPending}
            >
              {createMut.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              {t("common.add")}
            </Button>
            {error && (
              <span className="flex items-center gap-1 text-sm text-destructive">
                <AlertCircle className="h-4 w-4" />
                {error}
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> {t("common.loading")}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {groups.map((group) => (
          <CategoryGroupCard
            key={group.parent.id}
            group={group}
            onDelete={onDelete}
            onColorChange={(id, color) => patchMut.mutate({ id, color })}
            colorPending={patchMut.isPending}
          />
        ))}
      </div>
    </div>
  );
}

function ColorSwatch({
  color,
  onChange,
  ariaLabel,
  subtle = false,
}: {
  color: string | null;
  onChange: (color: string) => void;
  ariaLabel: string;
  subtle?: boolean;
}) {
  return (
    <label
      className={cn(
        "relative inline-flex cursor-pointer items-center justify-center rounded-full ring-1 ring-border",
        subtle ? "h-3.5 w-3.5 opacity-60" : "h-5 w-5",
      )}
      style={{ backgroundColor: color ?? "hsl(var(--muted-foreground))" }}
      title={ariaLabel}
    >
      <input
        type="color"
        value={color ?? "#888888"}
        onChange={(e) => onChange(e.target.value)}
        className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
        aria-label={ariaLabel}
      />
    </label>
  );
}

function CategoryGroupCard({
  group,
  onDelete,
  onColorChange,
  colorPending,
}: {
  group: CategoryGroup;
  onDelete: (cat: CategoryDef) => void;
  onColorChange: (id: number, color: string) => void;
  colorPending: boolean;
}) {
  const { t } = useT();
  const { parent } = group;
  const savedColor = parent.color ?? "#888888";
  const [draftColor, setDraftColor] = useState(savedColor);
  const hasDraftColor = draftColor.toLowerCase() !== savedColor.toLowerCase();

  useEffect(() => {
    setDraftColor(savedColor);
  }, [savedColor]);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <ColorSwatch
              color={draftColor}
              onChange={setDraftColor}
              ariaLabel={t("categories.color")}
            />
            {hasDraftColor ? (
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  disabled={colorPending}
                  onClick={() => onColorChange(parent.id, draftColor)}
                  aria-label={t("common.save")}
                >
                  {colorPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  disabled={colorPending}
                  onClick={() => setDraftColor(savedColor)}
                  aria-label={t("common.cancel")}
                >
                  <X className="h-3.5 w-3.5 text-muted-foreground" />
                </Button>
              </div>
            ) : null}
            <CardTitle className="text-sm">
              {tCategory(t, parent.name)}
            </CardTitle>
            {parent.is_system ? (
              <Badge variant="outline" className="text-[10px]">
                system
              </Badge>
            ) : (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => onDelete(parent)}
                aria-label={t("common.delete")}
              >
                <Trash2 className="h-3.5 w-3.5 text-destructive" />
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <span className="text-xs tabular-nums text-muted-foreground">
          {t("categories.usage")}: {parent.usage_count}
        </span>
      </CardContent>
    </Card>
  );
}
