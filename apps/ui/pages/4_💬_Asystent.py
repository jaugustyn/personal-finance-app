"""Asystent — chat z hybrydowym routerem (heurystyka + opcjonalnie Ollama)."""
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _auth  # noqa: E402, F401
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Asystent", page_icon="💬", layout="wide")
st.title("💬 Asystent finansowy")

# --- Sidebar -----------------------------------------------------------------
with st.sidebar:
    st.header("Ustawienia")
    use_llm_summary = st.checkbox(
        "Polerowanie odpowiedzi przez LLM",
        value=False,
        help="Wolniejsze, ale ładniejsze sformułowania. Wymaga Ollamy.",
    )

    st.markdown("---")
    st.subheader("Status Ollamy")
    try:
        h = requests.get(f"{API_BASE_URL}/chat/health", timeout=3).json()
        if h.get("ollama_available"):
            st.success("Ollama dostępna")
        else:
            st.warning("Ollama niedostępna — używam tylko heurystyki.")
    except requests.exceptions.RequestException:
        st.error("API nie odpowiada")

    st.markdown("---")
    st.caption(
        "Przykładowe pytania:\n"
        "- Ile wydałem w tym miesiącu?\n"
        "- Top sklepy w kwietniu 2026\n"
        "- Subskrypcje?\n"
        "- Anomalie w marcu 2026\n"
        "- Prognoza dla food\n"
        "- Porównaj ten miesiąc z poprzednim"
    )

    if st.button("🧹 Wyczyść historię"):
        st.session_state.pop("chat_history", None)
        st.rerun()

# --- History -----------------------------------------------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for turn in st.session_state.chat_history:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])
        if turn.get("meta"):
            with st.expander("Szczegóły"):
                st.json(turn["meta"])

# --- Input -------------------------------------------------------------------
prompt = st.chat_input("Zadaj pytanie po polsku…")
if prompt:
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"), st.spinner("Liczę…"):
        try:
            resp = requests.post(
                f"{API_BASE_URL}/chat",
                json={"question": prompt, "use_llm_summary": use_llm_summary},
                timeout=120 if use_llm_summary else 30,
            )
            resp.raise_for_status()
            payload = resp.json()
        except requests.exceptions.RequestException as exc:
            err = f"Błąd API: {exc}"
            st.error(err)
            st.session_state.chat_history.append(
                {"role": "assistant", "content": err}
            )
        else:
            ans = payload.get("answer", "(brak odpowiedzi)")
            tool = payload.get("tool")
            src = payload.get("source")
            st.markdown(ans)
            badge = f"źródło: `{src}`" + (f" • narzędzie: `{tool}`" if tool else "")
            st.caption(badge)
            meta = {
                "tool": tool,
                "tool_args": payload.get("tool_args"),
                "source": src,
                "data": payload.get("data"),
            }
            with st.expander("Szczegóły"):
                st.json(meta)
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": ans + f"\n\n*{badge}*",
                "meta": meta,
            })
