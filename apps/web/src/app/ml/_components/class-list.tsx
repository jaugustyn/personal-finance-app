import { Badge } from "@/components/ui/badge";
import { tCategory, useT } from "@/lib/i18n";

export function ClassList({
  title,
  values,
  variant,
}: {
  title: string;
  values: string[];
  variant: "secondary" | "destructive" | "outline";
}) {
  const { t } = useT();
  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-muted-foreground">{title}</div>
      {values.length === 0 ? (
        <span className="text-sm text-muted-foreground">—</span>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {values.map((value) => (
            <Badge key={value} variant={variant}>
              {tCategory(t, value)}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
