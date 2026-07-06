"use client";

import { CalendarClock } from "lucide-react";

import type { SubscriptionOverview } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";

export function UpcomingPaymentsCard({
  overview,
}: {
  overview: SubscriptionOverview | undefined;
}) {
  const { t } = useT();
  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">
              {t("subscriptions.upcoming")}
            </h2>
            <p className="text-xs text-muted-foreground">
              {t("subscriptions.upcomingHint")}
            </p>
          </div>
          <CalendarClock className="h-4 w-4 text-muted-foreground" />
        </div>
        {!overview || overview.upcoming.length === 0 ? (
          <div className="text-sm text-muted-foreground">
            {t("subscriptions.upcomingEmpty")}
          </div>
        ) : (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {overview.upcoming.slice(0, 6).map((item) => (
              <div
                key={`${item.subscription_key}-${item.due_date}`}
                className="rounded-md border bg-muted/20 p-3 text-sm"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-medium">{item.display_name}</span>
                  <span className="shrink-0 tabular-nums">
                    {formatCurrency(item.amount_base, item.base_currency)}
                  </span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {formatDate(item.due_date)}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
