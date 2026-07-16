"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Check,
  Loader2,
  MoreHorizontal,
  Palette,
  Plus,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/page-header";
import { useConfirm } from "@/components/confirm-dialog";
import { ErrorState } from "@/components/error-state";
import { CategoryAccent } from "@/components/category-accent";
import { CATEGORIES_QUERY_KEY } from "@/hooks/use-categories";
import { api, isApiError, type CategoryDef } from "@/lib/api";
import {
  getReadableForeground,
} from "@/lib/category-colors";
import { useT, tCategory } from "@/lib/i18n";
import { showErrorToast } from "@/lib/toasts";
import { transactionsHref } from "@/lib/transaction-links";

const CATEGORY_COLORS = [
  "#3b82f6",
  "#8b5cf6",
  "#ec4899",
  "#ef4444",
  "#f59e0b",
  "#10b981",
  "#06b6d4",
  "#64748b",
] as const;

const DEFAULT_CATEGORY_COLOR = CATEGORY_COLORS[0];

export default function CategoriesPage() {
  const { t, locale } = useT();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const {
    data: categories = [],
    isLoading,
    isError,
    refetch,
  } = useQuery<CategoryDef[]>({
    queryKey: CATEGORIES_QUERY_KEY,
    queryFn: () => api.listCategories(),
  });

  const [addOpen, setAddOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newColor, setNewColor] = useState<string>(DEFAULT_CATEGORY_COLOR);
  const [error, setError] = useState<string | null>(null);
  const [colorTarget, setColorTarget] = useState<CategoryDef | null>(null);
  const [draftColor, setDraftColor] = useState<string>(DEFAULT_CATEGORY_COLOR);

  const createMut = useMutation({
    mutationFn: (payload: {
      name: string;
      color: string;
      parent: string | null;
    }) => api.createCategory(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY });
      setAddOpen(false);
      setNewName("");
      setNewColor(DEFAULT_CATEGORY_COLOR);
      setError(null);
      toast.success(t("toast.categoryAdded"));
    },
    onError: (err: Error) => {
      setError(
        isApiError(err) && err.status === 409
          ? t("categories.duplicate")
          : err.message,
      );
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteCategory(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY });
      toast.success(t("toast.deleted"));
    },
    onError: (err) => {
      if (isApiError(err) && err.code === "category_in_use") {
        toast.error(t("categories.deleteBlocked"));
        return;
      }
      showErrorToast(err, t("toast.error"));
    },
  });

  const patchMut = useMutation({
    mutationFn: ({ id, color }: { id: number; color: string }) =>
      api.patchCategoryDef(id, { color }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY });
      setColorTarget(null);
      toast.success(t("toast.saved"));
    },
    onError: (err) => showErrorToast(err, t("toast.error")),
  });

  const normalizedName = newName.trim().toLocaleLowerCase(locale);
  const duplicateName =
    Boolean(normalizedName) &&
    categories.some((category) => {
      const storedName = category.name.toLocaleLowerCase(locale);
      const displayName = tCategory(t, category.name).toLocaleLowerCase(locale);
      return normalizedName === storedName || normalizedName === displayName;
    });

  const parentCategories = useMemo(
    () =>
      categories
        .filter((category) => !category.parent)
        .sort((left, right) =>
          tCategory(t, left.name).localeCompare(tCategory(t, right.name), locale),
        ),
    [categories, locale, t],
  );
  const systemCategories = parentCategories.filter(
    (category) => category.is_system,
  );
  const customCategories = parentCategories.filter(
    (category) => !category.is_system,
  );

  const submit = () => {
    const name = newName.trim();
    if (!name || duplicateName) return;
    createMut.mutate({ name, color: newColor, parent: null });
  };

  const onDelete = async (category: CategoryDef) => {
    if (category.usage_count > 0) {
      toast.error(t("categories.deleteBlocked"));
      return;
    }
    const ok = await confirm({
      title: t("categories.deleteConfirm", {
        name: tCategory(t, category.name),
      }),
      destructive: true,
    });
    if (ok) deleteMut.mutate(category.id);
  };

  const openColorEditor = (category: CategoryDef) => {
    setColorTarget(category);
    setDraftColor(category.color ?? DEFAULT_CATEGORY_COLOR);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("categories.title")}
        description={t("categories.subtitle")}
      />

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> {t("common.loading")}
        </div>
      ) : isError ? (
        <ErrorState
          description={t("categories.loadError")}
          onRetry={() => void refetch()}
        />
      ) : (
        <div className="grid items-start gap-6 lg:grid-cols-2">
          <CategorySection
            title={t("categories.systemSection")}
            categories={systemCategories}
            onColorChange={openColorEditor}
            onDelete={onDelete}
          />
          <CategorySection
            title={t("categories.customSection")}
            categories={customCategories}
            emptyText={t("categories.noCustom")}
            onAdd={() => setAddOpen(true)}
            onColorChange={openColorEditor}
            onDelete={onDelete}
          />
        </div>
      )}

      <Dialog
        open={addOpen}
        onOpenChange={(open) => {
          if (createMut.isPending) return;
          setAddOpen(open);
          if (!open) setError(null);
        }}
      >
        <DialogContent className="max-w-md">
          <form
            className="space-y-5"
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            <DialogHeader>
              <DialogTitle>{t("categories.addNew")}</DialogTitle>
              <DialogDescription>
                {t("categories.addDescription")}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-2">
              <label htmlFor="category-name" className="text-sm font-medium">
                {t("categories.name")}
              </label>
              <Input
                id="category-name"
                value={newName}
                onChange={(event) => {
                  setNewName(event.target.value);
                  setError(null);
                }}
                placeholder={t("categories.namePlaceholder")}
                autoFocus
              />
              {duplicateName ? (
                <p className="flex items-center gap-1.5 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4" />
                  {t("categories.duplicate")}
                </p>
              ) : null}
            </div>

            <ColorField value={newColor} onChange={setNewColor} />

            <div className="space-y-2">
              <span className="text-sm font-medium">{t("categories.preview")}</span>
              <div className="rounded-lg border bg-muted/20 px-4 py-3">
                <CategoryName
                  name={newName.trim() || t("categories.previewPlaceholder")}
                  color={newColor}
                  translate={false}
                />
              </div>
            </div>

            {error && !duplicateName ? (
              <p className="flex items-center gap-1.5 text-sm text-destructive">
                <AlertCircle className="h-4 w-4" />
                {error}
              </p>
            ) : null}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setAddOpen(false)}
                disabled={createMut.isPending}
              >
                {t("common.cancel")}
              </Button>
              <Button
                type="submit"
                disabled={!newName.trim() || duplicateName || createMut.isPending}
              >
                {createMut.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="mr-2 h-4 w-4" />
                )}
                {t("categories.addNew")}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(colorTarget)}
        onOpenChange={(open) => {
          if (!open && !patchMut.isPending) setColorTarget(null);
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{t("categories.changeColor")}</DialogTitle>
            <DialogDescription className="sr-only">
              {t("categories.changeColorDescription")}
            </DialogDescription>
          </DialogHeader>
          <ColorField value={draftColor} onChange={setDraftColor} />
          {colorTarget ? (
            <div className="space-y-2">
              <span className="text-sm font-medium">
                {t("categories.preview")}
              </span>
              <div className="rounded-lg border bg-muted/20 px-4 py-3">
                <CategoryName name={colorTarget.name} color={draftColor} />
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setColorTarget(null)}
              disabled={patchMut.isPending}
            >
              {t("common.cancel")}
            </Button>
            <Button
              onClick={() => {
                if (colorTarget) {
                  patchMut.mutate({ id: colorTarget.id, color: draftColor });
                }
              }}
              disabled={!colorTarget || patchMut.isPending}
            >
              {patchMut.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              {t("common.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CategorySection({
  title,
  categories,
  emptyText,
  onAdd,
  onColorChange,
  onDelete,
}: {
  title: string;
  categories: CategoryDef[];
  emptyText?: string;
  onAdd?: () => void;
  onColorChange: (category: CategoryDef) => void;
  onDelete: (category: CategoryDef) => void;
}) {
  const { t, locale } = useT();

  return (
    <section className="space-y-3">
      <div className="flex min-h-8 items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold">{title}</h2>
          <Badge variant="secondary" className="tabular-nums">
            {categories.length}
          </Badge>
        </div>
        {onAdd && categories.length > 0 ? (
          <Button variant="outline" size="sm" onClick={onAdd}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            {t("common.add")}
          </Button>
        ) : null}
      </div>

      <div className="overflow-hidden rounded-xl border bg-card">
        {categories.length === 0 ? (
          <div className="flex flex-col items-start gap-3 px-4 py-6">
            <p className="text-sm text-muted-foreground">
              {emptyText ?? t("categories.empty")}
            </p>
            {onAdd ? (
              <Button variant="outline" size="sm" onClick={onAdd}>
                <Plus className="mr-1.5 h-3.5 w-3.5" />
                {t("categories.addFirst")}
              </Button>
            ) : null}
          </div>
        ) : (
          <>
            <div className="hidden grid-cols-[minmax(0,1fr)_8.5rem_2.5rem] items-center gap-4 border-b bg-muted/25 px-4 py-2.5 text-xs font-medium text-muted-foreground sm:grid">
              <span>{t("categories.categoryColumn")}</span>
              <span>{t("categories.transactions")}</span>
              <span className="sr-only">{t("common.actions")}</span>
            </div>
            <div className="divide-y">
              {categories.map((category) => (
                <div
                  key={category.id}
                  className="grid grid-cols-[minmax(0,1fr)_auto_2.5rem] items-center gap-3 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_8.5rem_2.5rem] sm:gap-4"
                >
                  <CategoryName
                    name={category.name}
                    color={category.color}
                    onColorClick={() => onColorChange(category)}
                  />
                  {category.usage_count > 0 ? (
                    <Link
                      href={transactionsHref({ category: category.name })}
                      className="text-sm tabular-nums text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                      title={t("categories.openTransactions")}
                    >
                      {t(transactionCountKey(locale, category.usage_count), {
                        count: category.usage_count,
                      })}
                    </Link>
                  ) : (
                    <span className="text-sm text-muted-foreground/70">
                      {t("categories.noTransactions")}
                    </span>
                  )}
                  <CategoryActions
                    category={category}
                    onColorChange={onColorChange}
                    onDelete={onDelete}
                  />
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

function transactionCountKey(
  locale: "pl" | "en",
  count: number,
):
  | "categories.transactionsCountOne"
  | "categories.transactionsCountFew"
  | "categories.transactionsCountMany" {
  if (count === 1) return "categories.transactionsCountOne";
  if (locale === "pl") {
    const lastDigit = count % 10;
    const lastTwoDigits = count % 100;
    if (
      lastDigit >= 2 &&
      lastDigit <= 4 &&
      (lastTwoDigits < 12 || lastTwoDigits > 14)
    ) {
      return "categories.transactionsCountFew";
    }
  }
  return "categories.transactionsCountMany";
}

function CategoryName({
  name,
  color,
  translate = true,
  onColorClick,
}: {
  name: string;
  color: string | null;
  translate?: boolean;
  onColorClick?: () => void;
}) {
  const { t } = useT();
  const swatch = <CategoryAccent color={color ?? DEFAULT_CATEGORY_COLOR} />;

  return (
    <div className="flex min-w-0 items-center gap-2.5">
      {onColorClick ? (
        <button
          type="button"
          className="shrink-0 cursor-pointer rounded-lg transition-transform hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          onClick={onColorClick}
          aria-label={`${t("categories.changeColor")}: ${tCategory(t, name)}`}
          title={t("categories.changeColor")}
        >
          {swatch}
        </button>
      ) : (
        <span className="shrink-0">{swatch}</span>
      )}
      <span className="truncate text-sm font-medium">
        {translate ? tCategory(t, name) : name}
      </span>
    </div>
  );
}

function CategoryActions({
  category,
  onColorChange,
  onDelete,
}: {
  category: CategoryDef;
  onColorChange: (category: CategoryDef) => void;
  onDelete: (category: CategoryDef) => void;
}) {
  const { t } = useT();
  const deleteBlocked = category.usage_count > 0;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={t("categories.actionsFor", {
            name: tCategory(t, category.name),
          })}
        >
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-52">
        <DropdownMenuItem onClick={() => onColorChange(category)}>
          <Palette className="h-4 w-4" />
          {t("categories.changeColor")}
        </DropdownMenuItem>
        {!category.is_system ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              disabled={deleteBlocked}
              onClick={() => onDelete(category)}
              className="text-destructive focus:text-destructive"
              title={deleteBlocked ? t("categories.deleteInUse") : undefined}
            >
              <Trash2 className="h-4 w-4" />
              {deleteBlocked
                ? t("categories.deleteInUse")
                : t("common.delete")}
            </DropdownMenuItem>
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ColorField({
  value,
  onChange,
}: {
  value: string;
  onChange: (color: string) => void;
}) {
  const { t } = useT();
  const customColorSelected = !CATEGORY_COLORS.some(
    (color) => color.toLowerCase() === value.toLowerCase(),
  );

  return (
    <div className="space-y-3">
      <span className="text-sm font-medium">{t("categories.color")}</span>
      <div className="space-y-1.5">
        <span className="block text-xs text-muted-foreground">
          {t("categories.palette")}
        </span>
        <div className="flex flex-wrap items-center gap-2">
          {CATEGORY_COLORS.map((color) => {
            const selected = value.toLowerCase() === color.toLowerCase();
            const foreground = getReadableForeground(color);
            return (
              <button
                key={color}
                type="button"
                className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border shadow-sm transition-transform hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                  selected
                    ? "ring-2 ring-ring ring-offset-2 ring-offset-background"
                    : ""
                }`}
                style={{ backgroundColor: color }}
                onClick={() => onChange(color)}
                aria-label={`${t("categories.selectColor")} ${color}`}
                aria-pressed={selected}
              >
                {selected ? (
                  <Check
                    className="h-4 w-4 drop-shadow-sm"
                    style={{ color: foreground }}
                  />
                ) : null}
              </button>
            );
          })}
          <label
            className={`relative inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg border border-primary/35 bg-accent-soft/70 text-accent-soft-foreground shadow-sm transition-transform hover:scale-105 hover:bg-accent-soft focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 ${
              customColorSelected
                ? "ring-2 ring-ring ring-offset-2 ring-offset-background"
                : ""
            }`}
            style={customColorSelected ? { backgroundColor: value } : undefined}
            title={t("categories.chooseCustomColor")}
          >
            <Plus
              className="h-4 w-4"
              style={
                customColorSelected
                  ? { color: getReadableForeground(value) }
                  : undefined
              }
            />
            <input
              type="color"
              value={value.toLowerCase()}
              onChange={(event) => onChange(event.target.value)}
              className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
              aria-label={t("categories.chooseCustomColor")}
            />
          </label>
        </div>
      </div>
    </div>
  );
}
