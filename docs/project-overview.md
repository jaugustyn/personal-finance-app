# Personal Finance ML — Project Overview

> Briefing dla osoby, która widzi projekt pierwszy raz. Skondensowany przegląd
> celu, architektury, decyzji projektowych i statusu prac. Do przedstawienia w
> ~10 min rozmowy.

## 1. Cel projektu (one-liner)

**Self-hosted system do analizy i optymalizacji wydatków osobistych z
wykorzystaniem klasycznego ML i lokalnego LLM.**

Praca magisterska — WSEI Kraków, 2026, Informatyka Stosowana, II stopień.
Zakres: end-to-end aplikacja od ingest CSV z banków, przez ML (klasyfikacja,
detekcja anomalii, prognozowanie, detekcja abonamentów), aż po
produkcyjny dashboard webowy + asystenta NLP.

### Hipotezy badawcze

1. Hybrydowa klasyfikacja (TF-IDF + LinearSVC z fallbackiem do LLM dla
   niskiego confidence) osiąga macro-F1 ≥ 0.75 na rzeczywistym datasecie ~2k
   oznakowanych transakcji, przy zachowaniu p99 latencji <200 ms (bez LLM
   fallback).
2. Augmentacja LLM rzadkich klas mierzalnie poprawia F1 dla under-represented
   kategorii (`health`, `housing`, `savings`).
3. Hybrydowa detekcja anomalii (IsolationForest na cechach liczbowych +
   robust z-score median/MAD per kategoria + reguły) daje dobre precision@20,
   a jednocześnie zachowuje czytelne uzasadnienia w UI.
4. Klasyczne metody prognozowania (Naive / Mean / SES / ARIMA) na
   miesięcznych szeregach kategorii są wystarczające dla krótkiej historii
   transakcji bez dokładania ciężkich zależności typu Prophet.

## 2. Stos technologiczny

| Warstwa | Technologia |
|---|---|
| Backend API | **FastAPI 0.115** + Pydantic v2 + SQLAlchemy 2.0 + Alembic |
| Baza danych | **PostgreSQL** (prod) / SQLite (testy) |
| ML | scikit-learn 1.5 (LinearSVC, LogReg, RF, IsolationForest), statsmodels |
| LLM | **Ollama** (Llama 3.1 8B Instruct Q4_K_M) — lokalnie |
| Web frontend | **Next.js 16** (App Router) + React 19 + TypeScript strict + Tailwind v4 + TanStack Query v5 + Recharts |
| Tooling frontend | shadcn-lite UI kit (button/card/input/table/badge), lucide-react, next-themes |
| Streamlit lab | workflow ML developera + chat asystent (nie główne UI) |
| Obserwowalność | structlog (JSON) + `X-Request-ID` + health/readiness endpoints |
| Scheduler | APScheduler (in-process, retraining nocą) |
| Auth | HTTP Basic (single-user, self-hosted) |
| Konteneryzacja | Docker Compose (api / web / ui / postgres) |
| CI | GitHub Actions: ruff + mypy + pytest + tsc + eslint + pip-audit + npm audit |
| Dependencies | Dependabot (weekly) |

## 3. Architektura wysokopoziomowa

```
                          ┌─────────────────────┐
                          │  Next.js 16 (web)   │  ← główne UI (port 3000)
                          │  + Streamlit (ui)   │  ← asystent + admin (8501)
                          └──────────┬──────────┘
                                     │ HTTP + BasicAuth (proxy w Next)
                          ┌──────────▼──────────┐
                          │   FastAPI (api)     │  port 8000
                          │  ──────────────     │
                          │  • routers/         │
                          │  • middleware:      │
                          │     - Logging       │
                          │     - SecurityHdrs  │
                          │     - RateLimit     │
                          │     - CORS          │
                          └──────────┬──────────┘
                                     │ SQLAlchemy
                ┌────────────────────┼────────────────────┐
                ▼                    ▼                    ▼
        ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
        │  PostgreSQL  │    │  src/finance │    │   Ollama     │
        │              │    │  ──────────  │    │  (host net)  │
        │  transactions│    │  ingestion/  │    │  llama3.1:8b │
        │  imports     │    │  domain/     │    └──────────────┘
        │  assets      │    │  ml/         │
        │  categories  │    │   ├ classification (SVC + augment)
        └──────────────┘    │   ├ anomaly       (IsolationForest + z-score)
                            │   ├ forecasting   (naive/mean/SES/ARIMA)
                            │   └ subscriptions (period detector)
                            │  llm/         │
                            │  observability│
                            └──────────────┘
```

### Kluczowe katalogi

```
apps/api/         FastAPI backend (routers, middleware, scheduler, security)
apps/web/         Next.js dashboard (App Router, /transactions, /forecast, ...)
apps/ui/          Streamlit (asystent + admin workflows)
src/finance/      Importowalny pakiet — używany przez api, ui i CLI
  ingestion/        Parsery CSV: Pekao, Revolut, generic, nordigen (PoC)
  domain/           SQLAlchemy models, Pydantic DTOs, enums
  ml/
    classification/   pipeline.py, train.py, augment.py, predict.py, registry.py
    anomaly/          IsolationForest + robust z-score + reguły
    forecasting/      Naive, Mean, SES, ARIMA + walk-forward CV
    subscriptions/    detector kadencji 7/30/90/365 dni
  llm/              Klient Ollama, prompty, tool calls
  observability.py  structlog config
docs/
  adr/              Architecture Decision Records (4)
  observability/    lightweight logs/health README
  ml-evidence.md    powtarzalne raporty ML + prywatność wyników
  model-card.md     Model Card (Mitchell et al. format)
tests/            150+ testów, ~75%+ coverage
data/             runtime/private artifacts: models, reports, raw exports (gitignored)
notebooks/        EDA / PoC / porównania badawcze
scripts/          smoke/debug helpers
```

### Granice repozytorium

- **Production demo path**: `apps/web` → `/api/proxy/*` → `apps/api` →
  `src/finance` → PostgreSQL.
- **Lab/research path**: `apps/ui`, `notebooks/`, `scripts/`,
  `src/finance/ingestion/nordigen.py`.
- **Artefakty runtime**: `data/models/`, `data/reports/`, `coverage.xml`,
  cache i build frontendu są generowane lokalnie i gitignored.
- **Dane prywatne**: rzeczywiste eksporty bankowe trzymać w `data/raw/`,
  `data/private/` albo poza repo.

## 4. Kluczowe decyzje projektowe (ADR)

| # | Decyzja | Plik |
|---|---|---|
| 0001 | Integracja PSD2 / GoCardless — **DEFERRED** poza zakres tezy. CSV jest powtarzalny i wystarczający dla wniosków naukowych. | [`docs/adr/0001-nordigen.md`](adr/0001-nordigen.md) |
| 0002 | **Hybrydowy klasyfikator**: TF-IDF + LinearSVC jako pierwszy, LLM (Ollama) jako fallback dla niskiego confidence. Augmentacja LLM rzadkich klas. | [`docs/adr/0002-hybrid-classifier.md`](adr/0002-hybrid-classifier.md) |
| 0003 | **Hybrydowa detekcja anomalii**: IsolationForest + robust z-score + reguły, oraz abonamenty przez period detection. Powód: skuteczność + interpretowalne uzasadnienia. | [`docs/adr/0003-anomaly-subscription-detection.md`](adr/0003-anomaly-subscription-detection.md) |
| 0004 | **structlog + health checks**, **bez Prometheus/OpenTelemetry**. Self-hosted single-node nie potrzebuje osobnego stosu metryk. | [`docs/adr/0004-observability.md`](adr/0004-observability.md) |

## 5. ML — co i jak

### 5.1 Klasyfikacja transakcji

**Wejście**: merchant + title + abs_amount + day_of_week.
**Wyjście ML**: sugestia jednej z 8 kategorii wydatkowych (`food`,
`transport`, `housing`, `health`, `savings`, `subscriptions`,
`entertainment`, `other`) wraz z confidence. Typ przepływu pieniędzy jest
osobną warstwą `transaction_type` (`purchase`, przelew własny/do osoby,
wynagrodzenie, zwrot, wypłata gotówki, opłata bankowa, oszczędności/inwestycje),
żeby nie zanieczyszczać ontologii wydatków.

- **Pipeline**: `ColumnTransformer` (TF-IDF char 3-5 + word 1-2 na text;
  `StandardScaler` na numerycznych) → `LinearSVC(C=1.0)`.
- **Baseline**: `DummyClassifier(strategy="most_frequent")` w raportach
  `classification_*.json`, żeby jasno pokazać zysk względem trywialnego modelu.
- **Trening**: `python -m finance.ml.classification.train --from-files ...
  --persist linear_svc` → `data/models/classifier_latest.joblib`.
- **Augmentacja LLM**: `augment.py` generuje syntetyczne merchant strings dla
  rzadkich klas używając Ollamy (`SEED_EXAMPLES` per kategoria, `AMOUNT_RANGES`).
- **Ewaluacja**: 5-fold StratifiedKFold, macro-F1 + weighted-F1 + per-class
  report + confusion matrix → `data/reports/classification_*.json`.
- **Evidence package**: `scripts/build_ml_evidence.py` generuje real-only vs
  augmented, EDA, forecasting CV i publiczny summary anomalii; prywatny review
  top anomalii trafia do `data/private/`.
- **Predykcja w runtime**: `predict.py::predict_one` → jeśli `confidence >= τ`
  (0.55) zwraca SVC; inaczej fallback do LLM.

Wyniki orientacyjne (zob. `docs/model-card.md`):

| Estymator | Macro-F1 | Weighted-F1 |
|---|---|---|
| linear_svc | **0.78** | 0.84 |
| logreg | 0.75 | 0.82 |
| rf | 0.69 | 0.78 |

### 5.2 Detekcja anomalii (`finance.ml.anomaly`)

Detektor hybrydowy: IsolationForest na prostych cechach liczbowych
(`log_abs`, dzień tygodnia/miesiąca, częstotliwość merchanta, kierunek),
robust z-score median/MAD per (`category`, `direction`) oraz reguła
„nowy merchant + duża kwota”. UI pokazuje `severity` i powody po polsku, więc
wynik pozostaje interpretowalny mimo użycia IsolationForest.

### 5.3 Prognozowanie (`finance.ml.forecasting`)

Walk-forward CV po szeregach miesięcznych per kategoria. Modele:
`Naive` (last value), `Mean(window)`, `SES`, `ARIMA`. Wybór
najlepszego po RMSE. `forecast_best(series, horizon)` zwraca `ForecastResult`
z metrykami MAPE/RMSE i prognozą N-miesięczną.

### 5.4 Detekcja abonamentów (`finance.ml.subscriptions`)

Dla znormalizowanej nazwy merchanta: medianowy odstęp między transakcjami,
tolerancja kwoty ±10 %, domyślnie minimum 2 wystąpienia w krótkim oknie danych
→ zwraca kadencję (weekly/biweekly/monthly/yearly) + confidence + miesięczny
koszt.

### 5.5 Asystent LLM (`apps/api/routers/chat.py`)

Hybryda: heurystyczny router PL (intencje: „ile wydałem na X”, „pokaż
abonamenty”, „prognoza”, „anomalie”) → wywołanie odpowiedniej funkcji domeny.
LLM (Ollama) używany do *polish & rephrase* odpowiedzi i jako fallback dla
zapytań niezakwalifikowanych przez heurystykę. To nie jest czysty RAG do
twardych faktów liczbowych; fakty pochodzą z funkcji domenowych, a LLM tylko
routuje albo wygładza odpowiedź.

## 6. Bezpieczeństwo i obserwowalność

**Bezpieczeństwo**:
- HTTP Basic auth (włączane przez env `AUTH_USERNAME` / `AUTH_PASSWORD`).
- `SecurityHeadersMiddleware`: CSP, X-Frame-Options DENY, nosniff,
  Referrer-Policy, Permissions-Policy.
- CSV import: limit 10 MiB, allowlist rozszerzeń + MIME, walidacja pustego pliku.
- CSV export: escaping formula injection (CWE-1236) — prefix `'` dla cell
  zaczynających się od `=`, `+`, `-`, `@`, `\t`, `\r`.
- Rate limit per IP (sliding window, in-memory).
- CORS configurable przez `CORS_ALLOW_ORIGINS`.
- Zależności: pip-audit + npm audit w CI (non-blocking), Dependabot weekly.

**Obserwowalność**:
- structlog → JSON do stdout, korelacja po `request_id` (header `X-Request-ID`
  echo'd).
- Health: `/health` (publiczny, db + ollama), `/health/live`, `/health/ready`
  (k8s-style).
- Brak `/metrics`, Prometheusa i Grafany — świadomie, żeby nie zwiększać
  złożoności self-hosted single-user demo.

## 7. Testy i jakość kodu

- **150+ testów pytest**, coverage **~75%+** (gate 60%).
- Layers: unit (parsers, ML helpers), API (routers + middleware), property-based
  (Hypothesis dla CSV preview), security (oversize/MIME/injection), ML
  pipelines (synthetic dataset, walk-forward CV).
- **Frontend**: `tsc --noEmit` clean, `eslint` clean.
- **Lint backend**: `ruff` (E, F, I, UP, B, SIM) clean. `mypy` non-blocking w CI.
- **CI**: GitHub Actions — lint+test+build+audit na każdy PR i push do main.

## 8. Status pracy (Phase 1–10)

| Faza | Zakres | Status |
|---|---|---|
| 1 | Ingestion (Pekao + Revolut), API, podstawowe UI, Docker, CI | ✅ |
| 2 | ML klasyfikacja (TF-IDF + LinearSVC), augmentacja LLM, Nordigen PoC | ✅ |
| 3 | Forecasting miesięczny, anomalie, detekcja abonamentów | ✅ |
| 4 | Hybrydowy LLM asystent (PL router + Ollama tool-calling) | ✅ |
| 5 | BasicAuth, structlog, scheduler, healthcheck, 10-min setup | ✅ |
| 6 | Next.js 16 dashboard (KPI, cashflow, transactions, forecast, anomalies, subs) | ✅ |
| Hardening | CSV security, security headers, request logging, ADRs, model card | ✅ |
| 7 | ML evidence, confidence calibration, service/module refactors | ✅ |
| 8 | ML/AI backend hardening: classifier diagnostics, fallback gating, anomaly/forecast/subscription regressions | ✅ |
| 9 | Category review workflow: filters, suggestion accept/reject, deterministic savings recommendations | ✅ |
| 10 | Clean-start validation, fresh ML evidence, anomaly review, defence demo runbook | ⏳ |

## 9. Świadome trade-offs (tematy do dyskusji)

- **Single-user, self-hosted** — brak multi-tenancy, brak OAuth, brak email
  notyfikacji. Świadome — zakres pracy magisterskiej, nie SaaS.
- **PostgreSQL only** — `ON CONFLICT` w ingest. SQLite tylko do testów.
- **Brak distributed tracing** — patrz ADR-0004. Single-node + request-id wystarczy.
- **LLM tylko lokalnie (Ollama)** — privacy + brak kosztów. Odpowiedzi
  wolniejsze niż OpenAI API, ale akceptowalne (UX nie jest blocking — chat to
  asynchroniczne pytanie).
- **Brak fine-tuningu** transformera — mały dataset (~2k labelled), TF-IDF +
  SVC + augmentacja LLM dają porównywalne wyniki przy 100× mniejszym
  artefakcie i 0 GPU wymaganych.
- **Brak automatycznych reguł merchant → category definiowanych przez usera** —
  katalog kategorii istnieje, ale reguły dopasowania są poza zakresem.

## 10. Dane wejściowe (rzeczywiste)

- **Pekao SA** — ~2 lata historii, główne konto operacyjne.
- **Revolut** — konta multi-walutowe (PLN, USD), ~1 rok historii.
- Łącznie: ~3 800 transakcji, ~2 200 oznakowanych ręcznie do treningu.
- Nierównowaga klas: `food` dominuje, a `savings`/`health` są rzadkie
  → uzasadnia augmentację LLM. Przepływy typu przelew własny/do osoby,
  wynagrodzenie i zwroty są oznaczane w `transaction_type`, nie jako klasy
  modelu wydatkowego.

## 11. Najbardziej "thesis-worthy" rzeczy do pokazania

1. **Hybrydowa klasyfikacja z fallbackiem LLM** (ADR-0002) + Model Card.
2. **Walk-forward CV** dla forecastingu (autoselekcja modelu po RMSE).
3. **Hybrydowa detekcja anomalii**: IsolationForest + robust z-score + reguły,
   z interpretowalnymi powodami w UI.
4. **Augmentacja LLM rzadkich klas** — pomiar wpływu na macro-F1.
5. **Pragmatyczny DevOps**: Docker Compose + GitHub Actions + Dependabot +
   pip-audit + health checks + structured logs.
6. **150+ testów / ~75%+ coverage / property-based** — argument o jakości kodu.

## 12. Pliki do otwarcia podczas prezentacji (kolejność)

1. `README.md` — quick start.
2. `docs/project-overview.md` — ten dokument.
3. `docs/adr/0002-hybrid-classifier.md` — kluczowa decyzja ML.
4. `docs/model-card.md` — fairness/limitations/metrics.
5. `src/finance/ml/classification/pipeline.py` — TF-IDF + numeric pipeline.
6. `src/finance/ml/classification/train.py::evaluate` — walk-forward CV.
7. `apps/api/main.py` — middleware stack.
8. `apps/web/src/app/page.tsx` — dashboard główny.
9. `docs/observability/README.md` — minimalna obserwowalność bez Prometheusa.

## 13. URL-e (przy uruchomionym `docker compose up`)

| Co | URL |
|---|---|
| Web (Next.js) | <http://localhost:3000> |
| API + Swagger | <http://localhost:8000/docs> |
| Streamlit (asystent) | <http://localhost:8501> |
| Health (publiczny) | <http://localhost:8000/health> |
| Postgres | localhost:5432 (db `finance`) |
| Ollama (host) | localhost:11434 |

## 14. Ile to "kosztuje"

- ~7 000 LOC Python + ~4 000 LOC TS/TSX (backend + frontend + tests).
- ~2 GB RAM dla pełnego stacku (api 200 MB, web 300 MB, postgres 100 MB,
  Ollama 5 GB przy wczytanym modelu — host).
- Cold start ~10 sekund (Postgres → API → Web). Predict latency: <50 ms (SVC),
  ~500–2000 ms (LLM fallback, lokalnie).
