# journal-parser

Минимальный анализ PDF-журналов по двум спискам фрагментов:

- `filters/include.txt` — что искать (фрагменты/подстроки)
- `filters/exclude.txt` — что отбрасывать (после include)

Результат — отчет в формате **`.rtf`** (удобно открывать в Word/WordPad).

## GUI (Windows, без терминала)

### Установка / обновление (Windows)

- `installer\output\journal-parser-setup.exe` — полноценный установщик (Inno Setup).
- Если Inno Setup не установлен, `installer\build_installer.ps1` соберет `installer\output\Installer.exe` и `installer\output\Reinstaller.exe` через встроенный Windows IExpress.

Самый простой вариант: скачивать готовые файлы из **Releases** на GitHub (там лежат:
`journal-parser-Installer.exe` и `journal-parser-Reinstaller.exe`).

После установки появятся ярлыки:

- **journal-parser** — запуск GUI (без терминала)
- **Обновить journal-parser** — “reinstaller”: подтянуть свежую версию с GitHub (ваши `filters/` сохраняются)

Сборка установщика (для разработчика):

```powershell
installer\build_installer.ps1
```

Важно: “приложение” здесь не собирается в один `journal-parser.exe` рядом с исходниками.
Скрипт сборки делает **установщики** и кладет их в `installer\output\`.
GUI запускается либо через ярлык после установки, либо из установленной папки.

Режимы установки:

- **Для всех пользователей (рекомендуется)**: установка в `Program Files` (потребует права администратора).
- **Для одного пользователя**: установка в `%LOCALAPPDATA%\journal-parser\` (без админ-прав).

1) Установить зависимости:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2) Запуск:

- ярлык **journal-parser** (или файл `{localappdata}\journal-parser\journal-parser-bootstrap.bat`)

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
