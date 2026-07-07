import { RefreshCw } from "lucide-react";

import type { MlRetrainSignal } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatNumber } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { percent, retrainReasonLabel } from "../_lib/ml-format";

export function RetrainSignalCard({ signal }: { signal: MlRetrainSignal }) {
  const { t } = useT();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base text-foreground">
          <RefreshCw className="h-4 w-4 text-muted-foreground" />
          {t("ml.retrainSignal.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {signal.retrain_recommended ? (
          <Badge variant="warning">{t("ml.retrainSignal.recommended")}</Badge>
        ) : null}
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-md border bg-muted/20 p-3">
            <div className="text-xs text-muted-foreground">
              {t("ml.retrainSignal.newLabels")}
            </div>
            <div className="mt-1 text-lg font-semibold tabular-nums">
              {formatNumber(signal.new_labels_since_training)}
            </div>
            <div className="text-xs text-muted-foreground">
              {percent(signal.new_labels_since_training_ratio)}
            </div>
          </div>
          <div className="rounded-md border bg-muted/20 p-3">
            <div className="text-xs text-muted-foreground">
              {t("ml.retrainSignal.feedback")}
            </div>
            <div className="mt-1 text-lg font-semibold tabular-nums">
              {formatNumber(signal.feedback_events_since_model)}
            </div>
          </div>
          <div className="rounded-md border bg-muted/20 p-3">
            <div className="text-xs text-muted-foreground">
              {t("ml.retrainSignal.rejectionRate")}
            </div>
            <div className="mt-1 text-lg font-semibold tabular-nums">
              {percent(signal.rejection_rate)}
            </div>
          </div>
        </div>
        {signal.reason_codes.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {signal.reason_codes.map((reason) => (
              <Badge key={reason} variant="muted">
                {retrainReasonLabel(reason, t)}
              </Badge>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
