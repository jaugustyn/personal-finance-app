"""Anomaly detection on transaction data.

Hybrid approach (per plan):
  - Isolation Forest on engineered features.
  - Heuristic rules: amount >> category median, brand-new merchant, large outflow.
  - Severity = combination of model score + rule hits.
"""
from .detector import AnomalyResult, detect_anomalies

__all__ = ["AnomalyResult", "detect_anomalies"]
