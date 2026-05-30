"""Forecast page — historical monthly spending + chosen-model prediction."""
import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _auth  # noqa: E402, F401
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Prognoza", page_icon="📈", layout="wide")
st.title("📈 Prognoza wydatków")

CATEGORIES = [
    "(wszystkie)", "food", "transport", "subscriptions", "entertainment",
    "housing", "health", "savings", "other",
]
col1, col2 = st.columns([2, 1])
with col1:
    category = st.selectbox("Kategoria", CATEGORIES, index=0)
with col2:
    horizon = st.slider("Horyzont (mies.)", min_value=1, max_value=12, value=3)

params: dict[str, str | int] = {"horizon": horizon}
if category != "(wszystkie)":
    params["category"] = category

try:
    r = requests.get(f"{API_BASE_URL}/forecast", params=params, timeout=30)
    if r.status_code == 404:
        st.info("Brak danych dla wybranych filtrów.")
        st.stop()
    r.raise_for_status()
    data = r.json()
except requests.exceptions.RequestException as exc:
    st.error(f"Nie mogę połączyć się z API ({API_BASE_URL}).")
    st.exception(exc)
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("Wybrany model", data["model"])
c2.metric("MAPE (CV)", f"{data['mape']:.1f}%" if data["mape"] is not None else "—")
c3.metric("RMSE (CV)", f"{data['rmse']:.0f}" if data["rmse"] is not None else "—")

hist = pd.DataFrame(data["history"])
fc = pd.DataFrame(data["forecast"])
hist["month"] = pd.to_datetime(hist["month"])
fc["month"] = pd.to_datetime(fc["month"])

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=hist["month"], y=hist["amount"], name="historia",
    mode="lines+markers", line=dict(color="steelblue"),
))
fig.add_trace(go.Scatter(
    x=fc["month"], y=fc["amount"], name=f"prognoza ({data['model']})",
    mode="lines+markers", line=dict(color="crimson", dash="dash"),
))
fig.update_layout(
    height=420, xaxis_title="miesiąc", yaxis_title="PLN",
    title=f"Wydatki: {category} — historia + {horizon} mies. prognozy",
)
st.plotly_chart(fig, use_container_width=True)

with st.expander("Tabela danych"):
    st.write("**Historia**")
    st.dataframe(hist, use_container_width=True)
    st.write("**Prognoza**")
    st.dataframe(fc, use_container_width=True)
