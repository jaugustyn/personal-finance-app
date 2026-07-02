import { BrainCircuit } from "lucide-react";

import { useT } from "@/lib/i18n";
import { formatNumber } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { numberFromRecord, percent, retrainReasonLabel } from "../_lib/ml-format";

export function RetrainSignalCard({ signal }: { signal: Record<string, unknown> }) {
  const { t } = useT();
  const recommended = signal.retrain_recommended === true;
  const reasons = Array.isArray(signal.reason_codes)
    ? signal.reason_codes.map(String)
    : [];
  const newLabels = numberFromRecord(signal, "new_labels_since_training") ?? 0;
  const labelGrowth = numberFromRecord(signal, "new_labels_since_training_ratio");
  const feedbackSince = numberFromRecord(signal, "feedback_events_since_model") ?? 0;
  const rejectionRate = numberFromRecord(signal, "rejection_rate");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base text-foreground">
          <BrainCircuit className="h-4 w-4 text-muted-foreground" />
          {t("ml.retrainSignal.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Badge variant={recommended ? "warning" : "success"}>
          {recommended
            ? t("ml.retrainSignal.recommended")
            : t("ml.retrainSignal.stable")}
        </Badge>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-md border bg-muted/20 p-3">
            <div className="text-xs text-muted-foreground">
              {t("ml.retrainSignal.newLabels")}
            </div>
            <div className="mt-1 text-lg font-semibold tabular-nums">
              {formatNumber(newLabels)}
            </div>
            <div className="text-xs text-muted-foreground">
              {percent(labelGrowth)}
            </div>
          </div>
          <div className="rounded-md border bg-muted/20 p-3">
            <div className="text-xs text-muted-foreground">
              {t("ml.retrainSignal.feedback")}
            </div>
            <div className="mt-1 text-lg font-semibold tabular-nums">
              {formatNumber(feedbackSince)}
            </div>
          </div>
          <div className="rounded-md border bg-muted/20 p-3">
            <div className="text-xs text-muted-foreground">
              {t("ml.retrainSignal.rejectionRate")}
            </div>
            <div className="mt-1 text-lg font-semibold tabular-nums">
              {percent(rejectionRate)}
            </div>
          </div>
        </div>
        {reasons.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {reasons.map((reason) => (
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
