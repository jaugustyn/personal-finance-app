# Plan usprawnień backendu i ML

Stan: 29.09.2026. Zakres obejmuje małe zmiany w istniejącej architekturze.
Priorytetem jest poprawność obliczeń i wiarygodność oceny modeli.

## Etap 1 — spójność danych i wyników (wdrożony)

1. **Podział danych klasyfikatora:** cały dzień graniczny należy do zbioru
   oceny czasowej. Trening wykorzystuje wyłącznie wcześniejsze transakcje
   i wyklucza wszystkie grupy sprzedawców objęte oceną grupową. Ograniczenia
   obowiązują także dla transakcji dodanych po zamrożeniu zbioru.
2. **Integralność zamrożonej oceny:** osobne skróty danych obu podzbiorów
   obejmują identyfikatory, etykiety, pochodzenie potwierdzeń i cechy modelu.
   Usunięty rekord, utrata potwierdzenia, zmiana opisu, kwoty analitycznej,
   daty lub tożsamości sprzedawcy unieważniają ocenę. Kontrola następuje
   przy odczycie jej statusu, przed treningiem oraz przed eksperymentem LLM.
   Zmiany notatek i rekordów poza zbiorem oceny nie unieważniają go.
3. **Usuwanie danych:** usunięcie pojedynczej transakcji, usunięcie zbiorcze
   i usunięcie importu unieważniają powiązany zbiór oceny w tej samej
   transakcji bazodanowej. Błąd zapisu wycofuje oba działania.
4. **Eksperyment LLM:** aktywny model musi wskazywać aktualny zamrożony zbiór.
   Model oceniany na innym podziale wymaga ponownego treningu i aktywacji.
5. **Agregacje finansowe:** miesięczny cashflow korzysta z tych samych reguł
   typu i kierunku transakcji co overview. Ręczne dopuszczenie niezgodności
   kierunku z typem nie powoduje już różnych sum między tymi widokami.

Zmienione obszary: `classification/candidate_evaluation.py`,
`classification/evaluation_sets.py`, `classification/lifecycle.py`,
`transactions/mutations.py`, `ingestion/use_cases.py`, `stats/service.py`
oraz `scripts/evaluate_llm_fallback.py`.

Nie zmieniono schematu bazy. Skróty podzbiorów są zapisywane w istniejącym
polu `MlEvaluationSet.config`. Starszy zamrożony zbiór bez tych skrótów
zostaje unieważniony podczas kontroli i wymaga jawnego ponownego zamrożenia.
Wyniki powiązane z różnymi wersjami zbioru nie stanowią bezpośredniego
porównania modeli. Istniejące artefakty predykcyjne pozostają dostępne;
nowa, porównywalna ocena wymaga ponownego treningu.

Ścisły podział może zmniejszyć zbiór treningowy. Nowe transakcje z okresu
oceny lub od zarezerwowanych sprzedawców nie powiększają treningu w tym
eksperymencie. Liczba rekordów faktycznie użytych do uczenia znajduje się
w `metrics.oof.n`; `excluded_training_count` oznacza liczbę zarezerwowanych
identyfikatorów, a nie wszystkie rekordy odrzucone przez granice podziału.

## Etap 2 — wiarygodniejsze prognozowanie (wdrożony)

1. **Wspólna walidacja:** modele deklarują minimalną historię. Do porównania
   wchodzą te, dla których dostępna jest wymagana liczba pełnych etapów
   oceny (domyślnie sześć). Wszystkie używają tych samych momentów startu,
   danych treningowych i horyzontu. Przy 36 miesiącach historii i horyzoncie
   trzech miesięcy wszystkie pięć modeli ma teraz po 10 etapów oceny;
   wcześniej modele bazowe miały 28, a sezonowy 10.
2. **Nieudana ocena:** błąd dopasowania, nieprawidłowe daty, niepełna prognoza
   lub kwoty NaN/Inf wykluczają model z rankingu. Raport zachowuje status,
   liczbę udanych, oczekiwanych i nieudanych etapów. Nie oblicza wyniku na
   wybranych pozostałych etapach. Wykluczenie po błędzie trafia też do logu.
3. **Zgodność z predykcją:** ujemne przewidywane wydatki są ograniczane do
   zera zarówno podczas oceny, jak i przy prognozie końcowej. Nieprawidłowe
   prognozy końcowe nie są zamieniane na fikcyjne zerowe wydatki.
4. **Daty:** historia kategorii jest uzupełniana zerami do końca dostępnego
   zakresu danych, także gdy najnowsza transakcja jest przychodem lub przelewem.
   W ścieżce bazodanowej zakres obejmuje transakcje przeliczalne na PLN.
   Bieżący niepełny miesiąc oraz przyszłe transakcje nie należą do historii
   treningowej. Nie dodajemy zer przed pierwszym wydatkiem kategorii ani
   automatycznie aż do dzisiaj, gdy importy kończą się wcześniej.
5. **Raporty:** `horizon_metrics` zawiera RMSE, MAPE i liczbę etapów osobno
   dla kroków 1..h. Dla samych zer rzeczywistych MAPE wynosi `null`.
   Raport evidence korzysta z wyników walidacji wybranego eksperymentu,
   bez ponownego wykonywania tej samej walidacji po udanym wyborze modelu.

Zmienione pliki: `src/finance/ml/forecasting/pipeline.py`,
`src/finance/ml/forecasting/registry.py`, `src/finance/ml/evidence.py` oraz
testy prognozowania, API i raportowania. Kontrakt odpowiedzi API i schemat
bazy pozostają zgodne z istniejącymi odbiorcami.

Model sezonowy potrzebuje 24 miesięcy do uczenia oraz danych do oceny:
domyślnie co najmniej 32 miesiące dla horyzontu trzech miesięcy. Przy krótszej
historii jest oznaczony jako `insufficient_history`, a prostsze modele nadal
mogą być porównywane. Włączenie modelu sezonowego skraca wspólny okres oceny
pozostałych modeli; porównywać należy wyniki w ramach jednego protokołu.

## Etap 3 — wydajność i stabilność testów (wdrożony)

1. **Reguły klasyfikacji:** `reclassify_unlabelled` ładuje aktywne reguły raz
   na niepustą partię, korzystając z istniejącego `PersonalRuleMatcher`.
   Dla 100 transakcji oznacza to jeden odczyt reguł zamiast 100. Priorytety,
   pochodzenie etykiet i pierwszeństwo reguł przed modelem zostają zachowane.
   Automatyczne przypisania nadal nie są potwierdzonymi etykietami treningowymi.
   Zmiana reguły jest uwzględniana przy kolejnym wywołaniu klasyfikacji.
2. **Daty w testach:** wspólna fixture ustala datę odniesienia w testach
   opłat stałych i subskrypcji. Osobne przypadki obejmują miesiące o różnej
   długości, luty przestępny oraz granice 60 i 180 dni od ostatniej płatności.
3. **PostgreSQL:** wspólna fixture korzysta wyłącznie z jawnego
   `TEST_DATABASE_URL` do bazy PostgreSQL z nazwą zakończoną `_test`.
   Testy sprawdzają klucze obce, deduplikację w obrębie konta, kaskadowe
   usuwanie powiązań płatności, zachowanie audytu z pustym `transaction_id`
   oraz atomowe unieważnienie zbioru oceny. Obejmują usunięcie pojedyncze,
   zbiorcze i całego importu, również z wymuszonym błędem zapisu.
   Scenariusz referencyjny sprawdza rzeczywisty import i ponowny import.
   Daty syntetycznego scenariusza są porównywane w UTC, z uwzględnieniem
   różnic reprezentacji między SQLite a PostgreSQL.
4. **CI:** zadanie backendu uruchamia PostgreSQL 16, stosuje migracje,
   wykonuje `alembic check` i osobno uruchamia zestaw integracyjny.

Zmienione obszary: `classification/predict.py`, testy klasyfikacji,
opłat stałych i subskrypcji, `tests/integration`, wspólny scenariusz
referencyjny, `.github/workflows/ci.yml` i runbook walidacji.
Nie zmieniono schematu bazy ani logiki uczenia modeli. Redukcja dotyczy
liczby odczytów reguł; nie jest pomiarem przyspieszenia całej klasyfikacji.

## Etap 4 — jakość kodu i eksperymenty do pracy (wdrożony)

1. **Kontrakty wyników:** `TypedDict` opisuje metryki klasyfikacji,
   kalibrację, wyniki podzbiorów, ranking, bramki jakości i benchmarki.
   Typy są używane przez evaluator, lifecycle i raportowanie; kształt
   istniejących odpowiedzi JSON pozostaje zgodny z odbiorcami.
2. **Wspólne metryki:** `classification/metrics.py` zawiera obliczanie
   F1, macierzy pomyłek i kalibracji. Kandydaci i benchmarki korzystają
   z tej samej implementacji. Usunięto duplikację metryk podzbiorów.
3. **Porównanie cech:** `classification/feature_comparison.py` i skrypt
   `scripts/compare_classification_features.py` porównują oba klasyfikatory
   na `baseline` oraz istniejącym `feature_v2`. Wszystkie cztery warianty
   mają wspólne rekordy, podziały, próg i metryki, również kalibrację.
   Rekordy są sortowane przed OOF; LinearSVC ma ustalony seed.
   Raport zawiera skróty danych i różnice względem baseline'u.
4. **Pochodzenie i aktywacja:** eksperyment odrzuca niepotwierdzone etykiety
   oraz zaakceptowane sugestie bez referencji pochodzenia. Utrata takiego
   rekordu z walidacji zatrzymuje uczenie. Skrypt wymaga ważnego zamrożonego
   zbioru, nie zapisuje zmian do bazy ani artefaktów modeli. Evaluator
   jawnie oznacza warianty spoza konfiguracji produkcyjnej jako
   `benchmark_only`, nawet jeśli przechodzą bramki liczbowe.
5. **Protokół pracy:** [osobny dokument](thesis-experiment-protocol.md)
   opisuje macierz eksperymentów, dobór wariantu, ograniczenia i oddzielny
   prospektywny test końcowy. Raporty porównania są jawnie walidacyjne;
   przygotowanie narzędzi nie oznacza wykonania końcowego badania.

Nie dodano zależności ani migracji. Nowe cechy nie stały się domyślnym
modelem aplikacji. Reguły, fallback LLM i dotychczasowe artefakty zachowują
dotychczasową obsługę; seed dotyczy kolejnych treningów LinearSVC.

## Weryfikacja etapu 1

Testy regresyjne znajdują się w `tests/ml/test_evaluation_integrity.py`,
`tests/stats/test_cashflow_consistency.py` oraz `tests/ml/test_hardening.py`.
Sprawdzają także wycofanie usuwania po błędzie, niepełne członkostwo
zbioru oceny i zatrzymanie eksperymentu przed predykcjami.

Polecenia (uruchomione przez lokalne `.venv`, odpowiedniki sekwencji z runbooka):

```powershell
uv run pytest tests/ml/test_evaluation_integrity.py tests/ml/test_hardening.py tests/stats tests/api/test_stats.py tests/transactions/test_mutation_use_cases.py tests/ingestion --no-cov
uv run pytest
uv run ruff check .
uv run mypy src apps scripts
git diff --check
```

Wynik końcowy: 52 testy klasyfikacji i nowej spójności cashflow przeszły;
pełny backend: **703 passed, 2 failed, 1 deselected**, pokrycie **89,51%**.
Ruff i Mypy (169 plików) przeszły. Dwa błędy występowały już przed zmianami:

- `tests/api/test_fixed_charges.py::test_manual_transaction_link_updates_payment_status`
  — oczekiwanie liczby płatności w kolejnych 30 dniach zależy od długości miesiąca;
- `tests/api/test_subscriptions.py::test_manual_subscription_category_creates_confirmed_row`
  — status dla stałej daty transakcji zmienia się wraz z upływem czasu.

Oba problemy z testami usunięto w etapie 3.

Nie wykonywano migracji ani kontroli na prywatnej bazie użytkownika.
Test integracyjny PostgreSQL wymaga osobnej bazy z końcówką `_test` i nie
był częścią tej weryfikacji.

### Kontrola obu klasyfikatorów na danych syntetycznych

Wykorzystano 360 syntetycznych rekordów z istniejącego testu
`test_candidate_uses_both_primary_holdouts_and_reports_calibration`, który
obejmuje teraz oba modele. Trening: 232 rekordy; ocena czasowa: 72;
ocena grupowa: 72. Podzbiory oceny mogą się częściowo pokrywać.

| Model | Podzbiór | Macro-F1 | Weighted-F1 |
| --- | --- | --- | --- |
| Logistic Regression | czasowy | 1,000 | 1,000 |
| Logistic Regression | sprzedawcy | 1,000 | 1,000 |
| kalibrowany LinearSVC | czasowy | 1,000 | 1,000 |
| kalibrowany LinearSVC | sprzedawcy | 1,000 | 1,000 |

Dla obu modeli i obu podzbiorów macierz pomyłek wynosi:

```text
8 0 0 0 0 0 0 0 0
0 8 0 0 0 0 0 0 0
0 0 8 0 0 0 0 0 0
0 0 0 8 0 0 0 0 0
0 0 0 0 8 0 0 0 0
0 0 0 0 0 8 0 0 0
0 0 0 0 0 0 8 0 0
0 0 0 0 0 0 0 8 0
0 0 0 0 0 0 0 0 8
```

Kolejność wierszy (prawdziwa klasa) i kolumn (predykcja):
`entertainment, food, health, housing, other, savings, shopping, subscriptions, transport`.
OOF dla obu modeli: macro-F1 i weighted-F1 = 1,000; macierz jest diagonalna,
z wartościami `[26, 26, 26, 26, 26, 26, 25, 26, 25]`.

To celowo łatwy test techniczny: teksty zawierają nazwy klas. Wyniki
potwierdzają działanie ścieżki uczenia i raportowania, ale nie mierzą jakości
na rzeczywistych finansach i nie są wynikiem badawczym do magisterki.

## Weryfikacja etapu 2

Uruchomiono przez lokalne `.venv`:

```powershell
uv run pytest tests/ml/test_forecasting.py tests/api/test_forecast.py tests/ml/test_evidence.py tests/ml/test_evidence_package.py tests/llm/test_tools.py --no-cov
uv run pytest
uv run ruff check .
uv run mypy src apps scripts
git diff --check
```

Wynik: **59 testów kierunkowych przeszło**. Pełny backend: **718 passed,
2 failed, 1 deselected**, pokrycie **89,56%**. Niepowodzenia dotyczą tych
samych dwóch testów kalendarzowych opisanych w etapie 1. Ruff, Mypy
(169 plików) i kontrola diffu przeszły. Nie zmieniano frontendu ani schematu
bazy; nie uruchamiano PostgreSQL ani eksperymentów na prywatnych danych.

Testy kontrolne obejmują:

- identyczne okna uczenia wszystkich porównywanych modeli;
- odrzucenie modelu, który uzyskuje idealny wynik dopiero po pominięciu
  jednego trudnego etapu oceny;
- niepełne prognozy, błędne daty, NaN/Inf oraz zerowe wartości rzeczywiste;
- wspólną końcową datę historii kategorii i API po ustaniu wydatków;
- ograniczenie zakresu do zaobserwowanych danych i pełnych miesięcy;
- brak ponownej walidacji podczas raportowania udanego eksperymentu.

Dla syntetycznego szeregu rosnącego o 1 na miesiąc model naiwny uzyskał
RMSE odpowiednio **1, 2 i 3** dla kroków 1..3 oraz łącznie **sqrt(14/3)**
na ośmiu wspólnych etapach oceny. Dla dokładnie powtarzanego cyklu rocznego
model sezonowy został wybrany z **RMSE = 0** na dziesięciu etapach.
To kontrola poprawności obliczeń; jakość prognoz na rzeczywistych danych
wymaga osobnego eksperymentu.

## Weryfikacja etapu 3

Uruchomiono przez lokalne `.venv`:

```powershell
uv run pytest tests/ml/test_predict.py tests/api/test_ml_classify.py tests/api/test_fixed_charges.py tests/api/test_subscriptions.py tests/integration/test_database_guard.py --no-cov
uv run pytest
uv run ruff check .
uv run mypy src apps scripts
# DATABASE_URL i TEST_DATABASE_URL wskazują wyłącznie tymczasową bazę _test:
uv run alembic upgrade head
uv run alembic check
uv run pytest tests/integration -m postgres_integration --no-cov
git diff --check
```

Wynik: **76 testów kierunkowych przeszło**. Pełny backend: **738 passed,
10 deselected**, pokrycie **89,63%**. Osobny zestaw PostgreSQL: **10 passed,
4 deselected**. Ruff i Mypy (169 plików) przeszły. Wszystkie migracje na
pustej bazie PostgreSQL 16 zastosowano poprawnie; `alembic check` nie wykrył
różnic między schematem a modelami. Zweryfikowano też składnię konfiguracji CI.
Pełny przebieg zgłosił 12 ostrzeżeń: 11 o niedomkniętych połączeniach SQLite
w testach oraz jedno o przestarzałej operacji NumPy w joblib. Nie blokują
testów; wymagają osobnego uporządkowania.

Pomiar zapytań obejmuje partie 1, 12 i 100 transakcji w trybach sugestii
i automatycznego przypisania: każda wykonuje dokładnie jeden odczyt reguł.
Test kolejnego wywołania potwierdza uwzględnienie zmodyfikowanej reguły.

Wykorzystano osobny, tymczasowy kontener z danymi syntetycznymi i usunięto go
po weryfikacji. Prywatna baza nie była celem migracji ani testów.
Konfiguracja CI została sprawdzona
lokalnie; wykonanie w GitHub Actions nastąpi po wysłaniu zmian. Nie zmieniano
frontendu ani treningu klasyfikatorów, więc nie powtarzano eksperymentów F1.

## Weryfikacja etapu 4

Polecenia odpowiadające wykonanej weryfikacji:

```powershell
uv run pytest tests/ml/test_feature_comparison.py tests/ml/test_hardening.py tests/ml/test_evaluation_integrity.py tests/ml/test_train.py tests/ml/test_pipeline.py --no-cov
uv run pytest
uv run ruff check .
uv run mypy src apps scripts
git diff --check
```

Wykorzystano lokalny CPython 3.14.7 z instalacji uv i istniejące pakiety
`.venv`; Windows blokował uruchomienie samego launchera `.venv/Scripts/python.exe`.
Nie zmieniano zależności ani polityk systemowych.

Wynik: **69 testów kierunkowych przeszło**. Pełny backend: **748 passed,
10 deselected**, pokrycie **89,90%**. Ruff, Mypy (172 pliki) i kontrola diffu
przeszły. Nadal występuje 11 ostrzeżeń o połączeniach SQLite i jedno
ostrzeżenie joblib/NumPy opisane w etapie 3. Nie ponawiano migracji,
integracji PostgreSQL ani walidacji frontendu: etap 4 nie zmienia ich kodu
ani schematu bazy.

Nowe testy obejmują poprawność liczbową metryk, stałą kolejność klas
w macierzy pomyłek, brak słów z walidacji w słowniku treningowym,
identyczne metryki po przetasowaniu wejścia, pochodzenie etykiet,
odmowę użycia nieprawidłowego zamrożonego zbioru i brak dopuszczenia
`feature_v2` do aktywacji mimo przejścia bramek liczbowych.

### Kontrolne porównanie na danych syntetycznych

Uruchomiono pełną ścieżkę porównania na 360 rekordach generowanych przez
`synthetic_frame()` z `tests/ml/test_feature_comparison.py`. Trening zawiera
234 rekordy; walidacja czasowa i sprzedawców po 72 rekordy. Są trzy klasy
z równym wsparciem: `food`, `health`, `transport`. Część opisów jest celowo
niejednoznaczna. Wyniki dotyczą kontroli narzędzia, nie jakości na danych
użytkownika ani całej dziewięcioklasowej ontologii.

| Model | Cechy | Podzbiór | Macro-F1 | Weighted-F1 |
| --- | --- | --- | --- | --- |
| Logistic Regression | baseline | czasowy | 0,890211 | 0,890211 |
| Logistic Regression | feature_v2 | czasowy | 0,890211 | 0,890211 |
| kalibrowany LinearSVC | baseline | czasowy | 0,890211 | 0,890211 |
| kalibrowany LinearSVC | feature_v2 | czasowy | 0,890211 | 0,890211 |
| Logistic Regression | baseline | sprzedawcy | 0,916570 | 0,916570 |
| Logistic Regression | feature_v2 | sprzedawcy | 0,917320 | 0,917320 |
| kalibrowany LinearSVC | baseline | sprzedawcy | 0,930703 | 0,930703 |
| kalibrowany LinearSVC | feature_v2 | sprzedawcy | 0,916570 | 0,916570 |
| Logistic Regression | baseline | OOF | 0,854752 | 0,854752 |
| Logistic Regression | feature_v2 | OOF | 0,846223 | 0,846223 |
| kalibrowany LinearSVC | baseline | OOF | 0,846315 | 0,846315 |
| kalibrowany LinearSVC | feature_v2 | OOF | 0,854825 | 0,854825 |

Macierz czasowa jest wspólna dla wszystkich wariantów. Wiersze oznaczają
prawdziwe klasy, kolumny predykcje; kolejność: `food`, `health`, `transport`.

```text
21  3  0
 1 23  0
 1  3 20
```

Macierze dla sprzedawców, w tej samej kolejności klas:

```text
Logistic Regression baseline: [[23, 1, 0], [1, 22, 1], [2, 1, 21]]
Logistic Regression feature_v2: [[22, 2, 0], [1, 23, 0], [1, 2, 21]]
LinearSVC baseline:             [[23, 1, 0], [1, 23, 0], [2, 1, 21]]
LinearSVC feature_v2:           [[22, 1, 1], [1, 23, 0], [1, 2, 21]]
```

Macierze OOF:

```text
Logistic Regression baseline: [[67, 5, 6], [4, 67, 7], [6, 6, 66]]
Logistic Regression feature_v2: [[66, 6, 6], [7, 66, 5], [7, 5, 66]]
LinearSVC baseline:             [[66, 4, 8], [5, 66, 7], [5, 7, 66]]
LinearSVC feature_v2:           [[67, 4, 7], [4, 67, 7], [6, 6, 66]]
```

Nie ma podstaw, by na tej kontroli zastąpić baseline dodatkowymi cechami.
Następny krok badawczy to wykonanie tego samego porównania na lokalnym
zbiorze potwierdzonych etykiet, a następnie realizacja oddzielnego testu
końcowego według protokołu. W tym etapie nie wykonywano tych badań na
prywatnych danych.

## Porządki po etapach 1–4

Usunięto nieużywane `build_pipeline_text`, `to_features_text`,
`excluded_training_ids` i `find_matching_rule`. Prywatny alias
`_artifact_sha256` zastąpiono bezpośrednim użyciem `artifact_sha256`.
Raportowanie korzysta z wymaganych pól typowanych metryk, bez zastępowania
brakujących pól pustymi wynikami. Usunięto też powtórzone przypisania
i zbędne konwersje liczb. Algorytmy aktywnie używanych modeli pozostają takie same.

Testy API mają wspólną fabrykę sesji dla żądań i zadań w tle. Klienci
są zamykani przed usunięciem testowej bazy. Siedem testów statystyk oraz
test poprawnego logowania wymagają HTTP 200; wcześniej mogły przejść
pomimo błędu serwera. Konfiguracja testów auth jest przywracana przez
`monkeypatch`, a przeładowanie aplikacji jest potrzebne tylko do sprawdzenia
konfiguracji dokumentacji. Dodano regresję potwierdzającą, że sugestie
uruchamiane po imporcie operują na tej samej bazie co import.

Po testach kierunkowych API, ML i reguł wykonano końcową walidację:

```powershell
uv run pytest
uv run ruff check .
uv run mypy src apps scripts
git diff --check
```

Wynik: **748 passed, 10 deselected**, pokrycie **89,96%**. Ruff i Mypy
(172 pliki) przeszły. Liczba testów pozostała taka sama: usunięto test
nieużywanego pipeline'u tekstowego i dodano test sugestii w tle.
Zniknęło 11 ostrzeżeń SQLite. Pozostało jedno ostrzeżenie w
`joblib/numpy_pickle.py` o przypisywaniu `array.shape`, przestarzałym
w NumPy 2.5. Nie dodano filtrów ostrzeżeń ani modyfikacji bibliotek.
