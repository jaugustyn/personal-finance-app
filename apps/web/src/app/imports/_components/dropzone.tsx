"use client";

import { useState } from "react";
import { Upload } from "lucide-react";

export function Dropzone({
  onFile,
  label,
  disabled,
}: {
  onFile: (f: File | null) => void;
  label: string;
  disabled?: boolean;
}) {
  const [hover, setHover] = useState(false);
  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        setHover(true);
      }}
      onDragLeave={() => setHover(false)}
      onDrop={(e) => {
        e.preventDefault();
        setHover(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      className={`flex h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed text-sm transition-colors ${
        hover ? "border-primary bg-primary/5" : "border-muted-foreground/30"
      } ${disabled ? "pointer-events-none opacity-50" : ""}`}
    >
      <Upload className="h-6 w-6 text-muted-foreground" />
      <span className="text-muted-foreground">{label}</span>
      <input
        type="file"
        accept=".csv,.tsv,.txt,text/csv,text/plain,text/tab-separated-values"
        className="hidden"
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
      />
    </label>
  );
}
