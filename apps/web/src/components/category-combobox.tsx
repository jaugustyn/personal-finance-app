"use client";

import { useMemo, useState } from "react";
import { Plus, Check, X } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useCategories, CATEGORIES_QUERY_KEY } from "@/hooks/use-categories";
import { useT, tCategory, type TranslationKey } from "@/lib/i18n";

const CLEAR_VALUE = "__clear__";
const NEW_VALUE = "__new__";

interface Props {
  value: string | null;
  onChange: (value: string | null) => void;
  autoFocus?: boolean;
  size?: "sm" | "md";
  className?: string;
}

/**
 * Native `<select>` with the user's category catalog plus an inline
 * "+ new category" affordance. Stays minimal — no popover, no command-K.
 */
export function CategoryCombobox({
  value,
  onChange,
  autoFocus,
  size = "sm",
  className,
}: Props) {
  const { t } = useT();
  const { data: categories = [] } = useCategories();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: (name: string) => api.createCategory({ name }),
    onSuccess: (cat) => {
      qc.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY });
      setCreating(false);
      setNewName("");
      onChange(cat.name);
    },
    onError: (err: Error) => {
      if (err.message.includes("409")) setError(t("categories.duplicate"));
      else setError(err.message);
    },
  });

  const sortedCats = useMemo(
    () =>
      [...categories].sort((a, b) => {
        if (a.is_system !== b.is_system) return a.is_system ? -1 : 1;
        return a.name.localeCompare(b.name);
      }),
    [categories],
  );

  if (creating) {
    return (
      <div className={`flex items-center gap-1 ${className ?? ""}`}>
        <input
          autoFocus
          type="text"
          value={newName}
          onChange={(e) => {
            setNewName(e.target.value);
            setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && newName.trim())
              createMut.mutate(newName.trim());
            if (e.key === "Escape") {
              setCreating(false);
              setNewName("");
              setError(null);
            }
          }}
          placeholder={t("categories.name")}
          className={`h-7 rounded-md border border-input bg-transparent px-2 text-xs ${
            error ? "border-destructive" : ""
          }`}
        />
        <button
          type="button"
          onClick={() => newName.trim() && createMut.mutate(newName.trim())}
          disabled={!newName.trim() || createMut.isPending}
          className="rounded-md p-1 text-emerald-600 hover:bg-emerald-500/10 disabled:opacity-50"
          aria-label={t("common.save")}
        >
          <Check className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={() => {
            setCreating(false);
            setNewName("");
            setError(null);
          }}
          className="rounded-md p-1 text-muted-foreground hover:bg-muted"
          aria-label={t("common.cancel")}
        >
          <X className="h-3.5 w-3.5" />
        </button>
        {error && <span className="text-xs text-destructive">{error}</span>}
      </div>
    );
  }

  const heightCls = size === "sm" ? "h-7 text-xs" : "h-9 text-sm";

  return (
    <select
      autoFocus={autoFocus}
      value={value ?? ""}
      onChange={(e) => {
        const v = e.target.value;
        if (v === NEW_VALUE) {
          setCreating(true);
          return;
        }
        if (v === CLEAR_VALUE || v === "") {
          onChange(null);
          return;
        }
        onChange(v);
      }}
      className={`${heightCls} rounded-md border border-input bg-transparent px-2 ${className ?? ""}`}
    >
      <option value={CLEAR_VALUE}>{t("common.unknown")}</option>
      {sortedCats.map((c) => {
        const labelKey = `category.${c.name}` as TranslationKey;
        const label = c.is_system ? tCategory(t, c.name) : c.name;
        // Cheap detection of translated keys: if tCategory returned the raw
        // name we still want a usable label.
        void labelKey;
        return (
          <option key={c.id} value={c.name}>
            {label}
          </option>
        );
      })}
      <option value={NEW_VALUE}>+ {t("categories.addNew")}</option>
    </select>
  );
}

/** Compact icon button alternative used in toolbars. */
export function NewCategoryInlineButton({
  onCreated,
}: {
  onCreated?: (name: string) => void;
}) {
  const { t } = useT();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: (n: string) => api.createCategory({ name: n }),
    onSuccess: (cat) => {
      qc.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY });
      setOpen(false);
      setName("");
      onCreated?.(cat.name);
    },
    onError: (err: Error) =>
      setError(
        err.message.includes("409") ? t("categories.duplicate") : err.message,
      ),
  });

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-1 rounded-md border border-dashed border-muted-foreground/40 px-2 py-1 text-xs text-muted-foreground hover:border-primary hover:text-primary"
      >
        <Plus className="h-3.5 w-3.5" />
        {t("categories.addNew")}
      </button>
    );
  }
  return (
    <div className="flex items-center gap-1">
      <input
        autoFocus
        value={name}
        onChange={(e) => {
          setName(e.target.value);
          setError(null);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && name.trim()) createMut.mutate(name.trim());
          if (e.key === "Escape") setOpen(false);
        }}
        placeholder={t("categories.name")}
        className="h-7 rounded-md border border-input bg-transparent px-2 text-xs"
      />
      {error && <span className="text-xs text-destructive">{error}</span>}
    </div>
  );
}
