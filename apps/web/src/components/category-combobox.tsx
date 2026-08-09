"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronsUpDown, Plus, X } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useCategories } from "@/hooks/use-categories";
import { useFormatters, useT, tCategory } from "@/lib/i18n";
import { queryKeys } from "@/lib/query-keys";
import { showErrorToast } from "@/lib/toasts";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { CategoryCompactAccent } from "@/components/category-accent";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";

interface Props {
  id?: string;
  /** Selected category group name (the ML category), or null. */
  value: string | null;
  /** Selected subcategory name, currently hidden in the UI. */
  subValue?: string | null;
  onChange: (selection: CategorySelection) => void;
  autoFocus?: boolean;
  size?: "sm" | "md";
  className?: string;
  ariaLabel?: string;
  /** When true, only category groups are selectable (e.g. bulk operations). */
  groupsOnly?: boolean;
}

/** Structured category choice. Subcategories are supported by API but hidden for now. */
export interface CategorySelection {
  category: string | null;
  subcategory: string | null;
}

const SHOW_SUBCATEGORIES = false;

/** Compact category accent kept as a compatibility wrapper for existing pickers. */
export function CategoryColorDot({
  color,
  subtle = false,
}: {
  color?: string | null;
  subtle?: boolean;
}) {
  return (
    <CategoryCompactAccent
      color={color}
      className={subtle ? "opacity-60" : undefined}
    />
  );
}

/**
 * Category picker built on Popover + Command (cmdk). The backend still supports
 * subcategories, but the UI currently exposes only top-level ML categories.
 */
export function CategoryCombobox({
  id,
  value,
  subValue = null,
  onChange,
  autoFocus,
  size = "sm",
  className,
  ariaLabel,
  groupsOnly = false,
}: Props) {
  const { t } = useT();
  const { compare } = useFormatters();
  const {
    data: categories = [],
    isError: categoriesError,
    refetch: refetchCategories,
  } = useCategories();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const didAutoOpen = useRef(false);

  useEffect(() => {
    if (autoFocus && !didAutoOpen.current) {
      didAutoOpen.current = true;
      setOpen(true);
    }
  }, [autoFocus]);

  const createMut = useMutation({
    mutationFn: (name: string) => api.createCategory({ name }),
    onSuccess: (cat) => {
      void qc.invalidateQueries({ queryKey: queryKeys.categories.all });
      onChange({ category: cat.name, subcategory: null });
      setSearch("");
      setOpen(false);
    },
    onError: (error) => showErrorToast(error, t("toast.error")),
  });

  const catLabel = (name: string, isSystem: boolean) =>
    isSystem ? tCategory(t, name) : name;

  // Show only top-level categories for now. Subcategories remain in the catalog
  // response but are hidden until the workflow needs them.
  const groups = useMemo(() => {
    const parents = categories
      .filter((c) => !c.parent)
      .sort((a, b) => {
        if (a.is_system !== b.is_system) return a.is_system ? -1 : 1;
        return compare(a.name, b.name);
      });
    return parents.map((parent) => ({
      parent,
      children: SHOW_SUBCATEGORIES
        ? categories
            .filter((c) => c.parent === parent.name)
            .sort((a, b) => compare(a.name, b.name))
        : [],
    }));
  }, [categories, compare]);

  const current = useMemo(
    () => categories.find((c) => c.name === value) ?? null,
    [categories, value],
  );
  const currentSub = useMemo(
    () => categories.find((c) => c.name === subValue) ?? null,
    [categories, subValue],
  );

  const label = SHOW_SUBCATEGORIES && subValue
    ? catLabel(subValue, currentSub?.is_system ?? true)
    : value
      ? catLabel(value, current?.is_system ?? true)
      : t("common.unknown");

  const trimmed = search.trim();
  const exactExists = categories.some(
    (c) => c.name.toLowerCase() === trimmed.toLowerCase(),
  );
  const heightCls = size === "sm" ? "h-8 text-xs" : "h-9 text-sm";

  const selectGroup = (name: string) => {
    onChange({ category: name, subcategory: null });
    setOpen(false);
  };
  const selectSub = (parent: string, name: string) => {
    onChange({ category: parent, subcategory: name });
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-label={ariaLabel ?? t("transactions.column.category")}
          className={cn(
            "w-full justify-between gap-2 font-normal",
            heightCls,
            !value && "text-muted-foreground",
            className,
          )}
        >
          <span className="flex min-w-0 items-center gap-2">
            <CategoryColorDot
              color={
                SHOW_SUBCATEGORIES
                  ? currentSub?.color ?? current?.color
                  : current?.color
              }
            />
            <span className="truncate">{label}</span>
          </span>
          <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="start">
        <Command
          filter={(itemValue, query) =>
            itemValue.toLowerCase().includes(query.toLowerCase()) ? 1 : 0
          }
        >
          <CommandInput
            placeholder={t("categories.searchPlaceholder")}
            value={search}
            onValueChange={setSearch}
            clearLabel={t("common.clear")}
          />
          <CommandList>
            {categoriesError ? (
              <div className="px-3 py-2 text-center text-xs text-destructive">
                {t("common.error")} ·{" "}
                <button
                  type="button"
                  onClick={() => void refetchCategories()}
                  className="underline underline-offset-4"
                >
                  {t("common.retry")}
                </button>
              </div>
            ) : null}
            <CommandEmpty>
              {categoriesError ? null : trimmed ? (
                <button
                  type="button"
                  onClick={() => createMut.mutate(trimmed)}
                  disabled={createMut.isPending}
                  className="flex w-full items-center justify-center gap-2 text-sm text-primary"
                >
                  <Plus className="h-3.5 w-3.5" />
                  {t("categories.createNamed", { name: trimmed })}
                </button>
              ) : (
                t("common.empty")
              )}
            </CommandEmpty>
            <CommandGroup>
              <CommandItem
                value={t("common.unknown")}
                onSelect={() => {
                  onChange({ category: null, subcategory: null });
                  setOpen(false);
                }}
              >
                <X className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-muted-foreground">
                  {t("common.unknown")}
                </span>
                {!value && <Check className="ml-auto h-3.5 w-3.5" />}
              </CommandItem>
            </CommandGroup>
            {SHOW_SUBCATEGORIES ? (
              groups.map(({ parent, children }) => {
                const parentLabel = catLabel(parent.name, parent.is_system);
                return (
                  <CommandGroup key={parent.id} heading={parentLabel}>
                    <CommandItem
                      value={`${parent.name} ${parentLabel}`}
                      onSelect={() => selectGroup(parent.name)}
                    >
                      <CategoryColorDot color={parent.color} />
                      <span className="truncate">{parentLabel}</span>
                      {value === parent.name && !subValue && (
                        <Check className="ml-auto h-3.5 w-3.5" />
                      )}
                    </CommandItem>
                    {!groupsOnly &&
                      children.map((child) => {
                        const childLabel = catLabel(child.name, child.is_system);
                        return (
                          <CommandItem
                            key={child.id}
                            value={`${child.name} ${childLabel} ${parentLabel}`}
                            onSelect={() => selectSub(parent.name, child.name)}
                            className="pl-6"
                          >
                            <CategoryColorDot color={child.color} subtle />
                            <span className="truncate text-muted-foreground">
                              {childLabel}
                            </span>
                            {subValue === child.name && (
                              <Check className="ml-auto h-3.5 w-3.5" />
                            )}
                          </CommandItem>
                        );
                      })}
                  </CommandGroup>
                );
              })
            ) : (
              <CommandGroup>
                {groups.map(({ parent }) => {
                  const parentLabel = catLabel(parent.name, parent.is_system);
                  return (
                    <CommandItem
                      key={parent.id}
                      value={`${parent.name} ${parentLabel}`}
                      onSelect={() => selectGroup(parent.name)}
                    >
                      <CategoryColorDot color={parent.color} />
                      <span className="truncate">{parentLabel}</span>
                      {value === parent.name && (
                        <Check className="ml-auto h-3.5 w-3.5" />
                      )}
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            )}
            {trimmed && !exactExists && (
              <CommandGroup>
                <CommandItem
                  value={`__create__${trimmed}`}
                  onSelect={() => createMut.mutate(trimmed)}
                >
                  <Plus className="h-3.5 w-3.5 text-primary" />
                  <span className="text-primary">
                    {t("categories.createNamed", { name: trimmed })}
                  </span>
                </CommandItem>
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
