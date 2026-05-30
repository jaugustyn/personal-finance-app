"""LLM-driven data augmentation for under-represented classes.

Uses a local Ollama model (default: llama3.1:8b-instruct-q4_K_M) to generate
realistic Polish bank-transaction descriptions for rare categories. Output is
written as a CSV that the training script can load alongside real data.

CLI:
    python -m finance.ml.classification.augment \\
        --classes health housing savings \\
        --per-class 15 \\
        --out data/synthetic/augmented.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
import re
import sys
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import ollama

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama3.1:8b-instruct-q4_K_M"
DEFAULT_OUT = Path("data/synthetic/augmented.csv")

# Seed examples per category — guide the model's distribution.
SEED_EXAMPLES: dict[str, list[str]] = {
    "health": [
        "APTEKA DR.MAX KRAKOW",
        "MEDICOVER WARSZAWA wizyta",
        "LUX MED diagnostyka",
        "DOZ APTEKA ul. Floriańska",
    ],
    "housing": [
        "IKEA KRAKOW",
        "LEROY MERLIN BIELANY",
        "CASTORAMA wyposażenie",
        "JYSK meble",
    ],
    "savings": [
        "Przelew na konto oszczędnościowe",
        "Lokata Standard 3M",
        "Zakup obligacji EDO",
        "ETF iShares Core S&P 500 — zlecenie",
    ],
    "subscriptions": [
        "ORANGE FLEX",
        "Netflix.com subskrypcja",
        "Spotify Premium",
        "OpenAI ChatGPT Plus",
    ],
    "entertainment": [
        "Multikino Krakow Bonarka",
        "Empik ul. Grodzka książki",
        "Steam games",
        "PlayStation Store",
    ],
    "transport": [
        "ORLEN STACJA paliw",
        "BP Kraków paliwo",
        "MPK Kraków bilet",
        "Bolt Polska przejazd",
    ],
    "food": [
        "BIEDRONKA",
        "LIDL bochnia",
        "CARREFOUR Krakow",
        "Glovo zamowienie",
    ],
    "other": [
        "Allegro zakup",
        "ZUS skladka",
        "InPost paczkomat",
        "Poczta Polska oplata",
    ],
}

# Realistic amount ranges (PLN, abs value) per category.
AMOUNT_RANGES: dict[str, tuple[float, float]] = {
    "health": (15.0, 350.0),
    "housing": (50.0, 2500.0),
    "savings": (100.0, 5000.0),
    "subscriptions": (9.99, 80.0),
    "entertainment": (15.0, 400.0),
    "transport": (3.40, 350.0),
    "food": (5.0, 300.0),
    "other": (10.0, 500.0),
}


def _build_prompt(category: str, n: int) -> str:
    examples = SEED_EXAMPLES.get(category, [])
    seed = "\n".join(f"- {e}" for e in examples) or "- (brak — wygeneruj wiarygodne)"
    return PROMPT_TEMPLATE.format(n=n, category=category, examples=seed)


_NUMBERED_LINE_RE = re.compile(r"^\s*\d+[\.)-]?\s*")
_PREAMBLE_RE = re.compile(
    r"^(oto|tutaj|here|poniżej|ponizej|lista|przykłady|przyklady)\b",
    re.I,
)
_META_LINE_RE = re.compile(
    r"(realistyczn|opis|transakcj|kategorii|category|wygenerowa|poniżej|ponizej)",
    re.I,
)


def _parse_lines(text: str) -> list[str]:
    """Strip bullets / numbering / quotes from generated lines, drop preamble."""
    out: list[str] = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        # Drop leading "1.", "1)", "-", "*", "•", or quotes.
        for prefix in ("- ", "* ", "• "):
            if s.startswith(prefix):
                s = s[len(prefix):]
        s = _NUMBERED_LINE_RE.sub("", s)
        s = s.strip().strip('"').strip("'").strip()
        if not s or len(s) > 120:
            continue
        # Heuristic: drop conversational preambles ("Oto 5 ...", "Tutaj masz ...",
        # "Here are ...") or lines that contain the literal category name in quotes.
        low = s.lower()
        if _PREAMBLE_RE.search(low):
            continue
        if _META_LINE_RE.search(low) and (":" in low or '"' in low):
            continue
        if s.endswith(":"):
            continue
        out.append(s)
    return out


PROMPT_TEMPLATE = """Jesteś generatorem syntetycznych opisów transakcji bankowych w języku polskim.

Wygeneruj DOKŁADNIE {n} realistycznych opisów dla kategorii "{category}". Opisy mają wyglądać jak \
prawdziwe stringi z wyciągu polskiego banku (Pekao SA / Revolut): nazwa sklepu/usługi, \
miasto lub ulica, numer terminala POS, ewentualnie skrócone notatki transferu.

Przykłady (dla inspiracji, NIE kopiuj ich dosłownie):
{examples}

Wymagania:
- Każdy opis w osobnej linii.
- BEZ wstępu, bez "Oto:", bez podsumowania, bez numerów porządkowych, bez cudzysłowów, bez markdown.
- Pierwsza linia to JUŻ pierwszy opis.
- Mieszaj wielkość liter tak, jak robią to terminale POS (np. CARREFOUR, lidl, Biedronka).
- Czasem dodaj polskie znaki (ż, ł, ą, ę), czasem nie.
- Każdy opis 2–8 słów.
- Tylko {n} linii w odpowiedzi.
"""


def generate_for_category(
    category: str,
    n: int,
    *,
    model: str = DEFAULT_MODEL,
    host: str | None = None,
    temperature: float = 0.85,
) -> list[str]:
    client = ollama.Client(host=host) if host else ollama
    prompt = _build_prompt(category, n)
    resp = client.generate(
        model=model,
        prompt=prompt,
        options={"temperature": temperature, "top_p": 0.95, "num_predict": 400},
    )
    text = resp["response"] if isinstance(resp, dict) else resp.response
    lines = _parse_lines(text or "")
    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for line in lines:
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(line)
    return unique[:n]


def _synthetic_row(category: str, text: str, rng: random.Random) -> dict[str, object]:
    lo, hi = AMOUNT_RANGES.get(category, (10.0, 500.0))
    amount = round(rng.uniform(lo, hi), 2)
    days_back = rng.randint(0, 180)
    booking_date = date.today() - timedelta(days=days_back)
    return {
        "merchant": text,
        "title": "",
        "text": text,
        "abs_amount": amount,
        "amount": -Decimal(str(amount)),
        "currency": "PLN",
        "direction": "debit",
        "category": category,
        "raw_category": "synthetic",
        "source": "synthetic",
        "booking_date": booking_date.isoformat(),
        "day_of_week": booking_date.weekday(),
    }


def augment(
    classes: list[str],
    per_class: int,
    out_path: Path,
    *,
    model: str = DEFAULT_MODEL,
    host: str | None = None,
    seed: int = 42,
) -> int:
    rng = random.Random(seed)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for cat in classes:
        logger.info("Generating %d examples for class=%s ...", per_class, cat)
        t0 = time.time()
        try:
            lines = generate_for_category(cat, per_class, model=model, host=host)
        except Exception as exc:  # noqa: BLE001 — we want to log and continue
            logger.error("Ollama failed for class=%s: %s", cat, exc)
            continue
        if not lines:
            logger.warning("Model returned no usable lines for class=%s", cat)
            continue
        logger.info("  -> %d lines in %.1fs", len(lines), time.time() - t0)
        for line in lines:
            rows.append(_synthetic_row(cat, line, rng))

    if not rows:
        logger.error("No synthetic rows generated.")
        return 0

    fieldnames = list(rows[0].keys())
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    logger.info("Wrote %d rows to %s", len(rows), out_path)
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--classes", nargs="+", required=True,
                   help="Categories to augment (e.g. health housing savings)")
    p.add_argument("--per-class", type=int, default=15)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL))
    p.add_argument("--host", default=os.environ.get("OLLAMA_HOST"))
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    n = augment(args.classes, args.per_class, args.out,
                model=args.model, host=args.host, seed=args.seed)
    print(json.dumps({"rows": n, "out": str(args.out), "model": args.model}, indent=2))
    return 0 if n > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
