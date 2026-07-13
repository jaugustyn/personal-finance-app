import type { ReactNode } from "react";
import { Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface AssignmentValueProps {
  label: string | null;
  suggested?: boolean;
  icon?: ReactNode;
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

  const value = (
    <Badge
      variant={suggested ? "outline" : "secondary"}
      className={cn(
        "max-w-full truncate",
        suggested && "border-dashed bg-background",
      )}
    >
      {icon}
      {label}
    </Badge>
  );

  return (
    <div className="flex min-w-0 items-center gap-1.5">
      {onEdit ? (
        <button
          type="button"
          onClick={onEdit}
          className="min-w-0 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          title={title}
        >
          {value}
        </button>
      ) : (
        <span className="min-w-0" title={title}>
          {value}
        </span>
      )}
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
