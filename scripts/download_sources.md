# Источники для gazetteer

## Автоматически (скрипт `build_gazetteer.py`)

| Источник | Лицензия | Что даёт |
|----------|----------|----------|
| [openFDA NDC](https://open.fda.gov/apis/drug/ndc/) | Open | EN: generic, brand, active ingredients (~135k продуктов) |
| `data/custom/entries.yaml` | Ваш | RU + EN вручную |

```bash
python scripts/build_gazetteer.py
```

Быстрый тест:

```bash
python scripts/build_gazetteer.py --openfda-max 5000
```

---

## RxNorm (рекомендуется для полноты EN/латиницы)

1. Бесплатный аккаунт: [UTS / UMLS](https://uts.nlm.nih.gov/uts/login)
2. Скачать **Current Prescribable Content** (без полной лицензии UMLS):  
   [RxNorm Prescribable](https://www.nlm.nih.gov/research/umls/rxnorm/docs/prescribe.html)  
   или `RxNorm_full_prescribe_*.zip` с [страницы файлов](https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html)
3. Распаковать, положить `RXNCONSO.RRF` в `data/sources/rxnorm/`

```bash
python scripts/build_gazetteer.py --rxnorm-rrf data/sources/rxnorm/RXNCONSO.RRF
```

> Прямая ссылка `*_current.zip` с NLM редиректит на UTS login — нужна авторизация в браузере.

---

## PubChem (химия, синонимы; ~1 GB)

```bash
curl -L -o data/sources/pubchem/CID-Synonym-filtered.gz ^
  https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/CID-Synonym-filtered.gz
```

```bash
python scripts/build_gazetteer.py --pubchem-gz data/sources/pubchem/CID-Synonym-filtered.gz --pubchem-max-rows 500000
```

Полный файл — миллионы синонимов; для журналов часто достаточно RxNorm + custom.

---

## Русские названия (ГРЛС)

Официальный [opendata Минздрава](https://minzdrav.gov.ru/opendata/7707778246-grls) — устаревший паспорт; полный реестр на [grls.rosminzdrav.ru](https://grls.rosminzdrav.ru/).

Экспортируйте CSV (торговое + МНН) любым легальным способом и:

```bash
python scripts/build_gazetteer.py --ru-csv path/to/grls_export.csv
```

Колонки: `display` или `Торговое наименование`, плюс `mnn` / `МНН` / `search_key`.

---

## Итоговый файл

`data/built/gazetteer.json` — не коммитится, пересобирается скриптом.
