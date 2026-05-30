# ML Evidence Package

Cel tego pakietu to zebrać powtarzalne, agregatowe dowody jakości modeli bez
commitowania surowych danych bankowych. Surowe CSV, artefakty modeli i prywatny
review anomalii zostają lokalnie w `data/raw/`, `data/models/` i
`data/private/`.

## Co generować

```bash
python scripts/build_ml_evidence.py --from-db
```

Jeżeli lokalna baza używa innych danych dostępowych niż konfiguracja aplikacji:

```bash
python scripts/build_ml_evidence.py \
  --from-db \
  --database-url postgresql+psycopg://user:password@localhost:5432/finance
```

Opcjonalnie z augmentacją:

```bash
python scripts/build_ml_evidence.py \
  --from-db \
  --augment data/synthetic/augmented.csv
```

Skrypt zapisuje:

- `data/reports/classification_*.json` — real-only oraz opcjonalnie augmented,
  baseline `dummy_most_frequent`, `logreg`, `linear_svc`, `random_forest`,
  macro-F1, weighted-F1, per-class metrics i confusion matrix. Raport zawiera
  też eksperymentalne porównanie `feature_v2` (`merchant_norm`,
  `transaction_type`, `source`, amount bucket, month), ale produkcyjny model
  pozostaje na bazowym pipeline do czasu przeglądu wyników.
- `data/reports/eda_*.json` — bezpieczne agregaty do wizualizacji: rozkłady
  kategorii, cashflow miesięczny, missing values, top merchants jako aliasy.
- `data/reports/forecasting_*.json` — walk-forward CV dla Naive, Mean3, SES i
  ARIMA per kategoria.
- `data/reports/anomaly_summary_*.json` — publiczny opis powodów anomalii i
  aliasy przykładów.
- `data/reports/latest_*.json` oraz `data/reports/summary.md` — stabilne pliki
  do cytowania w pracy.
- `data/private/anomaly_review_*.csv` — prywatny row-level review top anomalii,
  nie do repo.

Po ręcznym oznaczeniu kolumny `is_relevant` (`tak/nie`, `1/0`, `true/false`)
można przeliczyć precision:

```bash
python scripts/build_ml_evidence.py \
  --from-db \
  --review-file data/private/latest_anomaly_review.csv
```

Po wygenerowaniu raportów uruchomić inspekcję:

```bash
python scripts/inspect_report.py --strict
```

Tryb `--strict` wymaga kompletnego pakietu `latest_classification.json`,
`latest_eda.json`, `latest_forecasting.json`, `latest_anomaly_summary.json`,
`privacy_check_latest.json` i `summary.md`. To jest szybki sanity check przed
cytowaniem wyników w pracy lub prezentacji.

## Phase 10: clean-start evidence flow

1. Uruchomić aplikację na czystej bazie zgodnie z `docs/demo-runbook.md`.
2. Zaimportować realny eksport bankowy przez Next.js `/imports`.
3. Ręcznie zatwierdzić/odrzucić sugestie i uzupełnić seed etykiet tak, żeby
   klasy były możliwie zbalansowane.
4. Uruchomić retraining i `reclassify`.
5. Wygenerować raporty `build_ml_evidence.py --from-db`.
6. Wypełnić prywatny review anomalii i przeliczyć raport z `--review-file`.
7. Potwierdzić `inspect_report.py --strict`.

## Kryteria interpretacji

- Klasyfikacja powinna pokazywać przewagę nad `dummy_most_frequent`; cel roboczy
  to `macro_f1 >= 0.75` dla `linear_svc`.
- `confidence_curve` pokazuje kompromis coverage vs accuracy dla progów
  `0.50`, `0.55`, `0.60`, `0.70`, `0.80`, `0.90`; dla `LinearSVC` to proxy z
  marginów, nie prawdopodobieństwo.
- Augmentacja rzadkich klas jest wynikiem eksperymentalnym: raportujemy wynik
  nawet wtedy, gdy poprawa jest mała albo neutralna.
- Forecasting wybiera model po najniższym RMSE w walk-forward CV; ARIMA jest
  tylko jednym z kandydatów, nie wymogiem.
- Anomalie są nienadzorowane, więc finalna jakość powinna być opisana przez
  manualny `precision@20` / `precision@50` policzony lokalnie z prywatnego CSV.

## Prywatność

Do dokumentacji i prezentacji używać wyłącznie agregatów, aliasów merchantów i
anonimizowanych przykładów. Nie pokazywać pełnych tytułów przelewów, nazw
odbiorców ani model artifactów z realnym słownikiem TF-IDF.
Skrypt maskuje credentials z `--database-url` w komunikatach błędów.
