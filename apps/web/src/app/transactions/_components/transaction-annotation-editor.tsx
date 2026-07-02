"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Transaction } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { Save, X } from "lucide-react";

interface TransactionAnnotationEditorProps {
  tx: Transaction;
  onCancel: () => void;
  onSave: (notes: string | null, tags: string[]) => void;
}

export function TransactionAnnotationEditor({
  tx,
  onCancel,
  onSave,
}: TransactionAnnotationEditorProps) {
  const { t } = useT();
  const [notes, setNotes] = useState(tx.notes ?? "");
  const [tagsText, setTagsText] = useState((tx.tags ?? []).join(", "));

  const handleSave = () => {
    const tags = tagsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    onSave(notes.trim() || null, tags);
  };

  return (
    <div className="mt-2 space-y-2" onClick={(e) => e.stopPropagation()}>
      <Input
        value={tagsText}
        onChange={(e) => setTagsText(e.target.value)}
        placeholder={t("transactions.tagsPlaceholder")}
        className="h-8 text-xs"
        autoFocus
      />
      <Input
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder={t("transactions.notesPlaceholder")}
        className="h-8 text-xs"
      />
      <div className="flex gap-2">
        <Button size="sm" className="h-7" onClick={handleSave}>
          <Save className="h-3.5 w-3.5" />
          {t("common.save")}
        </Button>
        <Button size="sm" variant="ghost" className="h-7" onClick={onCancel}>
          <X className="h-3.5 w-3.5" />
          {t("common.cancel")}
        </Button>
      </div>
    </div>
  );
}
