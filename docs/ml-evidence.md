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

Opcjonalnie z publicznym zbiorem Kaggle jako eksperymentem porównawczym:

```bash
python scripts/build_ml_evidence.py \
  --from-db \
  --external-kaggle data/external/kaggle_personal_finance_data/Personal_Finance_Dataset.csv
```

Kaggle jest raportowany wyłącznie jako `external_only` i
`real_plus_external`. Nie zastępuje ręcznie potwierdzonych polskich etykiet i
nie powinien automatycznie przełączać modelu produkcyjnego.

Skrypt zapisuje:

- `data/reports/classification_*.json` — real-only oraz opcjonalnie augmented,
  baseline `dummy_most_frequent`, `logreg`, `linear_svc`, `random_forest`,
  macro-F1, weighted-F1, per-class metrics i confusion matrix. Raport zawiera
  też eksperymentalne porównanie `feature_v2` (`merchant_norm`,
  `transaction_type`, `source`, amount bucket, month), `linear_svc_calibrated`
  jako wariant confidence oraz sekcję `label_readiness`, ale produkcyjny model
  pozostaje na bazowym pipeline do czasu przeglądu wyników.
- `data/reports/transaction_type_classification_*.json` — osobny
  eksperyment wieloklasowy dla `Transaction.transaction_type` na silver labels.
  Raport obejmuje `dummy_most_frequent`, `logreg`, `linear_svc`, macro-F1,
  weighted-F1, per-class metrics, confusion matrix, class counts i klasy
  odrzucone przez niski support. Runtime pozostaje bez zmian: typ transakcji w
  imporcie nadal wykrywają reguły.
- `data/reports/eda_*.json` — bezpieczne agregaty do wizualizacji: rozkłady
  kategorii, cashflow miesięczny, missing values, top merchants jako aliasy.
- `data/reports/forecasting_*.json` — walk-forward CV dla Naive, Mean3, SES i
  ARIMA per kategoria.
- `data/reports/anomaly_summary_*.json` — publiczny opis powodów anomalii i
  aliasy przykładów.
- `data/reports/subscriptions_*.json` — publiczny, zagregowany raport detekcji
  kadencji: liczba wykrytych subskrypcji, szacowany koszt miesięczny, rozkład
  cadence i przykłady jako aliasy.
- `data/reports/evidence_package_*.json` — główny wspólny pakiet w schemacie
  `schema_version = "2.0"`. Sekcje są pod kluczem `sections`:
  `category_classification`, `transaction_type_classification`, `forecasting`,
  `anomaly_detection` i `subscriptions`. Pakiet zawiera też `source`,
  `semantic_note` oraz `privacy_check`.
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
`latest_transaction_type_classification.json`, `latest_eda.json`,
`latest_forecasting.json`, `latest_anomaly_summary.json`,
`latest_subscriptions.json`, `latest_evidence_package.json`,
`privacy_check_latest.json` i `summary.md`. Sprawdza też minimalny kształt
`latest_evidence_package.json`: wersję schematu, źródło, pięć sekcji evidence,
metryki klasyfikacji, confusion matrix, pola precision dla anomalii, summary
subskrypcji i przejście privacy check. To jest szybki sanity check przed
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

## Ile danych potrzeba

Priorytetem są realne polskie transakcje z ręcznie potwierdzonym polem
`category`. `category_predicted` jest sugestią, nie ground truth.

- Minimum techniczne: `300-500` potwierdzonych transakcji.
- Sensowny poziom do pracy: `800-1500` etykiet.
- Docelowo do mocnego evidence: `~2000+` etykiet z `6-12` miesięcy.
- Per kategoria: `20-30` jako minimum dla rzadkich klas, `50-100` dla klas
  częstych.

Raport `label_readiness` pokazuje, które kategorie są poniżej progów i co
powinno trafić do kolejki review: brak kategorii, niski confidence, rzadkie
klasy i powtarzający się merchant z błędami.

## Kryteria interpretacji

- Klasyfikacja powinna pokazywać przewagę nad `dummy_most_frequent`; cel roboczy
  to `macro_f1 >= 0.75` dla `linear_svc`.
- `category_classification` i `transaction_type_classification` należy
  interpretować osobno. Pierwsza warstwa klasyfikuje budżetową kategorię
  wydatku, druga opisuje semantykę przepływu pieniędzy. `transaction_type` v1
  jest eksperymentem na `silver_transaction_type`, nie produkcyjnym
  zamiennikiem reguł.
- `confidence_curve` pokazuje kompromis coverage vs accuracy dla progów
  `0.50`, `0.55`, `0.60`, `0.70`, `0.80`, `0.90`; dla `LinearSVC` to proxy z
  marginów, nie prawdopodobieństwo.
- Augmentacja rzadkich klas jest wynikiem eksperymentalnym: raportujemy wynik
  nawet wtedy, gdy poprawa jest mała albo neutralna.
- Forecasting wybiera model po najniższym RMSE w walk-forward CV; ARIMA jest
  tylko jednym z kandydatów, nie wymogiem.
- Anomalie są nienadzorowane, więc finalna jakość powinna być opisana przez
  manualny `precision@20` / `precision@50` policzony lokalnie z prywatnego CSV.
- Subskrypcje są raportowane jako detekcja kadencji, nie klasyfikator
  nadzorowany; ich jakość najlepiej potwierdzić ręcznym review przykładów.

## Prywatność

Do dokumentacji i prezentacji używać wyłącznie agregatów, aliasów merchantów i
anonimizowanych przykładów. Nie pokazywać pełnych tytułów przelewów, nazw
odbiorców ani model artifactów z realnym słownikiem TF-IDF.
Skrypt maskuje credentials z `--database-url` w komunikatach błędów.
