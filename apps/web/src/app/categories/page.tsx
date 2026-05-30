"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, Plus, Loader2, AlertCircle } from "lucide-react";
import { api, type CategoryDef } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useT, tCategory } from "@/lib/i18n";
import { CATEGORIES_QUERY_KEY } from "@/hooks/use-categories";

export default function CategoriesPage() {
  const { t } = useT();
  const qc = useQueryClient();
  const { data: cats = [], isLoading } = useQuery<CategoryDef[]>({
    queryKey: CATEGORIES_QUERY_KEY,
    queryFn: () => api.listCategories(),
  });

  const [newName, setNewName] = useState("");
  const [newColor, setNewColor] = useState("#888888");
  const [error, setError] = useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: (payload: { name: string; color: string }) =>
      api.createCategory(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY });
      setNewName("");
      setError(null);
    },
    onError: (err: Error) => {
      setError(
        err.message.includes("409") ? t("categories.duplicate") : err.message,
      );
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteCategory(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY }),
  });

  const patchMut = useMutation({
    mutationFn: ({ id, color }: { id: number; color: string }) =>
      api.patchCategoryDef(id, { color }),
    onSuccess: () => qc.invalidateQueries({ queryKey: CATEGORIES_QUERY_KEY }),
  });

  const onDelete = (cat: CategoryDef) => {
    const ok = window.confirm(
      t("categories.deleteConfirm", { name: tCategory(t, cat.name) }),
    );
    if (ok) deleteMut.mutate(cat.id);
  };

  const system = cats.filter((c) => c.is_system);
  const custom = cats.filter((c) => !c.is_system);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">
        {t("categories.title")}
      </h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("categories.addNew")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={newName}
              onChange={(e) => {
                setNewName(e.target.value);
                setError(null);
              }}
              placeholder={t("categories.name")}
              className="max-w-xs"
              onKeyDown={(e) => {
                if (e.key === "Enter" && newName.trim())
                  createMut.mutate({ name: newName.trim(), color: newColor });
              }}
            />
            <input
              type="color"
              value={newColor}
              onChange={(e) => setNewColor(e.target.value)}
              className="h-9 w-12 cursor-pointer rounded border border-input bg-transparent"
              aria-label={t("categories.color")}
            />
            <Button
              onClick={() =>
                newName.trim() &&
                createMut.mutate({ name: newName.trim(), color: newColor })
              }
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
          <p className="mt-2 text-xs text-muted-foreground">
            {t("categories.systemNote")}
          </p>
        </CardContent>
      </Card>

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> {t("common.loading")}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("categories.system")}</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <CategoryTable
            categories={system}
            onDelete={onDelete}
            onColorChange={(id, color) => patchMut.mutate({ id, color })}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("categories.custom")}</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {custom.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">
              {t("categories.empty")}
            </p>
          ) : (
            <CategoryTable
              categories={custom}
              onDelete={onDelete}
              onColorChange={(id, color) => patchMut.mutate({ id, color })}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function CategoryTable({
  categories,
  onDelete,
  onColorChange,
}: {
  categories: CategoryDef[];
  onDelete: (cat: CategoryDef) => void;
  onColorChange: (id: number, color: string) => void;
}) {
  const { t } = useT();
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-12">{t("categories.color")}</TableHead>
          <TableHead>{t("categories.name")}</TableHead>
          <TableHead className="text-right">{t("categories.usage")}</TableHead>
          <TableHead className="w-20" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {categories.map((c) => (
          <TableRow key={c.id}>
            <TableCell>
              <input
                type="color"
                value={c.color ?? "#888888"}
                onChange={(e) => onColorChange(c.id, e.target.value)}
                className="h-7 w-10 cursor-pointer rounded border border-input bg-transparent"
                aria-label={t("categories.color")}
              />
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-2">
                <span>{tCategory(t, c.name)}</span>
                {c.is_system && (
                  <Badge variant="outline" className="text-[10px]">
                    system
                  </Badge>
                )}
              </div>
            </TableCell>
            <TableCell className="text-right tabular-nums text-muted-foreground">
              {c.usage_count}
            </TableCell>
            <TableCell>
              {!c.is_system && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => onDelete(c)}
                  aria-label={t("common.delete")}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
