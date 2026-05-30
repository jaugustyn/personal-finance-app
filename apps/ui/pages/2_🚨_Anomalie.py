"""Anomalies page — top flagged transactions."""
import os
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _auth  # noqa: E402, F401
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Anomalie", page_icon="🚨", layout="wide")
st.title("🚨 Anomalie")

contamination = st.slider(
    "Czułość (frakcja oczekiwanych anomalii)",
    min_value=0.01, max_value=0.20, value=0.05, step=0.01,
)
direction = st.radio(
    "Kierunek transakcji",
    options=["debit", "credit", "both"],
    horizontal=True,
    format_func=lambda x: {"debit": "wydatki", "credit": "wpływy", "both": "wszystko"}[x],
)
limit = st.number_input("Limit wierszy", 10, 500, 50)

try:
    params: dict[str, str | float | int] = {
        "contamination": contamination,
        "direction": direction,
        "limit": int(limit),
    }
    r = requests.get(
        f"{API_BASE_URL}/anomalies",
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json()
except requests.exceptions.RequestException as exc:
    st.error(f"Nie mogę połączyć się z API ({API_BASE_URL}).")
    st.exception(exc)
    st.stop()

if not rows:
    st.info("Brak wykrytych anomalii dla tej czułości.")
    st.stop()

df = pd.DataFrame(rows)
df["amount"] = pd.to_numeric(df["amount"])
df["booking_date"] = pd.to_datetime(df["booking_date"])
if "reasons" in df.columns:
    df["reasons"] = df["reasons"].apply(
        lambda value: ", ".join(value) if isinstance(value, list) else str(value or "")
    )

st.metric("Liczba flag", len(df))
st.dataframe(
    df[["booking_date", "merchant", "title", "amount", "direction",
        "category", "severity", "reasons"]],
    use_container_width=True,
    column_config={
        "severity": st.column_config.ProgressColumn(
            "severity", min_value=0.0, max_value=1.0, format="%.2f",
        ),
    },
)
