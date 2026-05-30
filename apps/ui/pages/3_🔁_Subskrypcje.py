"""Subscriptions page — recurring debits and estimated monthly cost."""
import os
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _auth  # noqa: E402, F401
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Subskrypcje", page_icon="🔁", layout="wide")
st.title("🔁 Subskrypcje")

st.caption(
    "Heurystyka: cykliczne obciążenia tego samego sprzedawcy z podobną kwotą "
    "i równomiernymi odstępami (tygodniowo / co 2 tyg. / miesięcznie / rocznie)."
)

with st.sidebar:
    st.subheader("Strojenie detektora")
    min_occ = st.slider("Min. liczba wystąpień", 2, 6, 2)
    amount_tol = st.slider("Tolerancja kwoty (%)", 0, 30, 10) / 100.0
    day_tol = st.slider("Tolerancja kadencji (dni)", 1, 10, 5)
    min_conf = st.slider("Min. zaufanie", 0.0, 1.0, 0.5, step=0.05)

try:
    r = requests.get(
        f"{API_BASE_URL}/subscriptions",
        params={
            "min_occurrences": min_occ,
            "amount_tol": amount_tol,
            "day_tol": day_tol,
            "min_confidence": min_conf,
        },
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json()
except requests.exceptions.RequestException as exc:
    st.error(f"Nie mogę połączyć się z API ({API_BASE_URL}).")
    st.exception(exc)
    st.stop()

if not rows:
    st.info(
        "Nie wykryto cyklicznych płatności. Spróbuj zmniejszyć liczbę wystąpień "
        "lub zwiększyć tolerancję — przy krótkiej historii to typowe."
    )
    st.stop()

df = pd.DataFrame(rows)
df["last_seen"] = pd.to_datetime(df["last_seen"])
total = float(df["estimated_monthly_cost"].sum())
yearly = total * 12

c1, c2, c3 = st.columns(3)
c1.metric("Wykryte subskrypcje", len(df))
c2.metric("Szacunkowy koszt mies.", f"{total:,.2f} PLN")
c3.metric("Szacunkowy koszt roczny", f"{yearly:,.2f} PLN")

st.dataframe(
    df[["merchant", "cadence", "median_amount", "occurrences",
        "last_seen", "estimated_monthly_cost", "confidence"]],
    use_container_width=True,
    column_config={
        "confidence": st.column_config.ProgressColumn(
            "zaufanie", min_value=0.0, max_value=1.0, format="%.2f",
        ),
    },
)
