# Aktualne metodyki i rozwiązania aplikacji

Data przeglądu: 2026-06-30.

Dokument opisuje aktualny stan projektu na podstawie kodu, konfiguracji,
istniejącej dokumentacji i testów. Nie zawiera prywatnych danych finansowych ani
surowych eksportów bankowych.

## 1. Cel systemu

Projekt jest samo-hostowaną aplikacją do analizy finansów osobistych. Łączy:

- import transakcji bankowych z plików CSV/XLSX,
- trwałe przechowywanie danych w PostgreSQL,
- dashboard webowy do analizy wydatków, przychodów, kategorii i portfela,
- klasyczne modele ML do klasyfikacji, anomalii, prognoz i subskrypcji,
- lokalnego asystenta LLM opartego o Ollama,
- deterministyczne narzędzia domenowe do obliczeń finansowych.

Główna zasada metodologiczna: LLM nie jest źródłem prawdy dla liczb. Kwoty,
agregacje, prognozy i rekomendacje bazują najpierw na SQL, regułach domenowych
albo modelach klasycznych, a LLM może co najwyżej dobrać narzędzie lub streścić
wynik.

## 2. Stos technologiczny

Backend:

- FastAPI jako API HTTP,
- Pydantic v2 dla DTO i walidacji wejścia/wyjścia,
- SQLAlchemy 2 jako ORM,
- Alembic dla migracji,
- PostgreSQL jako baza runtime,
- structlog dla logów strukturalnych,
- APScheduler dla opcjonalnych zadań okresowych.

Frontend:

- Next.js App Router,
- React 19,
- TypeScript,
- Tailwind CSS 4,
- TanStack Query,
- Recharts,
- Radix UI,
- lucide-react,
- next-themes,
- sonner.

ML i dane:

- pandas,
- numpy,
- scikit-learn,
- statsmodels,
- joblib.

LLM:

- lokalny Ollama,
- model konfigurowany przez zmienne środowiskowe,
- tool-calling przez cienkiego klienta HTTP.

Uruchomienie:

- Docker Compose: `postgres`, `api`, `web`,
- API wykonuje `alembic upgrade head` przed startem Uvicorn,
- katalog `data/` jest montowany do kontenera API jako miejsce na modele,
  raporty i artefakty runtime.

## 3. Architektura katalogów

Główne granice odpowiedzialności:

- `apps/api` - FastAPI, routery, middleware, security, scheduler.
- `apps/web` - dashboard Next.js.
- `src/finance` - logika domenowa, importy, ML, LLM, statystyki, waluty,
  aktywa i profil użytkownika.
- `src/finance/domain` - modele SQLAlchemy, enumy i DTO.
- `src/finance/ingestion` - parsery i import transakcji.
- `src/finance/transactions` - zapytania, mutacje, reguły, normalizacja,
  merchant aliases, review i eksport CSV.
- `src/finance/stats` - agregacje dashboardu i recap.
- `src/finance/ml` - klasyfikacja kategorii, klasyfikacja typu transakcji,
  anomalie, prognozowanie, subskrypcje, evidence i feedback.
- `src/finance/llm` - router asystenta, narzędzia, formatery, okresy i klient
  Ollama.
- `src/finance/assets` - portfel aktywów i snapshoty.
- `src/finance/currencies` - waluty bazowe i kursy FX.
- `src/finance/profile` - profil użytkownika i reguły personalizacji.
- `alembic` - migracje schematu bazy.
- `tests` - testy API, domeny, ML, LLM, importu, statystyk i migracji.
- `docs` - dokumentacja projektowa, ADR, model card i evidence.

## 4. Przepływ danych

Typowy przepływ produkcyjny:

1. Użytkownik importuje plik w dashboardzie.
2. Next.js wysyła żądanie przez `/api/proxy/*`.
3. Proxy przekazuje żądanie do FastAPI.
4. Router `imports` waliduje plik, wybiera parser i wywołuje warstwę
   `finance.ingestion`.
5. Parser bankowy zwraca listę `TransactionDTO`.
6. Serwis importu:
   - przelicza walutę na walutę bazową,
   - wykrywa `transaction_type`,
   - stosuje reguły personalne,
   - przypisuje kategorie bankowe/regułowe tylko tam, gdzie ma to sens,
   - wylicza stabilny `dedup_hash`,
   - zapisuje transakcje z ochroną przed duplikatami.
7. API i dashboard korzystają z transakcji przez moduły `transactions`,
   `stats`, `ml`, `llm`, `assets` i `currencies`.

## 5. Model domenowy

Najważniejsze tabele:

- `accounts` - konta źródłowe.
- `imports` - historia importów i liczba duplikatów.
- `transactions` - główna tabela transakcji.
- `categories` - katalog kategorii systemowych i własnych.
- `user_profile` - profil single-user: waluta bazowa, dzień pensji, cel
  oszczędnościowy, limity kategorii.
- `fx_rates` - kursy walut względem waluty bazowej.
- `personal_rules` - reguły użytkownika dla merchant/title.
- `merchant_aliases` - aliasy merchantów do nazw kanonicznych.
- `ml_feedback_events` - audyt feedbacku dla ML/AI.
- `subscription_preferences` - decyzje użytkownika dla subskrypcji.
- `assets` i `asset_snapshots` - portfel aktywów i historia wartości.

Kluczowe rozróżnienie domenowe:

- `category` oznacza kategorię budżetową wydatku, np. `food`, `transport`,
  `shopping`.
- `transaction_type` oznacza semantykę przepływu pieniędzy, np. `purchase`,
  `salary`, `refund`, `own_transfer`.

To rozdzielenie zapobiega mieszaniu pensji, zwrotów i przelewów własnych z
ontologią wydatków. W konsekwencji klasyfikator kategorii pracuje tylko na
transakcjach kwalifikujących się jako wydatki.

## 6. Metodyka importu i normalizacji

Import obsługuje parsery rejestrowane przez registry:

- Pekao,
- Revolut,
- parser generyczny,
- mechanizm detekcji źródła po nagłówkach.

Wspólna metodyka importu:

- parsery produkują ujednolicone `TransactionDTO`,
- kwota oryginalna pozostaje w `amount`,
- analityczna kwota w walucie bazowej trafia do `amount_base`,
- `dedup_hash` powstaje ze źródła, daty, kwoty, waluty, kierunku,
  znormalizowanego merchanta, tytułu i `external_id`,
- `INSERT ... ON CONFLICT DO NOTHING` chroni przed reimportem tych samych
  transakcji,
- reguły personalne są stosowane przed sugestiami ML,
- `skip_categories` pozwala importować bez kategorii bankowych, gdy potrzebna
  jest ręczna lub modelowa klasyfikacja.

Walidacja importu w API obejmuje m.in. limit rozmiaru pliku, dozwolone
rozszerzenia/MIME i walidację pustego pliku.

## 7. Transakcje, reguły i review

Warstwa transakcji jest podzielona na:

- `queries.py` - odczyt, filtrowanie, grupowanie i podsumowania,
- `mutations.py` - ręczne zmiany kategorii, typu, tagów, notatek i operacje
  bulk,
- `rules.py` - regułowe wykrywanie `transaction_type`,
- `system_rules.py` i `system_rules.json` - rejestr reguł systemowych,
- `merchants.py` - normalizacja merchantów, aliasy i grupowanie,
- `review.py` - podsumowanie kolejki review,
- `export.py` - eksport CSV z ochroną przed formula injection.

Najważniejsze zasady:

- kategorie można przypisać tylko do transakcji będących kandydatami na
  kategorię wydatkową,
- zmiana `transaction_type` aktualizuje `is_transfer`,
- jeśli typ transakcji przestaje być kandydatem kategorii, stan kategorii i
  sugestii jest czyszczony,
- ręczne decyzje użytkownika zapisują feedback ML,
- tagi i notatki są metadanymi użytkownika i nie karmią modeli ML.

## 8. Kategorie i subkategorie

System ma katalog kategorii zarządzany przez API:

- kategorie systemowe są seedowane i nie powinny być usuwane,
- użytkownik może tworzyć kategorie własne,
- `Transaction.category` przechowuje nazwę kategorii jako string,
- `subcategory` jest warstwą doprecyzowania UI,
- relacja subkategorii do kategorii nadrzędnej jest walidowana przy zapisie.

Podstawowa ontologia systemowa:

- `food`,
- `transport`,
- `subscriptions`,
- `health`,
- `entertainment`,
- `housing`,
- `savings`,
- `shopping`,
- `other`.

## 9. Waluty i kwoty bazowe

Metodyka walutowa:

- `amount` zawsze oznacza oryginalną kwotę z banku,
- `amount_base` jest kwotą analityczną w walucie bazowej użytkownika,
- domyślna waluta bazowa to `PLN`,
- kursy są przechowywane w `fx_rates`,
- dla walut obcych względem PLN system może pobrać kurs z NBP z lookbackiem,
- brak kursu dla waluty obcej zgłasza `MissingFxRate`, zamiast cicho użyć
  kursu `1`,
- agregacje korzystają z `amount_base_expr()`, czyli `coalesce(amount_base,
  amount)` dla kompatybilności ze starszymi/syntetycznymi danymi testowymi.

To rozwiązanie pozwala zachować oryginał transakcji, a jednocześnie prowadzić
spójne analizy w jednej walucie.

## 10. Statystyki i agregacje

Dashboard i narzędzia LLM korzystają z deterministycznych agregacji SQL oraz
wspólnych filtrów domenowych.

Dostępne agregacje obejmują:

- overview: przychody, wydatki, cashflow netto, stopa oszczędności, liczba
  transakcji,
- cashflow miesięczny,
- wydatki po kategoriach,
- narastający net worth z przepływów,
- top merchantów z uwzględnieniem aliasów,
- trend kategorii w miesiącach,
- histogram kwot, średnią, medianę, percentyl 95 i górny próg IQR,
- recap tygodniowy, miesięczny i custom.

Przelewy są domyślnie wykluczane z wielu agregacji, chyba że endpoint pozwala
ustawić `include_transfers=true`.

## 11. Frontend

Frontend jest aplikacją operacyjną, nie landing page'em. Układ bazuje na:

- sidebarze,
- nagłówku aplikacji,
- providerach: theme, accent, i18n, TanStack Query, tooltipy, confirm dialog,
- wspólnych komponentach UI,
- stronach modułowych dla każdego obszaru.

Główne widoki:

- dashboard,
- transakcje,
- importy,
- kategorie,
- merchant aliases,
- waluty,
- review,
- ML,
- prognoza,
- recap,
- anomalie,
- subskrypcje,
- aktywa,
- asystent,
- ustawienia.

Komunikacja z backendem przechodzi przez Next.js route handler
`/api/proxy/[...path]`, który:

- przekazuje metody GET/POST/PATCH/PUT/DELETE,
- zachowuje `content-type`,
- obsługuje multipart przez `arrayBuffer()`,
- dokłada BasicAuth do upstreamu, jeśli ustawiono `API_USERNAME` i
  `API_PASSWORD`,
- ma timeout 30 sekund,
- mapuje niedostępność upstreamu na 502.

Teksty runtime są zlokalizowane, a głównym językiem UI jest polski.

## 12. API FastAPI

API ma cienkie routery, a logika domenowa znajduje się w `src/finance`.

Routery:

- `/imports` - preview, import, historia importów, usuwanie importu,
- `/transactions` - lista, eksport, filtry, grupy merchantów, review,
  aktualizacje i bulk actions,
- `/merchants` - aliasy i sugestie aliasów,
- `/currencies` - status, kursy, pobieranie NBP, przeliczanie,
- `/ml` - status, readiness, raporty, dashboard ML, classify, feedback,
  reclassify, retrain,
- `/forecast` - prognoza wydatków,
- `/anomalies` - lista anomalii i feedback,
- `/subscriptions` - lista, overview, preferencje i feedback,
- `/chat` - asystent finansowy,
- `/stats` - agregacje dashboardu i recap,
- `/assets` - aktywa, portfel, odświeżanie, historia i Sankey,
- `/categories` - katalog kategorii,
- `/profile` - profil i reguły personalne.

Endpointy health:

- `/health`,
- `/health/live`,
- `/health/ready`.

Routery biznesowe są chronione warunkowym BasicAuth. Health i dokumentacja API
pozostają publiczne zgodnie z konfiguracją middleware.

## 13. Bezpieczeństwo i prywatność

Rozwiązania bezpieczeństwa:

- opcjonalny HTTP BasicAuth dla single-user self-hosting,
- security headers: CSP, `X-Frame-Options: DENY`, `nosniff`,
  `Referrer-Policy`, `Permissions-Policy`,
- in-memory sliding-window rate limiting per IP,
- CORS konfigurowany przez `CORS_ALLOW_ORIGINS`,
- walidacja importów,
- CSV export zabezpieczony przed formula injection,
- prywatne dane i artefakty runtime trzymane w katalogach ignorowanych przez
  Git,
- Ollama lokalnie zamiast zewnętrznego API LLM.

Ograniczenia:

- BasicAuth i rate limit są wystarczające dla lokalnego single-user, ale nie są
  kompletnym modelem multi-user,
- rate limiter jest pamięciowy i nie jest współdzielony między instancjami,
- brak Prometheus/OpenTelemetry jest świadomym kompromisem na rzecz prostoty.

## 14. Observability

Metodyka obserwowalności:

- `structlog` produkuje logi JSON,
- każde żądanie dostaje `X-Request-ID`,
- middleware mierzy czas obsługi i status,
- health check sprawdza bazę i dostępność Ollama,
- readiness wymaga dostępnej bazy,
- brak Prometheus/Grafana w runtime, bo aplikacja jest single-host.

Decyzja jest opisana w ADR-0004.

## 15. Klasyfikacja kategorii wydatków

Główny klasyfikator kategorii jest klasycznym modelem `scikit-learn`.

Cel:

- przewidzieć kategorię wydatkową `category`,
- tylko dla transakcji będących kandydatami na kategorię wydatkową,
- nie mieszać tego z typem transakcji.

Cechy bazowe:

- `text` = merchant + title,
- `abs_amount`,
- `day_of_week`.

Pipeline:

- `TfidfVectorizer` word n-gram 1-2,
- `TfidfVectorizer` char_wb n-gram 3-5,
- `log1p(abs_amount)` + `StandardScaler`,
- one-hot dzień tygodnia,
- estymator, domyślnie `LinearSVC`.

Istnieje też eksperymentalny feature set v2:

- `merchant_norm`,
- bucket kwoty,
- miesiąc,
- `transaction_type`,
- `source`.

Metodyka treningu:

- dane z plików lub bazy,
- tylko potwierdzone `Transaction.category` jako ground truth,
- odrzucenie klas z mniej niż 2 przykładami dla CV,
- StratifiedKFold,
- raport: macro-F1, weighted-F1, classification report, confusion matrix,
  confidence curve,
- baseline `DummyClassifier`,
- artefakt modelu zapisywany w `data/models/classifier_latest.joblib`,
- raporty w `data/reports`.

Polityka zaufania:

- domyślny próg akceptacji: 0.55,
- floor review: 0.25,
- `other` wymaga review, jeśli polityka nie pozwala go automatycznie
  akceptować,
- decyzje: `accept`, `review`, `manual`, `not_applicable`.

LLM fallback:

- opcjonalny,
- wywoływany przy niskiej pewności,
- prompt wymusza jedną kategorię z zamkniętej ontologii,
- wynik jest źródłem sugestii, nie twardym faktem finansowym.

## 16. Klasyfikacja `transaction_type`

`transaction_type` ma osobną metodykę:

- produkcyjnie źródłem prawdy pozostają reguły systemowe i personalne,
- model supervised jest evidence-only,
- etykiety są silver labels z `Transaction.transaction_type`,
- model nie zastępuje runtime `detect_transaction_type`.

Klasy:

- `purchase`,
- `own_transfer`,
- `person_transfer`,
- `salary`,
- `income`,
- `refund`,
- `cash_withdrawal`,
- `debt_payment`,
- `bank_fee`,
- `savings_investment`,
- `other`.

Cechy:

- `merchant + title + raw_category`,
- `abs_amount`,
- `direction`,
- `source`.

Raport porównuje:

- `dummy_most_frequent`,
- `LogisticRegression`,
- `LinearSVC`.

Metryki:

- macro-F1,
- weighted-F1,
- per-class metrics,
- confusion matrix,
- liczebności klas,
- klasy odrzucone przez niski support.

## 17. Detekcja anomalii

Metodyka anomalii jest hybrydowa i wyjaśnialna:

- IsolationForest,
- robust z-score per `(category, direction)` z medianą i MAD,
- reguły deterministyczne, np. nowy merchant + duża kwota,
- kontekst merchanta: liczba wystąpień, mediana kwoty, ratio, z-score,
  powtarzalność miesięczna.

Cechy IsolationForest:

- `log_abs`,
- dzień tygodnia,
- dzień miesiąca,
- częstotliwość merchanta,
- robust z-score kwoty,
- kierunek debit/credit.

Wynik zawiera:

- `anomaly`,
- `severity`,
- `priority_score`,
- `anomaly_type`,
- powody po polsku,
- kody powodów,
- dane kontekstowe merchanta.

Filtracja:

- analizowane są przede wszystkim transakcje wydatkowe,
- wykluczane są typy takie jak `savings_investment`,
- model-only może być ukryty w widoku review.

## 18. Detekcja subskrypcji

Subskrypcje są wykrywane heurystycznie, bez LLM:

- normalizacja merchanta,
- grupowanie po merchant/currency,
- minimalna liczba wystąpień,
- stabilność kwoty z tolerancją około 10%,
- mediana odstępów między płatnościami,
- klasy kadencji: weekly, biweekly, monthly, yearly,
- minimalna długość historii względem kadencji,
- blacklist sklepów i sieci handlowych,
- whitelist znanych usług subskrypcyjnych.

Wynik zawiera:

- merchant display label,
- merchant key,
- walutę,
- kadencję,
- medianę kwoty,
- liczbę wystąpień,
- ostatnie wystąpienie,
- szacowany koszt miesięczny,
- confidence.

Warstwa preferencji użytkownika pozwala potwierdzać, nadpisywać kadencję i
utrzymywać decyzje dla grup subskrypcji.

## 19. Prognozowanie

Prognozowanie bazuje na miesięcznych szeregach wydatków:

- wejściem są transakcje debit kwalifikujące się jako wydatki,
- seria może dotyczyć wszystkich kategorii albo jednej kategorii,
- kwoty są agregowane miesięcznie,
- brakujące miesiące są uzupełniane zerami.

Metody:

- naive,
- rolling mean,
- SES,
- ARIMA.

Metodyka wyboru:

- walk-forward CV,
- horyzont walidacji 1 miesiąc,
- wybór modelu po najniższym RMSE,
- zwracane są MAPE, RMSE, historia i prognoza,
- przy zbyt krótkiej historii fallbackiem jest naive.

To jest świadomy kompromis: krótkie historie finansów osobistych nie
uzasadniają ciężkich modeli sekwencyjnych.

## 20. Rekomendacje oszczędnościowe

Rekomendacje są deterministyczne:

- porównują bieżący okres z poprzednim okresem tej samej długości,
- liczą sumy kategorii,
- wykrywają kategorie z największym wzrostem,
- sprawdzają limity kategorii z profilu,
- liczą postęp względem celu oszczędnościowego,
- dołączają top merchantów,
- dołączają podsumowanie subskrypcji i anomalii.

LLM może później opisać wynik, ale same fakty są wyliczone w Pythonie/SQL.

## 21. Asystent LLM

Asystent ma trzyetapowy routing:

1. Heurystyczne rozpoznanie intencji po polsku.
2. Kontekstowe follow-upy, np. krótkie pytanie o inny okres.
3. Tool-calling przez Ollamę, jeśli heurystyka nie wystarczy.

Dostępne narzędzia:

- `get_spending`,
- `top_merchants`,
- `top_categories`,
- `cashflow_overview`,
- `list_subscriptions`,
- `list_anomalies`,
- `forecast_for`,
- `compare_periods`,
- `recommend_savings`,
- `category_review_summary`.

Formatowanie odpowiedzi jest deterministyczne przez `format_answer`. Opcjonalne
`use_llm_summary` pozwala Ollamie przeformułować wynik, ale po danych
narzędzia.

Założenia:

- odpowiedzi po polsku,
- krótko i konkretnie,
- liczby pochodzą z narzędzi,
- fallback informuje użytkownika, jakie pytania są obsługiwane.

## 22. Portfel aktywów

Moduł aktywów pozwala śledzić:

- akcje,
- ETF-y,
- krypto,
- cash,
- obligacje.

Model danych:

- `Asset` przechowuje symbol, nazwę, klasę aktywa, walutę, ilość, koszt bazowy
  i notatki,
- `AssetSnapshot` przechowuje punkt historyczny: datę, cenę, wartość PLN i
  źródło.

Serwisy:

- CRUD aktywów,
- odświeżanie snapshotów,
- podsumowanie portfela,
- historia wartości,
- Sankey przepływów/struktury.

Wartość portfela raportowana jest w PLN.

## 23. Profil i reguły personalne

Profil użytkownika jest pojedynczy (`id=1`) i przechowuje:

- walutę bazową,
- dzień pensji,
- miesięczny cel oszczędnościowy,
- limity kategorii.

Reguły personalne:

- mogą działać na `merchant`, `title` albo `both`,
- mogą sugerować kategorię,
- mogą ustawiać `transaction_type`,
- mogą ustawiać `is_transfer`,
- mają priorytet,
- mogą działać jako `suggest_only` albo `auto_apply`,
- mają confidence.

Ręczne przypisanie kategorii może zapamiętać regułę merchanta, ale domyślnie
jest to reguła sugestii, nie automatyczne przepisywanie historii.

## 24. ML feedback i evidence

System zbiera feedback dla:

- ręcznego ustawienia kategorii,
- czyszczenia kategorii,
- akceptacji sugestii,
- odrzucenia sugestii,
- feedbacku anomalii,
- feedbacku subskrypcji.

Warstwa evidence generuje raporty prywatnościowe:

- EDA bez raw merchant/title w publicznych przykładach,
- evidence klasyfikacji kategorii,
- evidence klasyfikacji `transaction_type`,
- evidence prognoz,
- evidence anomalii,
- evidence subskrypcji.

Założenie prywatności:

- publiczne raporty mają agregaty i aliasy,
- row-level anomaly review zostaje lokalnie w `data/private`,
- raporty z realnych danych i modele są artefaktami runtime, nie materiałem do
  commita.

## 25. Testy i jakość

Backend:

- `pytest` z coverage,
- próg coverage ustawiony na 60%,
- testy parserów,
- testy deduplikacji,
- testy API,
- testy hardeningu i auth,
- testy ML pipeline, policy, confidence, predict, train,
- testy LLM routera i narzędzi,
- testy statystyk i recap,
- testy migracji.

Lint/type checks:

- Ruff z regułami `E`, `F`, `I`, `UP`, `B`, `SIM`,
- mypy jest skonfigurowany, ale w CI nieblokujący.

Frontend:

- `npm run typecheck`,
- ESLint,
- build/lint/typecheck dostępne w `apps/web/package.json`.

CI:

- Python 3.11,
- `pip install -e ".[dev]"`,
- Ruff,
- mypy non-blocking,
- pytest,
- upload `coverage.xml`,
- Node 20,
- `npm ci`,
- TypeScript check,
- ESLint,
- non-blocking `pip-audit` i `npm audit`.

## 26. Migracje i kompatybilność danych

Projekt używa Alembic. W repozytorium są migracje obejmujące m.in.:

- schemat początkowy,
- aktywa,
- kategorie,
- źródła typu transakcji,
- odrzucanie sugestii,
- reguły personalne,
- subkategorie,
- tagi i notatki,
- taxonomy dla shopping/income,
- feedback ML,
- aliasy merchantów,
- warstwę walutową,
- preferencje subskrypcji.

Zasada operacyjna: zmiany modelu domenowego powinny uwzględniać migracje i
wpływ na API, parsery, ML i frontend.

## 27. Decyzje architektoniczne

Istniejące ADR:

- ADR-0002: hybrydowa klasyfikacja transakcji, TF-IDF + LinearSVC + lokalny LLM
  fallback + augmentacja rzadkich klas.
- ADR-0003: anomalie i subskrypcje metodami klasycznymi, bez autoencoderów i
  embeddingów LLM.
- ADR-0004: lekka obserwowalność przez structlog i health checks, bez
  Prometheus/OpenTelemetry w runtime.

Wspólne motywy decyzji:

- prywatność danych,
- wyjaśnialność,
- prostota deploymentu,
- reprodukowalność evidence,
- mały koszt operacyjny,
- brak zależności od chmury.

## 28. Aktualne ograniczenia i ryzyka

Ograniczenia produktu:

- aplikacja jest single-user, nie multi-tenant,
- BasicAuth nie jest pełnym systemem kont i ról,
- Ollama jest opcjonalna i lokalna, więc jakość oraz latency zależą od sprzętu,
- modele ML są dopasowane do małego, prywatnego datasetu,
- `transaction_type` supervised jest evidence-only i uczy się silver labels,
- klasy rzadkie wymagają ręcznego review lub augmentacji,
- `other` pozostaje kategorią niejednorodną,
- brak kursu FX może blokować import/przeliczenia dla walut obcych,
- brak Prometheus/Grafana ogranicza historyczne metryki runtime,
- `data/models`, `data/reports`, `data/private` są lokalnymi artefaktami i nie
  powinny być publikowane.

Ryzyka metodologiczne:

- drift merchantów i formatów bankowych,
- nierównowaga klas,
- confidence LinearSVC jest proxy marginesu, nie skalibrowanym
  prawdopodobieństwem,
- detekcja subskrypcji może pomijać zmienne opłaty,
- anomalie wymagają feedbacku użytkownika do oceny precision@k,
- forecast na krótkich szeregach powinien być interpretowany jako orientacyjny,
  nie jako gwarancja.

## 29. Najważniejsze pliki źródłowe

Backend i domena:

- `apps/api/main.py`,
- `apps/api/routers/*.py`,
- `src/finance/domain/models.py`,
- `src/finance/domain/enums.py`,
- `src/finance/ingestion/service.py`,
- `src/finance/transactions/rules.py`,
- `src/finance/transactions/queries.py`,
- `src/finance/transactions/mutations.py`,
- `src/finance/stats/service.py`,
- `src/finance/currencies/service.py`,
- `src/finance/profile/service.py`.

ML:

- `src/finance/ml/classification/pipeline.py`,
- `src/finance/ml/classification/train.py`,
- `src/finance/ml/classification/predict.py`,
- `src/finance/ml/classification/policy.py`,
- `src/finance/ml/transaction_type/train.py`,
- `src/finance/ml/anomaly/detector.py`,
- `src/finance/ml/subscriptions/detector.py`,
- `src/finance/ml/forecasting/pipeline.py`,
- `src/finance/ml/evidence.py`.

LLM:

- `src/finance/llm/router.py`,
- `src/finance/llm/tools.py`,
- `src/finance/llm/spending_tools.py`,
- `src/finance/llm/recommendation_tools.py`,
- `src/finance/llm/client.py`.

Frontend:

- `apps/web/src/app/layout.tsx`,
- `apps/web/src/app/api/proxy/[...path]/route.ts`,
- `apps/web/src/lib/api/client.ts`,
- `apps/web/src/lib/api/types.ts`,
- `apps/web/src/lib/nav.ts`,
- `apps/web/src/app/*/page.tsx`.

Dokumentacja:

- `README.md`,
- `docs/project-overview.md`,
- `docs/model-card.md`,
- `docs/ml-evidence.md`,
- `docs/adr/0002-hybrid-classifier.md`,
- `docs/adr/0003-anomaly-subscription-detection.md`,
- `docs/adr/0004-observability.md`.

## 30. Podsumowanie metodyki projektu

Projekt jest zbudowany wokół kilku spójnych zasad:

- logika finansowa jest deterministyczna,
- LLM jest warstwą językową i routingową, nie kalkulatorem faktów,
- ML jest klasyczny, mierzalny i raportowany,
- import i agregacje mają wspólne reguły filtrowania,
- typ transakcji jest oddzielony od kategorii budżetowej,
- prywatne dane i artefakty pozostają lokalne,
- dashboard jest operacyjnym narzędziem do pracy na danych,
- deployment jest możliwy na jednym hoście przez Docker Compose,
- jakość jest wzmacniana przez testy, CI, ADR i raporty evidence.
