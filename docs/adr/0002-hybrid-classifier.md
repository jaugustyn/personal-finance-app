# ADR-0002: Hybrydowa klasyfikacja transakcji (LLM + LinearSVC)

- **Status:** ACCEPTED
- **Data:** 2026-05-01
- **Faza:** Faza 1 → Faza 3 (kalibracja konfidencji)

## Kontekst

Klasyfikacja transakcji bankowych do 8 kategorii systemowych
(`food`, `transport`, `housing`, `health`, `savings`, `subscriptions`,
`entertainment`, `other`)
to klasyczny problem klasyfikacji wielo­klasowej na krótkim tekście (merchant +
title) z dużą nierównowagą klas i silnym ogonem rzadkich wzorców (np. apteki,
abonamenty z nowymi merchantami). Dwie skrajne strategie:

- **A) Czysty klasyk ML** (TF-IDF + LinearSVC). Szybki, deterministyczny,
  wymaga oznakowanego datasetu, słabo radzi sobie z OOV merchantami.
- **B) Czysty LLM** (Llama 3.1 8B via Ollama). Zero-shot, dobrze rozumie nowe
  merchanty, ale: niedeterministyczny, drogi obliczeniowo, halucynuje
  kategorie spoza ontologii.

## Decyzja

Wybrano **podejście hybrydowe**:

1. **LinearSVC** (TF-IDF na `text` + numeryczne `abs_amount`, `day_of_week`)
   jako pierwszy klasyfikator. Jeśli `decision_function`-derived confidence ≥ τ
   (domyślnie 0.55) → akceptujemy predykcję.
2. **LLM (Ollama llama3.1:8b)** jako fallback dla niskiego confidence i dla
   merchantów nieobecnych w treningu (cold-start). Prompt zawiera ścisłą
   ontologię i przykłady few-shot z `SEED_EXAMPLES` w `augment.py`.
3. **LLM-driven augmentacja** rzadkich klas (`finance.ml.classification.augment`)
   poprawia macro-F1 SVC dla `health`, `housing`, `savings`.

## Konsekwencje

**Pozytywne:**

- Średnia latencja predykcji <50 ms na ~95 % zapytań (SVC ścieżka).
- Macro-F1 wzrasta z ~0.71 (czysty SVC, ~400 rzeczywistych transakcji) do
  ~0.78 po augmentacji LLM (n=120 syntetycznych próbek na 4 rzadkie klasy).
- Brak zależności od chmury — Ollama działa lokalnie.

**Negatywne:**

- Dwie ścieżki kodu = większa złożoność i powierzchnia testów.
- Augmentacja LLM jest niedeterministyczna; zapisujemy seed i wersję modelu
  Ollama w nazwie pliku CSV.
- Próg τ jest kalibrowany empirycznie w `classification_*.json` przez
  `confidence_curve`: coverage i accuracy na zaakceptowanych predykcjach dla
  progów 0.50/0.55/0.60/0.70/0.80/0.90. Dla `LinearSVC` confidence jest
  proxy znormalizowanym z marginów, nie skalibrowanym prawdopodobieństwem.

## Alternatywy odrzucone

- **Fine-tuning DistilBERT-multilingual.** Wymaga GPU, ~5–10× większy artefakt,
  marginalna poprawa na małym datasecie (<2k oznakowanych transakcji).
- **Reguły regexowe.** Nie skalują się; merchanci zmieniają formatowanie.
  Reguły zachowane jako *override* dla ścieżki LLM (planowane).

## Mierniki sukcesu

- Macro-F1 ≥ 0.75 w 5-fold StratifiedKFold po augmentacji.
- p99 latencji `/ml/classify` ≤ 200 ms (bez LLM fallback).
- Hit rate LLM fallback ≤ 10 % zapytań (jeśli wyższy → re-train SVC).
