# journal-parser

Терминальный анализ PDF-журналов: **все препараты/вещества из локального gazetteer**, которые встретились в тексте, с номерами страниц. Excel: **№ | Название | Страницы**.

## Словарь (gazetteer)

Собирается скриптом из открытых данных + ваших дополнений:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/build_gazetteer.py
```

Подробно: [scripts/download_sources.md](scripts/download_sources.md)

- **openFDA** — автоматически (EN, без ключа)
- **`data/custom/entries.yaml`** — RU/EN вручную
- **RxNorm** — после скачивания с UTS (`--rxnorm-rrf`)
- **PubChem** — опционально (`--pubchem-gz`)
- **ГРЛС CSV** — `--ru-csv`

## Нормализация текста

Пробелы и переносы удаляются; переносные дефисы между буквами склеиваются; **сохраняются** `()[]+.,` и цифры (валентности, формулы).

## Анализ PDF (repo-only)

```bash
python -m journal_parser analyze "D:\path\document.pdf"
```

Пишет отчет в папку `reports/` внутри репозитория.

## Фильтры include/exclude

- `filters/include.txt`: фрагменты (1 на строку). Токен попадает в кандидаты, если содержит **любой** фрагмент.
- `filters/exclude.txt`: фрагменты (1 на строку). Токен исключается, если содержит **любой** фрагмент. Применяется **после** include.

Обе таблицы поддерживают комментарии строками `# ...`. Внутри пайплайна весь текст приводится к нижнему регистру, а `ё` заменяется на `е`.

## Репозиторий

https://github.com/AlesBan/journal-parser.git
