# Funkcje Aplikacji, Status i Roadmapa

Stan na: **2026-06-05**. Ten dokument jest produktową mapą projektu: co już
mamy w aplikacji, jaki jest status poszczególnych modułów i co warto zaplanować
dalej. Główne `README.md` pozostaje dokumentem startowym do uruchomienia
projektu i opisem architektury.

## Zakres

Projekt to self-hostowany system analizy finansów osobistych:

- ścieżka produkcyjnego demo: **Next.js dashboard -> FastAPI -> PostgreSQL**,
- ścieżka badawcza/evidence: **scripts + moduły ML + lokalne notebooki bez prywatnych outputów**,
- ścieżka AI/ML: **klasyfikacja, prognozowanie, anomalie, subskrypcje i lokalny
  asystent LLM**,
- model prywatności: realne eksporty bankowe, artefakty modeli i prywatne
  raporty zostają lokalnie.

Aktualny fokus to **Phase 12 - personalizacja i poprawa jakości AI/ML**.
System jest funkcjonalny, ale jakość wyników ML nadal zależy głównie od
czystego importu, ręcznego review kategorii i świeżych raportów evidence
zbudowanych na realnych danych lokalnych.

## Legenda Statusów

| Status | Znaczenie |
|---|---|
| Gotowe | Funkcja jest zaimplementowana i działa w normalnym flow aplikacji. |
| W trakcie | Funkcja istnieje częściowo albo wymaga walidacji na realnych danych. |
| Planowane | Sensowny kolejny krok, ale nie jest konieczny do obecnego demo. |
| Odłożone | Świadomie poza aktualnym zakresem pracy/demo. |

## Mapa Funkcji

| Obszar | Funkcja | Status | Uwagi |
|---|---|---|---|
| Import danych | Import Pekao SA | Gotowe | Parser CSV/XLSX i mapowanie kategorii bankowych tam, gdzie etykieta jest użyteczna. |
| Import danych | Import Revolut | Gotowe | Obsługa statementów PLN/USD i generycznego mapowania kolumn. |
| Import danych | Generyczny import CSV/XLSX | Gotowe | Preview nagłówków, ręczne mapowanie kolumn i fallback parsera. |
| Import danych | Deduplikacja | Gotowe | Deterministyczne hashe importu ograniczają duplikaty przy ponownym imporcie. |
| Import danych | Reguły `transaction_type` | Gotowe | Wykrywa zakup, przelew własny, przelew do osoby, pensję, inny przychód, zwrot, bankomat, opłatę bankową i oszczędności/inwestycje. |
| Import danych | Reguły personalne przed ML | W trakcie | Reguły merchant/title mogą sugerować lub automatycznie ustawiać kategorię, typ i transfer. Wymaga strojenia po realnym imporcie. |
| Transakcje | Tabela transakcji | Gotowe | Filtrowanie, paginacja, inline edit kategorii i bulk categorization. |
| Transakcje | Tryb "Do przypisania" | Gotowe | Priorytetyzuje brak kategorii, brak sugestii i niskie confidence. |
| Transakcje | Akceptacja/odrzucanie sugestii ML | Gotowe | Akceptacja zamienia sugestię w etykietę manualną; odrzucenie usuwa błędną sugestię z kolejki. |
| Kategorie | 9 głównych kategorii wydatkowych | Gotowe | `food`, `transport`, `subscriptions`, `health`, `entertainment`, `housing`, `savings`, `shopping`, `other`. |
| Kategorie | `transaction_type` oddzielony od kategorii | Gotowe | Przelewy, pensje, inne przychody, zwroty, gotówka, opłaty i inwestycje nie zanieczyszczają kategorii wydatkowych. |
| Kategorie | Katalog kategorii custom | Gotowe | Dostępny w API/UI, ale taksonomia ML pod pracę magisterską zostaje oparta o 9 kategorii systemowych. |
| Profil | Lokalny profil użytkownika | Gotowe | Waluta bazowa, dzień pensji, miesięczny cel oszczędnościowy i limity kategorii. |
| Profil | Reguły merchant/title | Gotowe | CRUD w ustawieniach i API. Domyślnie działają jako sugestia, zaufane reguły mogą mieć `auto_apply`. |
| Pulpit | Główny dashboard KPI | Gotowe | Przychody, wydatki, cashflow netto, stopa oszczędności i ostatnie transakcje. |
| Pulpit | Wykresy cashflow, kategorii, net worth i merchantów | Gotowe | Semantyka transferów i potwierdzonych kategorii jest spójna ze statystykami backendu. |
| Import UI | Upload i preview importu | Gotowe | Strona Next.js do preview, mapowania i historii importów. |
| Assets | Opcjonalny portfel inwestycyjny | Gotowe | Funkcja poboczna z yfinance, snapshotami i widokami portfolio. Nie jest rdzeniem ML pracy. |
| Stats API | Overview/cashflow/by-category/net worth/top merchants | Gotowe | Domyślnie potwierdzone kategorie; predykcje tylko na jawnym parametrze diagnostycznym. |
| Bezpieczeństwo | BasicAuth | Gotowe | Opcjonalne auth z env; health endpointy zostają publiczne. |
| Bezpieczeństwo | Hardening importu/eksportu CSV | Gotowe | Limity pliku, MIME/extension checks i zabezpieczenie przed formula injection. |
| Obserwowalność | Logi i health checks | Gotowe | structlog, request ID, `/health`, `/health/live`, `/health/ready`. |
| Obserwowalność | Prometheus/Grafana | Odłożone | Usunięte z aktualnego zakresu jako nadmiarowe dla single-user self-hosted demo. |

## Komponenty AI/ML

| Komponent | Co robi | Status | Uwagi jakościowe |
|---|---|---|---|
| Klasyfikacja transakcji | Sugeruje jedną z 9 kategorii wydatkowych. | W trakcie | Baseline TF-IDF + LinearSVC, porównanie z Logistic Regression/RF/Dummy, opcja calibrated LinearSVC i eksperyment feature-v2. Jakość zależy od potwierdzonych etykiet. |
| Klasyfikacja `transaction_type` | Raportuje wieloklasowy eksperyment typu transakcji. | Gotowe | Evidence-only model na silver labels z `Transaction.transaction_type`; porównuje Dummy/LogReg/LinearSVC i nie zastępuje reguł runtime. |
| Diagnostyka confidence | Zwraca kategorię, confidence, źródło, kategorię modelu, próg i informację o fallbacku. | Gotowe | Runtime i evidence używają tej samej interpretacji confidence. |
| Opcjonalny LLM fallback | Używa lokalnej Ollamy tylko przy niskim confidence i tylko dla pojedynczej klasyfikacji, gdy użytkownik to włączy. | Gotowe | Nie jest używany w masowym reclassify, żeby nie generować wolnych i niestabilnych wywołań. |
| Kolejka sugestii ML | Wypełnia `category_predicted` dla nieoznaczonych transakcji podobnych do wydatków. | Gotowe | Sugestia nie jest ground truth, dopóki użytkownik jej nie zaakceptuje. |
| Feature-v2 classification | Dodaje `merchant_norm`, `transaction_type`, `source`, amount bucket i month. | W trakcie | Tylko evidence/eksperyment, dopóki nie wygra wyraźnie z baseline na macro-F1 i threshold accuracy. |
| Augmentacja LLM | Generuje syntetyczne opisy transakcji dla rzadkich klas. | W trakcie | Musi być raportowana osobno jako `real_only` vs `augmented`; nie zastępuje realnych etykiet. |
| Forecasting | Prognozuje miesięczne wydatki per kategoria albo globalnie. | Gotowe | Naive, Mean3, SES i ARIMA z walk-forward CV. Wymaga wystarczającej historii miesięcznej. |
| Detekcja anomalii | Flagi nietypowych wydatków. | Gotowe | Hybrid IsolationForest + robust z-score + reguły. Wymaga prywatnego review precision@20/50 na świeżych danych. |
| Detekcja subskrypcji | Wykrywa powtarzalne obciążenia. | Gotowe | Interpretowalny detector kadencji oparty o normalizację merchanta, stabilność kwoty i cykliczność. |
| Asystent LLM | Polski asystent do pytań i rekomendacji. | Gotowe | Najpierw heuristic routing i deterministic tools; LLM tylko opisuje wyniki i nie wymyśla liczb. |
| ML evidence package | Buduje raporty classification, transaction type, EDA, forecasting, anomaly summary, subscriptions i wspólny evidence package. | W trakcie | Kod raportów jest gotowy; nadal trzeba wygenerować świeże `latest_*` po czystym imporcie i ręcznym review. |

## Aktualne Luki

- Największą luką dowodową są świeże raporty clean-start:
  `latest_classification.json`, `latest_transaction_type_classification.json`,
  `latest_eda.json`, `latest_forecasting.json`,
  `latest_anomaly_summary.json`, `latest_subscriptions.json`,
  `latest_evidence_package.json` i `summary.md`
  po nowym imporcie realnych danych oraz ręcznym review kategorii.
- `transaction_type` w evidence jest silver-label eksperymentem. Daje
  spełnienie wymogu wieloklasowej analizy typu transakcji, ale nie jest jeszcze
  niezależnym modelem produkcyjnym.
- Jakość klasyfikacji zależy od liczby i balansu potwierdzonych etykiet.
  Nie trenować na `category_predicted`; ground truth to tylko zaakceptowane lub
  ręcznie ustawione `category`.
- Feature-v2 istnieje, ale powinno pozostać eksperymentem, dopóki nie wygra z
  baseline na realnych danych clean-start.
- Anomalie wymagają prywatnego review: oznaczyć top 20/50 flag i publikować
  tylko zagregowane precision, bez raw transakcji.
- Subskrypcje skorzystają na feedbacku użytkownika: potwierdzone, ignorowane i
  stałe merchanty.
- Asystenta LLM warto rozwijać przez deterministic tools, nie przez proszenie
  modelu o liczenie faktów z promptu. RAG w projekcie należy opisywać jako
  hybrydę: function calling / heuristic routing + lokalny LLM do opisu wyników.

## Planowane Funkcje

### Phase 13 - Jakość danych i eksperymenty z datasetami zewnętrznymi

- Dodać lokalny workflow przygotowania datasetów zewnętrznych w `scripts/`:
  HuggingFace/Kaggle/Plaid-like data -> znormalizowane transakcje -> mapowanie
  do 9 kategorii.
- Porównać warianty `real_only`, `external_only`, `mixed` i
  `mixed + calibration`.
- Dodać jawnie opisaną tabelę mapowania obcych kategorii do naszych 9 klas.
- Trzymać raw pliki zewnętrzne w `data/external/` albo poza repo.
- Podjąć decyzję, czy feature-v2 ma zostać domyślnym modelem runtime.

Stan implementacji:

- Kaggle `ramyapintchy/personal-finance-data` jest obsługiwany przez
  `scripts/prepare_external_classification_data.py`.
- Dataset jest mapowany do lokalnego schematu klasyfikacji i może być
  raportowany jako osobne eksperymenty `external_only` oraz
  `real_plus_external`.
- HF `mitulshah/transaction-categorization` ma obecnie w repo metadane i mapę
  kategorii; właściwy parquet trzeba dodać lokalnie przed integracją.

Przykładowe komendy lokalne:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_external_classification_data.py
.\.venv\Scripts\python.exe -m finance.ml.classification.train --from-db --external-kaggle data\external\kaggle_personal_finance_data\Personal_Finance_Dataset.csv
```

### Phase 14 - Active learning i UX review

- Dodać liczniki review:
  brak kategorii, brak sugestii, low confidence, high confidence i odrzucone
  sugestie.
- Dodać akcję "zapamiętaj tego odbiorcę" bezpośrednio w review transakcji.
- Priorytetyzować review według wartości dla ML: rzadkie klasy, low confidence
  i często powtarzający się merchant.
- Dodać diagnostykę, dlaczego dana transakcja jest albo nie jest kandydatem do
  sugestii kategorii.

### Phase 15 - Lepsza personalizacja

- Rozszerzyć reguły personalne o ignorowane merchanty dla subskrypcji i
  anomalii.
- Dodać feedback: subskrypcja potwierdzona/ignorowana.
- Mocniej używać limitów kategorii i celu oszczędnościowego w deterministic
  recommendations.
- Dodać diagnostykę konfliktów, gdy kilka reguł personalnych pasuje do jednej
  transakcji.

### Phase 16 - Pakiet finalny pod obronę

- Wygenerować świeże raporty evidence na czystej lokalnej bazie.
- Zaktualizować `docs/model-card.md`, `docs/ml-evidence.md` i
  `docs/project-overview.md` aktualnymi metrykami.
- Przygotować stabilny scenariusz demo:
  import -> sugestie kategorii -> review -> retrain/reclassify -> dashboard
  -> forecast -> anomalies -> subscriptions -> assistant.
- Trzymać raw CSV, prywatne review i artefakty modeli poza gitem.

## Inspiracje z Profesjonalnych Aplikacji

Research na dzień **2026-05-29**. Poniższe punkty nie są wymaganiami do
obecnego demo, tylko backlogiem pomysłów z rynku aplikacji personal finance.

### Co robią dobrze aplikacje komercyjne i open-source

| Aplikacja | Wyróżniające funkcje | Co warto przenieść do naszego projektu |
|---|---|---|
| [YNAB](https://www.ynab.com/features/) | Bank import, praca na wielu urządzeniach, offline sync, współdzielenie z rodziną, category templates i custom views. | Prostszy tryb budżetowania oparty o realny cashflow i szablony kategorii. |
| [Monarch Money](https://help.monarch.com/hc/en-us/articles/360048883631-Creating-Your-Budget-in-Monarch) | Budżet miesięczny oparty o cashflow: income = expenses + savings, cele, raporty i household/collaboration. | Lepsze połączenie budżetu, celu oszczędnościowego i rekomendacji. |
| [Monarch AI](https://help.monarch.com/hc/en-us/articles/16116906962452-About-Monarch-s-AI-Features) | AI Assistant, AI Insights i Weekly Recap, z opcjonalnym kontekstem gospodarstwa domowego. | Tygodniowe/miesięczne podsumowania deterministyczne + LLM tylko do opisu. |
| [Copilot Money](https://help.copilot.money/en/articles/3971267-transaction-types) | Silne rozdzielenie transaction types: Income, Internal Transfer, Regular; korekty mogą tworzyć reguły. | To potwierdza nasz kierunek: typ transakcji osobno od kategorii wydatkowej. |
| [Copilot Recurrings](https://help.copilot.money/en/articles/3760068-creating-recurrings) | Ręczne i półautomatyczne tworzenie harmonogramów recurring, także non-monthly. | Edycja/pauzowanie/archiwizacja wykrytych subskrypcji i rachunków. |
| [Rocket Money](https://help.rocketmoney.com/en/articles/2677184-premium-membership-features) | Custom budgets, tags, notes, transaction splitting, automation rules, subscription cancellation, goals i net worth. | Tags, notes, split transactions i reguły automatyzacji są wartościowe; cancellation/bill negotiation poza zakresem. |
| [PocketGuard](https://pocketguard.com/) | Prosty widok spendable money po odjęciu rachunków, celów i koniecznych wydatków. | Widok "ile mogę jeszcze wydać" na bazie forecastu, limitów i stałych płatności. |
| [PocketSmith](https://www.pocketsmith.com/features/) | Cash projections, what-if scenarios i budget calendar. | Scenariusze "co jeśli" i kalendarz przyszłych płatności dobrze pasują do naszego forecastingu. |
| [Tiller](https://help.tiller.com/en/articles/3279649-what-is-tiller-and-how-does-it-work) | Spreadsheet-first workflow, pełna kontrola danych, automatyczne feedy i elastyczne szablony. | Eksport do CSV/XLSX i widoki pod analizę w arkuszu jako funkcja dla zaawansowanych. |
| [Lunch Money](https://lunchmoney.app/features) | Import przez bank/CSV/API, tags, rules engine, recurring expenses, calendar, multi-currency, analytics. | Rules engine, tags, calendar i multi-currency są najbliżej naszego zakresu. |
| [Actual Budget](https://actualbudget.org/) | Local-first, prywatność, envelope budgeting, sync, opcjonalne E2EE i custom reports. | Wzmocnić narrację privacy-first/self-hosted i dodać więcej raportów konfigurowalnych. |

### Pomysły o Największym Zwrocie dla Naszej Aplikacji

1. **Review Center**
   Osobny panel jakości danych: transakcje bez kategorii, niskie confidence,
   brak sugestii, odrzucone sugestie, powtarzalni merchanty bez reguł i klasy
   rzadkie. To bezpośrednio poprawia dane treningowe i jakość ML.

2. **Available to spend**
   Widok kwoty dostępnej do końca miesiąca po odjęciu stałych płatności,
   celów oszczędnościowych, oczekiwanych rachunków i limitów kategorii. To
   łączy obecny profil, subskrypcje, forecast i statystyki.

3. **Kalendarz płatności**
   Kalendarz wykrytych subskrypcji, rachunków, pensji i przewidywanych dużych
   wydatków. Powinien pozwalać oznaczać pozycje jako potwierdzone, ignorowane,
   pauzowane albo roczne/kwartalne.

4. **What-if scenarios**
   Proste scenariusze: "co jeśli obniżę jedzenie o 10%", "co jeśli anuluję
   Netflix", "co jeśli zwiększę cel oszczędności o 300 PLN". Obliczenia
   deterministyczne, LLM tylko tłumaczy wynik.

5. **Tags, notes i split transactions**
   Kategorie są za mało elastyczne do wszystkich analiz. Tagi i notatki dają
   drugą oś opisu bez rozbudowy klas ML. Split transakcji przyda się dla
   zakupów mieszanych, np. market + chemia + prezent.

6. **Reguły automatyzacji z diagnostyką**
   Rozwinąć personal rules o testowanie reguły na historii, wykrywanie
   konfliktów, priorytety, podgląd "co ta reguła zmieni" i osobny tryb
   `suggest_only` vs `auto_apply`.

7. **Weekly/monthly recap**
   Automatyczne podsumowanie tygodnia/miesiąca: największe zmiany kategorii,
   top merchanty, przekroczone limity, nowe subskrypcje, anomalie i postęp
   celu oszczędnościowego. Dane liczone przez tool functions.

8. **Saved views i eksport analityczny**
   Zapisywane filtry w transakcjach oraz eksport do CSV/XLSX dla arkuszy.
   To jest prostsze niż budowa pełnego modułu BI, a daje użyteczność podobną do
   Tiller/Lunch Money.

9. **Personal context dla AI**
   Opcjonalne dane kontekstowe: gospodarstwo domowe, stałe koszty, koszty
   nienaruszalne, preferencje oszczędzania i priorytety. Nie jako demografia do
   modelu, tylko jako deterministic context dla rekomendacji.

10. **Konfigurowalne raporty**
    Raporty typu: cashflow, budget vs actual, category trends, merchant trends,
    transfer audit, subscriptions, anomaly review, savings goal progress.
    Przydatne zarówno dla użytkownika, jak i pod obronę.

### Funkcje Świadomie Mniej Istotne

- Automatyczne anulowanie subskrypcji i negocjowanie rachunków: ciekawe
  produktowo, ale wymaga integracji z usługami zewnętrznymi i wychodzi poza
  self-hosted/privacy-first zakres.
- Credit score i raport kredytowy: mocno zależne od rynku USA, mało użyteczne
  dla tej pracy.
- Pełna współpraca rodzinna/multi-user: wartościowe w SaaS, ale sprzeczne z
  aktualnym single-user/self-hosted założeniem.
- Automatyczne transfery oszczędnościowe: wymaga uprawnień do wykonywania
  operacji finansowych; niepotrzebne ryzyko w projekcie magisterskim.
- Mobilne widgety i natywna aplikacja: dobry polish, ale niższy zwrot niż
  jakość danych, evidence ML i stabilny dashboard.

## Docelowe Dane dla Lepszej Jakości AI/ML

Do sensownej ewaluacji clean-start:

- klasyfikacja minimum: **300-500 potwierdzonych etykiet**,
- klasyfikacja docelowo: **800-1500 potwierdzonych etykiet**,
- częste kategorie: **100+ przykładów** każda,
- rzadkie kategorie: **40-60 minimum**, **80-120 preferowane**,
- reguły `transaction_type`: **20-50 przykładów** dla przelewu własnego,
  przelewu do osoby, pensji, zwrotu, bankomatu, opłaty bankowej i inwestycji,
- forecasting: **6 miesięcy minimum**, **12-24 miesiące preferowane**,
- anomaly/subscription review: minimum **top 20/50 ręcznie ocenionych anomalii**
  oraz kilka miesięcy powtarzalnych transakcji.

Mieszane dane PL/EN są akceptowalne. Model powinien widzieć realistyczne opisy
bankowe w oryginalnym języku, zamiast opisów tłumaczonych sztucznie.

## Poza Aktualnym Zakresem

- Multi-user SaaS, OAuth, billing i izolacja tenantów.
- Fine-tuned transformer classifier bez porównania z TF-IDF baseline.
- LLM jako źródło prawdy dla sum finansowych.
- Automatyczna integracja bankowa online.
- Stos Prometheus/Grafana.
- Commitowanie realnych eksportów bankowych, prywatnych review anomalii albo
  lokalnych artefaktów modeli.
