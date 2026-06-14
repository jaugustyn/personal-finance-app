"""Anomaly detection on transaction data.

Hybrid approach (per plan):
  - Isolation Forest on engineered features.
  - Heuristic rules: amount >> category median, brand-new merchant, large outflow.
  - Severity = combination of model score + rule hits.
"""
from .detector import AnomalyResult, detect_anomalies
from .service import AnomalyReviewRow, list_anomaly_rows, record_anomaly_feedback

__all__ = [
    "AnomalyResult",
    "AnomalyReviewRow",
    "detect_anomalies",
    "list_anomaly_rows",
    "record_anomaly_feedback",
]
