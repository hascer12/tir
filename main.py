import sys

# ============================================
# ПРЕДОХРАНИТЕЛЬ (оставь как есть)
# ============================================
REQUIRED_PACKAGES = {
    'flet': 'flet',
    'requests': 'requests',
    'bs4': 'beautifulsoup4',
    'lxml': 'lxml',
}

missing = []
for module_name, package_name in REQUIRED_PACKAGES.items():
    try:
        __import__(module_name)
    except ImportError:
        missing.append(package_name)

if missing:
    print("ОШИБКА: Не установлены библиотеки:")
    for pkg in missing:
        print(f"  - {pkg}")
    sys.exit(1)

print("✅ Все библиотеки установлены. Запуск приложения...")

# ============================================
# СЮДА ВСТАВЬ СВОЙ НАСТОЯЩИЙ КОД
# ============================================

import flet as ft
import requests
from bs4 import BeautifulSoup

# ... твой код браузера ...