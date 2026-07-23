# Aktualne metodyki i rozwiązania

Stan na 2026-07-22. Dokument opisuje rozwiązania faktycznie obecne w kodzie.
Nie zawiera wyników z prywatnych danych; kryteria modelu kategorii znajdują się
w [model card](model-card.md).

## 1. Założenia projektu

Aplikacja jest samo-hostowanym systemem single-user do analizy finansów
osobistych. Obejmuje import danych bankowych, ręczne wprowadzanie i korektę
transakcji, analitykę, klasyczne ML oraz opcjonalnego lokalnego asystenta
językowego.

Najważniejsze zasady:

- fakty finansowe i agregacje są deterministyczne;
- LLM może wyłącznie dobrać narzędzie dla nierozpoznanego pytania; wynik jest
  formatowany deterministycznie;
- sugestia nie jest etykietą treningową bez decyzji użytkownika;
- typ przepływu pieniędzy jest oddzielony od kategorii budżetowej;
- modele i raporty z realnych danych pozostają lokalne;
- preferowane są proste i wyjaśnialne metody zamiast ciężkich modeli.

## 2. Architektura

```text
apps/web (Next.js)
  -> /api/proxy/*
  -> apps/api (FastAPI)
  -> src/finance (logika domenowa)
  -> PostgreSQL

Opcjonalnie: FastAPI -> lokalny Ollama
```

Granice odpowiedzialności:

- `apps/api`: routery, schematy HTTP, middleware i bezpieczeństwo;
- `apps/web`: polski interfejs i obsługa stanów loading/error/empty;
- `src/finance/domain`: modele SQLAlchemy, enumy i DTO;
- `src/finance/ingestion`: parsery i import;
- `src/finance/transactions`: zapytania, mutacje, reguły i review;
- `src/finance/fixed_charges`: harmonogramy opłat i powiązania płatności;
- `src/finance/stats`: agregacje dashboardu i podsumowań;
- `src/finance/ml`: klasyfikacja, forecasting, anomalie, subskrypcje i evidence;
- `src/finance/llm`: routing, narzędzia, formatowanie i klient Ollama.

Routery API pozostają cienkie; logika biznesowa jest współdzielona przez API,
skrypty i testy z poziomu `src/finance`.

## 3. Import, normalizacja i waluty

Obsługiwane są eksporty Pekao, Revolut oraz pliki generyczne z ręcznym
mapowaniem kolumn. Parsery zwracają wspólny `TransactionDTO`, zachowując m.in.
oryginalny opis bankowy, kategorię i rodzaj operacji.

Przebieg importu:

1. Walidacja rozszerzenia, MIME, rozmiaru i wymaganych pól.
2. Parsowanie do wspólnego schematu.
3. Normalizacja merchanta i kierunku przepływu.
4. Przeliczenie na PLN według daty księgowania.
5. Wyliczenie stabilnego `dedup_hash`.
6. Zapis transakcji i bezpiecznych sugestii.

`amount` przechowuje kwotę oryginalną, a `amount_base` kwotę analityczną w PLN.
Kurs jest dobierany dla konkretnego dnia; w razie braku notowania dostawca może
użyć ograniczonego lookbacku. Dla waluty obcej brak poprawnego kursu nie jest
zastępowany kursem `1`: rekord pozostaje widoczny, ale nie trafia do agregacji,
filtrów kwotowych ani datasetów.

Deduplication chroni przed ponownym importem tej samej operacji. Jeżeli źródło
dostarcza godzinę księgowania, jest ona częścią skrótu, dzięki czemu dwie
identyczne kwotowo operacje z jednego dnia nie są automatycznie scalane.
Oryginalne pola pozostają dostępne do audytu i eksportu.

Pojedynczą transakcję można również dodać ręcznie. Korzysta ona z tych samych
reguł walidacji kwoty, waluty, typu i kategorii co pozostałe mutacje, otrzymuje
źródło `manual` i może być później edytowana. Tryb edycji nie obejmuje rekordów
pochodzących z importu, aby nie zacierać ich bankowego pochodzenia.

## 4. Model transakcji

System rozdziela dwa niezależne wymiary:

- `transaction_type`: znaczenie ekonomiczne przepływu;
- `category`: kategoria budżetowa kwalifikującego się wydatku.

Typy transakcji:

`expense`, `salary`, `income`, `refund`, `own_transfer`, `cash_withdrawal`,
`debt_payment`, `asset_allocation`, `other`.

Kategorie systemowe:

`food`, `transport`, `subscriptions`, `health`, `entertainment`, `housing`,
`savings`, `shopping`, `other`.

`is_transfer` jest pochodną `transaction_type == own_transfer`. Kategorie nie
są przypisywane do wpływów, przelewów własnych ani innych przepływów, które nie
są kandydatami na wydatek. Zmiana typu może więc wyczyścić niepasującą kategorię
lub sugestię, a każda decyzja użytkownika jest audytowana.

Kategorie własne i subkategorie są dostępne w aplikacji, lecz klasyfikator
kategorii v1 korzysta wyłącznie z dziewięciu klas systemowych.

## 5. Sugestie i review

Źródła kategorii i typów są jawnie rozróżniane: decyzja ręczna, reguła
personalna, mapowanie bankowe, reguła systemowa, model oraz opcjonalny LLM.

Zasady użytkowe:

- ręczna decyzja i zaakceptowana sugestia są potwierdzone;
- mapowania bankowe i reguły systemowe pozostają sugestiami;
- reguła personalna `suggest_only` nie zmienia aktywnej wartości;
- świadomie utworzona reguła `auto_apply` może ustawić wartość prowizoryczną,
  ale nie tworzy gold label;
- odrzucenie sugestii nie zmienia transakcji w etykietę treningową;
- przeliczanie kategorii nie modyfikuje typu transakcji.

Widok review rozdziela typy i kategorie, umożliwia szybkie potwierdzanie oraz
grupowanie powtarzalnych przypadków. Szczegóły provenance są dostępne dla
diagnostyki, ale nie dominują podstawowej listy transakcji.

## 6. Analityka finansowa

Dashboard, recap i narzędzia LLM korzystają ze wspólnych filtrów domenowych i
kwot bazowych. Przelewy własne oraz wypłaty gotówki nie są wydatkami
budżetowymi. Zwroty pomniejszają wydatki odpowiedniej kategorii, a spłaty długu
i alokacje aktywów są raportowane osobno.

Główne agregacje obejmują:

- przychody, wydatki netto i cashflow;
- wydatki według kategorii i merchantów;
- trendy miesięczne oraz porównania okresów;
- histogram i statystyki kwot;
- deterministyczne rekomendacje na podstawie zmian okresowych, kategorii,
  największych merchantów, subskrypcji i anomalii.

## 7. Klasyfikacja kategorii wydatków

To podstawowy workflow ML aplikacji. Model przewiduje kategorię wyłącznie dla
transakcji kwalifikujących się jako `expense`.

### Dane treningowe

Gold label wymaga jednocześnie:

- kategorii z ontologii systemowej;
- metody `manual` albo `accepted_suggestion`;
- daty potwierdzenia;
- semantyki wydatku i kierunku debit.

Etykiety bankowe, reguły systemowe, `personal_rule_auto`, niezaakceptowane
predykcje oraz kategorie własne są wykluczone. Zamrożone rekordy testowe są
wyłączane z treningu.

### Cechy i modele

Promowalny baseline wykorzystuje:

- `merchant + title` jako tekst;
- `abs_amount` po transformacji `log1p`;
- dzień tygodnia.

Tekst jest reprezentowany przez word TF-IDF 1-2 oraz `char_wb` TF-IDF 3-5.
Domyślny job porównuje dokładnie:

- Logistic Regression;
- kalibrowany LinearSVC.

Feature-v2, Dummy, zwykły LinearSVC i Random Forest są dostępne wyłącznie w
jawnym trybie benchmarkowym. Nie tworzą aktywowalnego modelu.

### Walidacja

Trening wymaga co najmniej 300 gold labels. Do modelu wchodzą klasy mające co
najmniej 10 przykładów; muszą istnieć przynajmniej dwie takie klasy.

Dwa równorzędne przekroje walidacyjne to:

- time holdout z najnowszych transakcji;
- merchant holdout grupujący warianty tego samego merchanta.

Jeżeli obu przekrojów nie da się zbudować, job kończy się czytelną diagnostyką.
Ranking maksymalizuje słabszy macro-F1 z obu holdoutów, następnie ich średnią,
covered accuracy i latency. OOF z `StratifiedKFold` służy do diagnostyki
kalibracji, nie zastępuje głównych holdoutów.

Raportowane są macro-F1, weighted-F1, metryki klas, macierze pomyłek,
coverage/covered accuracy, log-loss, Brier score, ECE, reliability bins i p99.

### Confidence i bramki

Runtime zawsze używa progu `0.55`. Potencjalne progi wyliczone z OOF są
zapisywane diagnostycznie, ale nie sterują aplikacją. Kategoria `other` zawsze
pozostaje do weryfikacji.

Techniczna aktywacja wymaga:

- minimum 300 potwierdzonych etykiet;
- macro-F1 co najmniej `0.60` na obu holdoutach;
- p99 do `200 ms` dla rozgrzanych predykcji bez LLM;
- braku regresji powyżej `0.02` tylko wtedy, gdy oba modele są oceniane na tym
  samym zamrożonym evaluation set.

Wymagania finalnego evidence są celowo oddzielone od zwykłego runtime i nie
blokują codziennego użycia aplikacji.

### Lifecycle artefaktu

Trening jest wyłącznie jawną akcją użytkownika. Jeden lokalny slot joba ma stany
`queued`, `running`, `completed`, `failed` i `interrupted`. Restart procesu
przerywa job; ponowienie jest ręczne.

Każdy kandydat przechowuje pipeline, klasy, schemat cech, politykę confidence,
metryki, fingerprint danych, wersję evaluation set, wersje środowiska i SHA-256.
Aktywacja jest ręczna i wykonuje kontrolę zgodności oraz smoke test. Poprzedni
kompatybilny model może zostać ponownie aktywowany jako rollback.

Nie ma schedulera retrainingu ani ścieżki `classifier_latest.joblib`. Runtime
ładuje tylko artefakt wskazany przez aktywny rekord w bazie. Brak lub
niezgodność artefaktu zwraca kontrolowany `model_retrain_required`.

## 8. Typ transakcji

Runtime typu pozostaje prostą warstwą hybrydową:

1. potwierdzona decyzja użytkownika nie jest nadpisywana;
2. reguła personalna może sugerować lub ustawić prowizoryczny typ;
3. jednoznaczne mapowania bankowe i systemowe tworzą sugestie;
4. zwykły fallback kierunku daje `debit -> expense`, `credit -> income` bez
   dodawania elementu do kolejki review.

Ogólne słowa, takie jak „przelew”, nie są wystarczającym powodem do silnego
automatycznego przypisania. Nietypowa ręczna kombinacja kierunku i typu wymaga
świadomego potwierdzenia.

Model `transaction_type` jest osobnym eksperymentem evidence-only. Trenuje się
wyłącznie na ręcznych typach i zaakceptowanych sugestiach, wykorzystując tekst
z `raw_transaction_type`, kwotę, kierunek i źródło. Porównuje Dummy, Logistic
Regression oraz kalibrowany LinearSVC. Jego wynik nie uczestniczy w runtime.

## 9. Pozostałe moduły analityczne

### Forecasting

Prognoza korzysta wyłącznie z zakończonych miesięcy. Wymaga co najmniej 12
miesięcy historii, 6 miesięcy z wydatkami i przynajmniej 6 okien walidacji;
minimalna długość szeregu rośnie wraz z wybranym horyzontem. Porównywane są
Naive, rolling mean, SES, tłumiony trend Holta i seasonal-naive. Model z trendem lub
sezonowością jest wybierany tylko wtedy, gdy poprawia RMSE najlepszego prostego
baseline'u o co najmniej 5%. W przeciwnym razie aplikacja jawnie prezentuje
prognozę bazową. Moduł pozostaje provisional.

### Anomalie

Detektor łączy IsolationForest, robust z-score oparty na medianie i MAD oraz
reguły, np. nowy merchant z dużą kwotą. Wynik zawiera priorytet i czytelne
powody. Jakość wymaga prywatnego review top-k; anomalia nie oznacza oszustwa.

### Subskrypcje

Normalizowane transakcje są grupowane według merchanta, a następnie oceniane po
kadencji i stabilności kwoty. Wynik zawiera częstotliwość, confidence i
szacowany koszt miesięczny. To detektor wzorca, nie klasyfikator nadzorowany.

Stałe opłaty są odrębnym, ręcznie utrzymywanym harmonogramem planowanych
kosztów w PLN. Terminy są przesuwane kalendarzowo, a podsumowanie pokazuje
ekwiwalent miesięczny, roczny i płatności z najbliższych 30 dni. Harmonogram
nie generuje transakcji automatycznie i nie zmienia statystyk faktycznie
zaksięgowanych kwot. Użytkownik może przypisać istniejącą transakcję albo jawnie
dodać ręczną płatność do terminu opłaty. Powiązanie można cofnąć; nie
modyfikuje ono typu ani kategorii transakcji.

Forecasting oraz detekcja anomalii i subskrypcji pozostają `provisional` w
pakiecie evidence do czasu osobnej walidacji. Ręczne harmonogramy stałych opłat
są funkcją operacyjną i nie są modułem ML.

## 10. Lokalny asystent LLM

Asystent najpierw rozpoznaje polską intencję, a następnie wywołuje
deterministyczne narzędzie dotyczące wydatków, cashflow, merchantów, prognoz,
anomalii, subskrypcji lub rekomendacji. Dla pytań nierozpoznanych przez reguły
lokalna Ollama może dobrać jedno z dostępnych narzędzi. Odpowiedź końcowa jest
zawsze tworzona przez kontrolowany formatter z wyniku narzędzia; LLM nie
redaguje ani nie przelicza faktów finansowych.

Ollama może działać wyłącznie pod `localhost`, `127.0.0.1`, `::1` albo
`host.docker.internal`. Fallback kategorii wymaga globalnej flagi oraz
`use_llm_fallback=true` w żądaniu. Wynik LLM ma `confidence=null`, zachowuje
osobno `model_confidence` i zawsze pozostaje sugestią.

## 11. Evidence i prywatność

Generator evidence pracuje na spójnym snapshotcie bazy i zapisuje tylko
agregaty, aliasy oraz fingerprinty. Raport publiczny nie zawiera raw merchantów,
tytułów ani numerów rachunków. Row-level anomaly review trafia do
`data/private`.

Pakiet obejmuje pięć sekcji:

- klasyfikację kategorii;
- eksperyment typu transakcji;
- forecasting;
- anomalie;
- subskrypcje.

Profil `classification-strict` wymaga kompletnej klasyfikacji kategorii i
dopuszcza pozostałe moduły jako provisional. Szczegółowy przebieg znajduje się w
[ml-evidence.md](ml-evidence.md).

## 12. Uruchomienie, bezpieczeństwo i jakość

Jedynym wspieranym runtime Python jest 3.12. `uv.lock` jest źródłem wersji
zależności, a Docker używa `uv sync --frozen`. Stack lokalny składa się z
PostgreSQL, API i web uruchamianych przez Docker Compose.

Wdrożenie single-user może opcjonalnie używać BasicAuth. Niezależna blokada po
nieaktywności jest domyślnie wyłączona; po skonfigurowaniu backend egzekwuje
czas sesji i wymaga lokalnego kodu do ponownego odblokowania interfejsu. Nie
zastępuje to blokady systemu operacyjnego, HTTPS ani ochrony plików i bazy.

Kontrole jakości:

- pytest z coverage;
- Ruff i Mypy;
- testy migracji Alembic;
- frontend lint, typecheck i build;
- walidacja Docker Compose;
- testy generatora evidence i ochrony prywatności.

Projekt jest w aktywnej fazie rozwoju i nie gwarantuje migracji historycznych
lokalnych datasetów pomiędzy każdą iteracją. Migracje Alembic utrzymują schemat,
ale zmiana eksperymentalnej ontologii może wymagać czystego importu.

## 13. Ograniczenia

- Moduł aktywów oczekuje na osobną przebudowę; backend, tabele i wyceny nie są
  częścią bieżącej implementacji, a frontend pokazuje wyłącznie placeholder.
- Wyniki dotyczą jednego prywatnego użytkownika i nie dowodzą generalizacji na
  populację.
- Małe oraz niezbalansowane klasy dają niestabilne metryki.
- Próg `0.55` wymaga oceny na rzeczywistych OOF; nie jest gwarancją accuracy.
- Drift merchantów i formatów bankowych może obniżać jakość.
- Forecasting jest blokowany przy zbyt krótkiej historii, a przechodzące
  prognozy nadal należy traktować jako orientacyjne.
- Anomalie i subskrypcje wymagają ręcznej oceny.
- Local LLM zwiększa latency i jego jakość zależy od sprzętu oraz modelu.
- BasicAuth i pamięciowy rate limit są adekwatne dla jednego hosta, nie dla
  systemu wieloużytkownikowego.

## 14. Powiązane dokumenty

- [Opis projektu](project-overview.md)
- [Model card klasyfikatora](model-card.md)
- [Pakiet evidence](ml-evidence.md)
- [Runbook walidacji](validation-runbook.md)
- [ADR klasyfikacji kategorii](adr/0002-hybrid-classifier.md)
- [ADR anomalii i subskrypcji](adr/0003-anomaly-subscription-detection.md)
