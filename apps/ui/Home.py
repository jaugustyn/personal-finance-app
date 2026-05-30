"""Streamlit home page — KPIs and category breakdown."""
import os
from datetime import date, timedelta

import _auth  # noqa: F401  (installs HTTP Basic Auth via env)
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Personal Finance", page_icon="💸", layout="wide")
st.title("💸 Personal Finance — przegląd")


@st.cache_data(ttl=30)
def fetch_summary(date_from: date, date_to: date) -> pd.DataFrame:
    r = requests.get(
        f"{API_BASE_URL}/transactions/summary/by-category",
        params={"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
        timeout=10,
    )
    r.raise_for_status()
    return pd.DataFrame(r.json())


@st.cache_data(ttl=30)
def fetch_transactions(date_from: date, date_to: date, limit: int = 1000) -> pd.DataFrame:
    params: dict[str, str | int] = {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "limit": limit,
    }
    r = requests.get(
        f"{API_BASE_URL}/transactions",
        params=params,
        timeout=10,
    )
    r.raise_for_status()
    df = pd.DataFrame(r.json())
    if not df.empty:
        df["booking_date"] = pd.to_datetime(df["booking_date"])
        df["amount"] = pd.to_numeric(df["amount"])
    return df


with st.sidebar:
    st.header("Zakres dat")
    today = date.today()
    default_from = today - timedelta(days=90)
    date_from = st.date_input("Od", value=default_from)
    date_to = st.date_input("Do", value=today)

    st.divider()
    st.header("ML")
    if st.button("Przewiduj kategorie dla nieoznaczonych"):
        try:
            r = requests.post(f"{API_BASE_URL}/ml/reclassify", timeout=60)
            r.raise_for_status()
            st.success(f"Zaktualizowano: {r.json().get('updated', 0)} transakcji")
            st.cache_data.clear()
        except requests.exceptions.HTTPError as exc:
            st.error(f"Klasyfikator niedostępny: {exc.response.text}")
        except requests.exceptions.RequestException as exc:
            st.error(f"Błąd połączenia: {exc}")
    if st.button("🔁 Przetrenuj klasyfikator"):
        try:
            r = requests.post(f"{API_BASE_URL}/ml/retrain", timeout=10)
            r.raise_for_status()
            st.success(r.json().get("message", "Trening uruchomiony w tle."))
        except requests.exceptions.RequestException as exc:
            st.error(f"Nie udało się: {exc}")

try:
    summary = fetch_summary(date_from, date_to)
    txs = fetch_transactions(date_from, date_to)
except requests.exceptions.RequestException as exc:
    st.error(f"Nie mogę połączyć się z API ({API_BASE_URL}). Czy backend działa?")
    st.exception(exc)
    st.stop()

if txs.empty:
    st.info("Brak transakcji w wybranym zakresie. Zaimportuj plik CSV przez API: "
            f"`POST {API_BASE_URL}/imports`.")
    st.stop()

# Effective category: ground truth fallback to model prediction (with marker).
if "category_predicted" not in txs.columns:
    txs["category_predicted"] = None
if "category_confidence" not in txs.columns:
    txs["category_confidence"] = None

def _effective(row: pd.Series) -> str:
    if pd.notna(row["category"]) and row["category"]:
        return row["category"]
    if pd.notna(row["category_predicted"]) and row["category_predicted"]:
        return f"{row['category_predicted']} *"
    return "(brak)"

txs["category_effective"] = txs.apply(_effective, axis=1)
star_count = int((txs["category"].isna() & txs["category_predicted"].notna()).sum())
if star_count:
    st.caption(f"✱ oznacza kategorię przewidywaną przez model ({star_count} transakcji).")

c1, c2, c3 = st.columns(3)
total_debit = float(summary["total_debit"].sum()) if not summary.empty else 0.0
total_credit = float(summary["total_credit"].sum()) if not summary.empty else 0.0
c1.metric("Wydatki (debit)", f"{total_debit:,.2f}")
c2.metric("Wpływy (credit)", f"{total_credit:,.2f}")
c3.metric("Liczba transakcji", len(txs))

st.subheader("Wydatki per kategoria")
if not summary.empty:
    # Augment summary with predicted-only buckets so charts reflect the model.
    debit_by_eff = (
        txs[txs["direction"] == "debit"]
        .assign(cat=txs["category_effective"])
        .groupby("cat", as_index=False)["amount"]
        .sum()
        .rename(columns={"cat": "category", "amount": "total_debit"})
        .sort_values("total_debit", ascending=False)
    )
    fig = px.bar(debit_by_eff, x="category", y="total_debit")
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Saldo dzienne")
daily = (
    txs.assign(signed=lambda d: d["amount"] * d["direction"].map({"credit": 1, "debit": -1}))
    .groupby(txs["booking_date"].dt.date)["signed"]
    .sum()
    .reset_index()
)
fig2 = px.bar(daily, x="booking_date", y="signed")
st.plotly_chart(fig2, use_container_width=True)

st.subheader("Ostatnie transakcje")
display_cols = [
    "booking_date", "merchant", "title", "amount", "currency",
    "direction", "category_effective", "source",
]
st.dataframe(txs[display_cols].head(50), use_container_width=True)

# --- Active learning: manual category override -------------------------------
CATEGORIES = [
    "food", "transport", "subscriptions", "entertainment",
    "housing", "health", "savings", "salary", "transfer", "other",
]

st.subheader("✏️ Popraw kategorię (active learning)")
st.caption(
    "Filtruj transakcje wg słowa w merchant/title i ustaw poprawną kategorię. "
    "Po zapisie zmian możesz uruchomić retrain w panelu bocznym."
)
search = st.text_input("Filtruj (merchant/title):", "")

mask = pd.Series(True, index=txs.index)
if search.strip():
    s = search.lower().strip()
    mask = (
        txs["merchant"].fillna("").str.lower().str.contains(s)
        | txs["title"].fillna("").str.lower().str.contains(s)
    )
edit_df = txs[mask][[
    "id", "booking_date", "merchant", "title", "amount",
    "category", "category_predicted",
]].head(100).copy()

if edit_df.empty:
    st.info("Brak transakcji pasujących do filtra.")
else:
    edit_df["new_category"] = edit_df["category"].fillna(edit_df["category_predicted"])
    edited = st.data_editor(
        edit_df,
        use_container_width=True,
        hide_index=True,
        disabled=["id", "booking_date", "merchant", "title", "amount",
                  "category", "category_predicted"],
        column_config={
            "new_category": st.column_config.SelectboxColumn(
                "nowa kategoria", options=CATEGORIES, required=False,
            ),
        },
        key="category_editor",
    )

    if st.button("💾 Zapisz poprawki"):
        # Persist only rows where new_category differs from existing category.
        changes = edited[edited["new_category"].notna()]
        changes = changes[changes["new_category"] != changes["category"].fillna("")]
        ok, fail = 0, 0
        for _, row in changes.iterrows():
            try:
                resp = requests.patch(
                    f"{API_BASE_URL}/transactions/{int(row['id'])}/category",
                    json={"category": row["new_category"]},
                    timeout=10,
                )
                resp.raise_for_status()
                ok += 1
            except requests.exceptions.RequestException:
                fail += 1
        st.cache_data.clear()
        if ok:
            st.success(f"Zapisano {ok} zmian. Uruchom retrain z panelu bocznego.")
        if fail:
            st.error(f"Nie udało się zapisać {fail} zmian.")
        if ok == 0 and fail == 0:
            st.info("Brak zmian do zapisania.")
