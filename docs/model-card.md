# Model Card — Klasyfikator transakcji bankowych

> Standard model-card wg Mitchell et al., 2019 (FAccT). Szablon dostosowany do
> klasyfikatora wbudowanego w pracę magisterską „Personal Finance ML”.

## 1. Szczegóły modelu

| Pole             | Wartość                                                                                       |
| ---------------- | --------------------------------------------------------------------------------------------- |
| **Nazwa**        | `classifier_linear_svc`                                                                       |
| **Wersja**       | 0.1.0 (faza 3)                                                                                |
| **Architektura** | TF-IDF (char 3-5 + word 1-2) + numeryczne (`abs_amount`, `day_of_week`) → `LinearSVC` (C=1.0) |
| **Pipeline**     | `src/finance/ml/classification/pipeline.py::build_pipeline`                                   |
| **Train script** | `python -m finance.ml.classification.train --from-files data/...`                             |
| **Artefakt**     | `data/models/classifier_latest.joblib`                                                        |
| **Autor**        | Jakub \*\*\* (praca magisterska, WSEI Kraków, 2026)                                           |
| **Licencja**     | MIT (kod), dane treningowe — prywatne                                                         |

## 2. Zamierzony użytek

- **Primary:** sugestia kategorii wydatkowej dla transakcji bankowych (PL/EN
  merchant strings) na 8 kategorii zgodnie z ontologią użytkownika.
- **Secondary:** sugestia kategorii w UI z poziomem pewności.
- **Out of scope:**
  - decyzje kredytowe / scoring,
  - profilowanie behawioralne,
  - wykrywanie przelewów/przychodów jako kategorii ML (`transaction_type` i
    `is_transfer` są osobną warstwą regułową),
  - klasyfikacja transakcji w innych walutach niż PLN (eksperymentalne).

## 3. Dane treningowe

| Pole            | Wartość                                                                                               |
| --------------- | ----------------------------------------------------------------------------------------------------- |
| **Źródła**      | CSV: Pekao SA, Revolut                                                                                |
| **Okres**       | 2024-01 – 2026-04                                                                                     |
| **Wielkość**    | ~3 800 transakcji, ~2 200 oznakowanych ręcznie                                                        |
| **Klasy**       | food, transport, housing, health, savings, subscriptions, entertainment, other                        |
| **Augmentacja** | `finance.ml.classification.augment` (LLM Llama 3.1 8B) — synthetic merchant strings dla rzadkich klas |
| **Train/test**  | StratifiedKFold (5-fold), MIN_PER_CLASS=2                                                             |

### Charakterystyka

- Nierównowaga: dominuje `food`; `savings` i `health` mają niski support.
- Przelewy, wynagrodzenia i zwroty są wyłączane z ontologii wydatków i
  oznaczane w warstwie `transaction_type`; przelewy własne dodatkowo mają
  `is_transfer`.
- Klasy poniżej 2 % udziału (`savings`, `health`) augmentowane do ~5 %.
- Język: ~90 % polskie merchant strings, ~10 % angielskie (Revolut).

### Pre-processing

- Lowercase, strip diacritics tylko w analyzerze TF-IDF.
- Brak stop-listy (krótkie merchant strings) — testowane, pogarsza F1.
- `abs_amount` standaryzowane (`StandardScaler`).

## 4. Metryki ewaluacyjne

StratifiedKFold, 5 splitów. Estymator wybrany: `linear_svc`. Raporty generowane
przez `scripts/build_ml_evidence.py` zawierają też baseline
`dummy_most_frequent`, confusion matrix, confidence curve dla progów akceptacji
oraz porównanie real-only vs augmented.

| Estymator    | Macro-F1 | Weighted-F1 |
| ------------ | -------- | ----------- |
| `linear_svc` | **0.78** | 0.84        |
| `logreg`     | 0.75     | 0.82        |
| `rf`         | 0.69     | 0.78        |

Per-class F1 (linear_svc, agregat 5 foldów):

| Klasa         | F1   | Support |
| ------------- | ---- | ------- |
| food          | 0.91 | 770     |
| transport     | 0.86 | 290     |
| housing       | 0.78 | 180     |
| subscriptions | 0.81 | 95      |
| entertainment | 0.72 | 120     |
| health        | 0.68 | 70      |
| savings       | 0.66 | 55      |
| other         | 0.61 | 210     |

> _Wartości orientacyjne — odtwórz z `data/reports/classification\__.json` po
> ponownym treningu na własnym datasecie.\*

## 5. Ograniczenia i ryzyka

- **OOV merchanty** — nowy bank/sklep z nietypową nazwą → niski confidence,
  fallback do LLM (ADR-0002).
- **Drift** — sezonowość świąteczna i zmiana nazewnictwa merchantów (np. po
  rebrandzie). Mitygacja: re-train co 3–6 miesięcy.
- **Klasa `other`** to „śmietnik” — nie jest interpretowalna jako kategoria
  budżetowa. Unikać prezentowania jej w analizach trendu.
- **Bias geograficzny** — model uczony na transakcjach jednego użytkownika
  (Polska, Kraków). Generalizacja na inne miasta/kraje nieznana.
- **Privacy** — model artefakt nie zawiera surowych transakcji, ale TF-IDF
  vocabulary potencjalnie ujawnia merchantów. Nie udostępniać artefaktu
  publicznie.

## 6. Etyka i fairness

Aplikacja jest narzędziem osobistym (single-user). Brak decyzji wobec osób
trzecich, brak ryzyka dyskryminacji w sensie ML fairness. Augmentacja LLM:

- prompt nie generuje danych osobowych (wymóg w `_build_prompt`),
- generowane stringi są fikcyjne (random merchant + lokalizacja).

## 7. Reproducibility

```bash
python -m finance.ml.classification.train \
    --from-files data/raw/*.csv \
    --augment data/synthetic/augmented.csv \
    --persist linear_svc
```

Seed: `random_state=42` w `StratifiedKFold`. Wersje bibliotek: zob.
`pyproject.toml` i lockfile frontendu `apps/web/package-lock.json`.
