# journal-parser

Минимальный анализ PDF-журналов по двум спискам фрагментов:

- `filters/include.txt` — что искать (фрагменты/подстроки)
- `filters/exclude.txt` — что отбрасывать (после include)

Результат — отчет в формате **`.rtf`** (удобно открывать в Word/WordPad).

## GUI (Windows, без терминала)

### Установка / обновление (Windows)

- `install.bat` — установка в `%LOCALAPPDATA%\journal-parser` + ярлык на рабочий стол
- `update.bat` — “reinstaller”: подтянуть свежую версию с GitHub (ваши `filters/` сохраняются)

1) Установить зависимости:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2) Запуск:

- Двойной клик по `start_gui.bat`

GUI использует **только** `filters/include.txt` и `filters/exclude.txt`, отчеты пишет в `reports/` в формате **`.rtf`**.

## Фильтры include/exclude

- `filters/include.txt`: фрагменты (1 на строку). Токен попадает в кандидаты, если содержит **любой** фрагмент.
- `filters/exclude.txt`: фрагменты (1 на строку). Токен исключается, если содержит **любой** фрагмент. Применяется **после** include.

Оба файла поддерживают комментарии строками `# ...`. Внутри пайплайна весь текст приводится к нижнему регистру, а `ё` заменяется на `е`.

## CLI (опционально)

```bash
python -m journal_parser analyze "D:\path\document.pdf"
```

По умолчанию пишет отчет в `reports/` (формат `.rtf`).

## Репозиторий

https://github.com/AlesBan/journal-parser.git
