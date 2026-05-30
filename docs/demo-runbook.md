# Clean-Start Demo Runbook

Ten runbook opisuje finalną walidację projektu na świeżej bazie. Nie zawiera
surowych danych i nie powinien trafiać do niego żaden eksport bankowy.

## 1. Czysty start

Operacja usunięcia volume jest destrukcyjna. Wykonać ją tylko wtedy, gdy bieżąca
baza może zostać utracona.

```powershell
docker compose -f docker/docker-compose.yml down -v
docker compose -f docker/docker-compose.yml up -d --build
```

API uruchamia `alembic upgrade head` przy starcie kontenera, więc świeża baza
powinna mieć wszystkie migracje, w tym `category_suggestion_rejected`.

Smoke:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/transactions
```

Jeżeli BasicAuth jest włączony, użyć użytkownika i hasła z `.env`.

## 2. Import i review kategorii

1. Otworzyć Next.js: <http://localhost:3000>.
2. Wejść w `/imports`, załadować realny eksport bankowy i potwierdzić mapping.
3. Po imporcie odczekać kilka sekund na background suggestions.
4. Wejść w `/transactions` → `Do przypisania`.
5. Sprawdzić:
   - typy transakcji (`purchase`, `own_transfer`, `person_transfer`, `salary`,
     `refund`, `cash_withdrawal`, `bank_fee`, `savings_investment`),
   - `is_transfer` dla przelewów własnych,
   - sugestie ML i confidence,
   - accept/reject sugestii.
6. Ręcznie oznaczyć seed treningowy. Cel praktyczny: kilkadziesiąt przykładów
   na kategorię, a dla rzadkich klas tyle, ile realnie występuje.

Nie traktować `category_predicted` jako etykiety treningowej, dopóki użytkownik
jej nie zaakceptuje albo ręcznie nie przypisze kategorii.

## 3. Retraining i reclassify

Z poziomu API docs albo curl:

```powershell
curl -X POST "http://localhost:8000/ml/retrain?estimator=linear_svc"
curl -X POST "http://localhost:8000/ml/reclassify"
```

Po reclassify wrócić do `/transactions` → `Do przypisania` i sprawdzić, czy
nowe sugestie są sensowne. Błędne sugestie odrzucać, nie akceptować.

## 4. Pakiet ML evidence

Po etykietowaniu i retrainingu uruchomić lokalnie:

```powershell
.\.venv\Scripts\python.exe scripts\build_ml_evidence.py --from-db
.\.venv\Scripts\python.exe scripts\inspect_report.py --strict
```

Jeżeli baza działa pod innym URL:

```powershell
.\.venv\Scripts\python.exe scripts\build_ml_evidence.py `
  --from-db `
  --database-url "postgresql+psycopg://finance:finance@localhost:5432/finance"
```

Następnie uzupełnić prywatny review anomalii:

```powershell
.\.venv\Scripts\python.exe scripts\build_ml_evidence.py `
  --from-db `
  --review-file data/private/latest_anomaly_review.csv
.\.venv\Scripts\python.exe scripts\inspect_report.py --strict
```

Do pracy i prezentacji cytować tylko:

- `data/reports/summary.md`,
- `data/reports/latest_classification.json`,
- `data/reports/latest_eda.json`,
- `data/reports/latest_forecasting.json`,
- `data/reports/latest_anomaly_summary.json`,
- `data/reports/privacy_check_latest.json`.

`data/private/latest_anomaly_review.csv` zostaje lokalnie.

## 5. Scenariusz demo

1. Dashboard: KPI, cashflow, kategorie, top merchantów.
2. Import: preview, mapping, wynik importu i deduplikacja.
3. Transakcje: tryb `Do przypisania`, accept/reject sugestii, ręczna kategoria.
4. ML: retrain, reclassify, confidence threshold.
5. Forecast: miesięczna prognoza wydatków.
6. Anomalie: severity i powody flagowania.
7. Subskrypcje: koszt miesięczny i confidence.
8. Asystent: pytanie po polsku, np. `Co mogę ograniczyć w kwietniu 2026?`.

## 6. Kryteria gotowości

- `ruff check .`, `pytest`, `mypy src/finance apps` przechodzą.
- Frontend: `npm run lint`, `npx tsc --noEmit`, `npm run build` przechodzą.
- `inspect_report.py --strict` nie zgłasza brakujących raportów ani wycieku
  raw merchant/title.
- `linear_svc` jest lepszy od `dummy_most_frequent`.
- Anomalie mają ręcznie uzupełnione `precision@20` albo jasno opisany brak
  review.
