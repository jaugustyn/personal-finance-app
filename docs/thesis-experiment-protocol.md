# Protokół eksperymentów klasyfikacji do pracy magisterskiej

Wersja robocza: 29.09.2026. Ten dokument opisuje projekt eksperymentu,
a nie wyniki badania na rzeczywistych finansach. Progi gotowości w aplikacji
nie są wymaganiami uczelni ani gwarancją jakości pracy.

## 1. Pytanie badawcze i zakres

Czy dodatkowe cechy transakcji poprawiają klasyfikację kategorii wydatków
w porównaniu z obecnym zestawem bazowym? Drugie pytanie dotyczy różnicy
między Logistic Regression a kalibrowanym LinearSVC, zwłaszcza dla późniejszych
transakcji i sprzedawców niewidzianych podczas uczenia.

Analizujemy trzy aspekty: poprawność kategorii, jakość pewności predykcji
i koszt lokalnego wnioskowania. Reguły bankowe, reguły użytkownika i LLM
nie uczestniczą w tym porównaniu. Ich wpływ wymaga osobnego eksperymentu,
bo inaczej trudno przypisać zmianę wyniku cechom klasyfikatora.

## 2. Macierz porównania

| Zestaw cech | Logistic Regression | Kalibrowany LinearSVC |
| --- | --- | --- |
| `baseline` | tak | tak |
| `feature_v2` | tak | tak |

`baseline` to TF-IDF słów i znaków z tekstu sprzedawca + tytuł,
`log1p(abs(kwota w PLN))` ze skalowaniem oraz dzień tygodnia.
Nie jest to wariant wyłącznie tekstowy.

`feature_v2` zachowuje te cechy i dodaje osobny TF-IDF znormalizowanego
sprzedawcy, przedział kwoty, miesiąc, typ transakcji i źródło importu.
W obecnym zbiorze kategorii typ transakcji jest stały (`expense`), więc
nie powinien wnosić informacji rozróżniającej klasy. Źródło importu może
odzwierciedlać specyfikę jednego konta; jego przydatność należy interpretować
ostrożnie przy przenoszeniu modelu na inną osobę.

Porównanie dotyczy całego pakietu dodatkowych cech. Nie pozwala stwierdzić,
która konkretna cecha spowodowała zmianę. Do takiego wniosku potrzebne
byłyby późniejsze eksperymenty z usuwaniem pojedynczych grup cech.

Hiperparametry pochodzą z `classification/registry.py`. LinearSVC ma
ustalone `random_state=42`; kalibracja sigmoid używa dwóch podziałów.
Wszystkie cztery warianty mają te same dane i ten sam protokół oceny.
Eksperyment nie aktywuje modeli. `feature_v2` pozostaje wariantem badawczym.

## 3. Etykiety i podział danych

Do eksperymentu dopuszczamy rzeczywiste wydatki z kategorią potwierdzoną
ręcznie albo świadomie zaakceptowaną sugestią, z datą potwierdzenia.
Zaakceptowana sugestia musi mieć również referencję pochodzenia.
Predykcje, automatyczne przypisania i niepotwierdzone mapowania bankowe
nie są etykietami wzorcowymi. Dane syntetyczne służą osobno do kontroli kodu.

CLI wymaga istniejącego, poprawnego zamrożonego zbioru oceny. Oba jego
podzbiory mają rolę **walidacyjną**:

- `time`: późniejsze transakcje; trening kończy się przed całym dniem
  granicznym, również po dopisaniu nowych etykiet;
- `merchant`: zarezerwowane grupy sprzedawców; żaden rekord tych grup
  nie może wejść do treningu.

Wspólna pula treningowa spełnia oba ograniczenia jednocześnie. Podzbiory
walidacyjne mogą się pokrywać; ich liczebności nie należy sumować jako
liczby różnych transakcji. Każdy wariant dopasowuje wektoryzatory, skalowanie
i klasyfikator wyłącznie na treningu. OOF używa pięciu podziałów
`StratifiedKFold(shuffle=True, random_state=42)` i służy diagnostyce.
Nie stanowi odrębnego testu generalizacji na przyszłość lub nowych sprzedawców.

Przed OOF rekordy są sortowane po `transaction_id`, więc kolejność wyniku
zapytania SQL nie zmienia podziałów. Raport zapisuje skróty całego zbioru,
treningu i podzbiorów walidacyjnych oraz wersje bibliotek. Zamrożone
identyfikatory nie wystarczą do odtworzenia wyniku, jeśli później zmienią
się dane treningowe; trzeba zachować lokalny snapshot danych i wersję kodu.

## 4. Metryki i wybór wariantu

Raport zawiera macro-F1, weighted-F1, wyniki poszczególnych klas,
macierze pomyłek i kolejność etykiet. Osobno podaje log-loss, wieloklasowy
Brier score, ECE i przedziały kalibracji.

Próg pewności wynosi `0.55` dla wszystkich wariantów. `other` nie należy
do automatycznie pokrytych predykcji. Raportujemy coverage oraz trafność
w pokrytej części; gdy nie ma pokrytych przypadków, trafność wynosi `null`.
Progi wyznaczane z OOF są diagnostyką i nie zastępują wspólnego progu.

Główne porównanie to macro-F1 osobno dla czasu i sprzedawców. Tabela
`feature_v2_minus_baseline` pokazuje różnice dla tego samego klasyfikatora.
Przed pierwszym badaniem na rzeczywistych danych należy zatwierdzić regułę
wyboru. Propozycja: preferować prostszy baseline, chyba że `feature_v2`
poprawia gorszy z dwóch wyników macro-F1 o co najmniej 0,01 i nie pogarsza
żadnego z nich o więcej niż 0,02. To decyzja projektowa, nie test istotności.
Skrypt prezentuje wyniki, nie wybiera modelu automatycznie.

`p99_ms` mierzy 1000 wywołań dla jednego rekordu po rozgrzewce,
tym samym kodem co ocena kandydatów. Nie obejmuje API, bazy danych ani
przygotowania ramki cech, w tym dodatkowych kolumn `feature_v2`.
Transformacje wewnątrz pipeline'u są wliczane. Powtarzalność metryk jakości nie oznacza
identycznych czasów wykonania. Do porównania wydajności w pracy trzeba
zapisać sprzęt, obciążenie i wykonać powtórzenia bez równoległych zadań.

## 5. Oddzielny test końcowy

Najprostszy wariant to prospektywny test czasowy: przed jego rozpoczęciem
ustalić datę graniczną i okres zbierania nowych transakcji. Tych danych
nie używać do wyboru cech, kalibracji, progów, reguł ani treści promptów.
Samo ponowne zamrożenie wcześniej oglądanego zbioru nie zapewnia niezależności.

1. Zamknąć decyzje na danych rozwojowych: ontologię kategorii, cechy, model, próg,
   regułę obsługi `other` i metryki. Zapisać wersję kodu oraz protokół.
   Ustalić również sposób raportowania klas o małym wsparciu; nie usuwać
   ich z oceny dlatego, że wynik okazał się słaby.
2. Przygotować prywatny artefakt wybranego wariantu i ustalić ostateczny
   zakres treningu. Zapisać jego sumę kontrolną i wersje bibliotek.
3. Zbierać finalne transakcje oddzielnie od danych dostępnych rutynowemu
   treningowi. Oznaczyć je ręcznie, najlepiej bez widocznych podpowiedzi
   ocenianego modelu. Nie wykluczać trudnych przykładów po zobaczeniu błędów.
4. Uruchomić zamknięty model na ustalonym zbiorze. Podać wszystkie
   metryki, liczebności klas i macierz pomyłek, także przy słabym wyniku.
5. Dodatkowo rozdzielić wyniki znanych i nowych sprzedawców, o ile
   liczebności pozwalają na sensowną interpretację. Nie dobierać grup
   po obejrzeniu ich wyników.

Po zmianie modelu na podstawie wyniku testowego zbiór staje się kolejną
walidacją. Następna niezależna ocena wymaga nowych danych. Przy małej
liczebności należy opisać ograniczenia; progi gotowości aplikacji nie
zastępują analizy niepewności. Wnioski z danych jednej osoby dotyczą
przede wszystkim tego przypadku, a nie wszystkich użytkowników bankowości.

Obecny skrypt **nie realizuje tego testu końcowego** ani nie rezerwuje
automatycznie przyszłych rekordów. Jego raporty mają jawne oznaczenie
`development_validation` i `final_test_evaluated=false`.

## 6. Uruchomienie i materiały do rozdziału badawczego

Po przygotowaniu potwierdzonych etykiet i zamrożeniu oceny w aplikacji:

```powershell
uv run python scripts/compare_classification_features.py --from-db
```

Połączenie korzysta z lokalnej konfiguracji aplikacji. `DATABASE_URL` musi
wskazywać bazę osiągalną ze środowiska, w którym działa polecenie; domyślny
stos Docker nie publikuje portu PostgreSQL na hoście. Skrypt sprawdza
ważność zamrożonego zbioru i nie zapisuje zmian do bazy. Raport JSON trafia
do `data/reports/feature_comparison_<czas>.json`. Opcja `--output` pozwala
wskazać inny lokalny plik. Raporty z różnych skrótów danych lub podziałów
nie są bezpośrednio porównywalnymi powtórzeniami.

Do pracy przygotować tabelę czterech wariantów dla obu walidacji,
macierze pomyłek, wykresy kalibracji, analizę pomyłek na zanonimizowanych
przykładach i opis testu końcowego. Brak poprawy po dodaniu cech także jest
wynikiem eksperymentu. Raporty i modele z prywatnych danych pozostają poza
repozytorium; przed publikacją trzeba przejrzeć nawet agregaty.
