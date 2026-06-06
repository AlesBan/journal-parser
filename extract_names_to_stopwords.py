#!/usr/bin/env python3
"""Extract likely names from report and add to stopwords."""

import re
from pathlib import Path

# Patterns for Russian names/surnames
RU_NAME_PATTERNS = [
    re.compile(r'^[А-Я][а-я]+(ов|ев|ёв|ин|ын|ан|ян|ский|цкий|ской|цкой|ых|их|ич|ыч|овна|евна|ична)$', re.IGNORECASE),
    re.compile(r'^[А-Я][а-я]+(ова|ева|ёва|ина|ына|ана|яна)$', re.IGNORECASE),
]

# Common first names in Latin
LATIN_FIRST_NAMES = {
    'aleksandr', 'alexander', 'sergey', 'sergei', 'dmitry', 'dmitriy', 'andrey', 'andrei',
    'natalya', 'marina', 'elena', 'olga', 'irina', 'svetlana', 'tatyana', 'anna',
    'mikhail', 'valentin', 'vitaliy', 'vladimir', 'igor', 'pavel', 'evgeniy', 'evgeny',
    'kristina', 'veronika', 'alina', 'anastasia', 'maria', 'olga', 'svetlana',
    'angelina', 'elena', 'maria', 'nina', 'vera', 'nadezhda', 'lyudmila', 'galina',
    'vasiliy', 'nikolay', 'yuriy', 'oleg', 'igor', 'roman', 'denis', 'maksim',
    'ilya', 'artem', 'nikita', 'daniil', 'egor', 'artyom', 'ivan', 'fedor',
    'timofey', 'kirill', 'matvey', 'mark', 'david', 'lev', 'petr', 'konstantin',
    'grigory', 'vadim', 'valery', 'gennady', 'eduard', 'rustam', 'timur', 'azat',
    'viktor', 'yakov', 'zahar', 'zachar', 'yasha', 'semen', 'spartak', 'slava',
}

def looks_like_name(candidate: str) -> bool:
    """Check if candidate looks like a name/surname."""
    c = candidate.strip()
    if not c:
        return False
    
    # Skip very short
    if len(c) < 3:
        return False
    
    # Check Latin first names
    if c.lower() in LATIN_FIRST_NAMES:
        return True
    
    # Check Russian surname patterns
    for pattern in RU_NAME_PATTERNS:
        if pattern.match(c):
            return True
    
    # All-caps Latin (likely surname)
    if c.isupper() and re.match(r'^[A-Z]{4,}$', c):
        return True
    
    # Mixed case Latin ending with typical suffixes
    if re.match(r'^[A-Z][a-z]+(ov|ev|in|sky|skaya|ova|eva|ina)$', c, re.IGNORECASE):
        return True
    
    return False

def main():
    report_path = Path("D:\\Coding\\Obsidian\\journal-parser\\20_Reports\\2026-06-04__пример-для-парсера-pdf.md")
    stopwords_path = Path("D:\\Coding\\Obsidian\\journal-parser\\30_System\\Filters\\stopwords_ru.txt")
    
    # Read candidates from report
    text = report_path.read_text(encoding='utf-8')
    
    # Extract candidates from table
    names_found = set()
    for line in text.splitlines():
        if '|' in line and 'review' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3:
                candidate = parts[1]
                if looks_like_name(candidate):
                    names_found.add(candidate.lower())
    
    print(f"Found {len(names_found)} likely names:")
    for n in sorted(names_found):
        print(f"  {n}")
    
    # Read existing stopwords
    existing = set()
    if stopwords_path.exists():
        for line in stopwords_path.read_text(encoding='utf-8').splitlines():
            existing.add(line.strip().lower())
    
    # Add new names
    new_names = names_found - existing
    if new_names:
        with stopwords_path.open('a', encoding='utf-8') as f:
            for name in sorted(new_names):
                f.write(f"{name}\n")
        print(f"\nAdded {len(new_names)} new names to stopwords.")
    else:
        print("\nNo new names to add.")

if __name__ == "__main__":
    main()
