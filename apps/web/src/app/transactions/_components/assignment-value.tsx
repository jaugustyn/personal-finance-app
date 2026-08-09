import type { ReactNode } from "react";
import { Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface AssignmentValueProps {
  label: string | null;
  suggested?: boolean;
  icon?: ReactNode;
  description?: ReactNode;
  title?: string;
  onEdit?: () => void;
  onAccept?: () => void;
  acceptLabel?: string;
  acceptPending?: boolean;
  actions?: ReactNode;
}

export function AssignmentValue({
  label,
  suggested = false,
  icon,
  description,
  title,
  onEdit,
  onAccept,
  acceptLabel,
  acceptPending = false,
  actions,
}: AssignmentValueProps) {
  if (!label) {
    return <span className="text-muted-foreground">—</span>;
  }

  const value = suggested ? (
    <Badge
      variant="outline"
      className="max-w-full gap-1.5 truncate border-dashed bg-background"
    >
      {icon}
      {label}
    </Badge>
  ) : (
    <span className="inline-flex max-w-full items-center gap-1.5 text-sm font-medium text-foreground">
      {icon}
      <span className="truncate">{label}</span>
    </span>
  );

  return (
    <div className="flex min-w-0 items-start gap-1.5">
      <div className="flex min-w-0 flex-col items-start gap-1">
        {onEdit ? (
          <button
            type="button"
            onClick={onEdit}
            className="-mx-1.5 -my-1 min-w-0 rounded-md px-1.5 py-1 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            title={title}
          >
            {value}
          </button>
        ) : (
          <span className="min-w-0" title={title}>
            {value}
          </span>
        )}
        {description ? (
          <span className="text-[11px] text-muted-foreground">
            {description}
          </span>
        ) : null}
      </div>
      {onAccept ? (
        <Button
          type="button"
          size="icon"
          variant="outline"
          className="h-7 w-7 shrink-0 border-positive/30 text-positive hover:bg-positive/10 hover:text-positive"
          disabled={acceptPending}
          onClick={onAccept}
          title={acceptLabel}
          aria-label={acceptLabel}
        >
          <Check className="h-3.5 w-3.5" />
        </Button>
      ) : null}
      {actions}
    </div>
  );
}
