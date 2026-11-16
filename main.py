import sys

# ============================================
# ПРЕДОХРАНИТЕЛЬ: проверка всех библиотек
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
    print("=" * 50)
    print("ОШИБКА: Не установлены библиотеки:")
    for pkg in missing:
        print(f"  - {pkg}")
    print("=" * 50)
    print("Установите их командой:")
    print(f"  pip install {' '.join(missing)}")
    print("=" * 50)
    sys.exit(1)

print("✅ Все библиотеки установлены. Запуск приложения...")

# ============================================
# ТВОЙ КОД НАЧИНАЕТСЯ ЗДЕСЬ
# ============================================

import flet as ft
import requests
from bs4 import BeautifulSoup

def main(page: ft.Page):
    page.title = "Tir Browser"
    page.add(ft.Text("Браузер Тир запущен!"))

ft.app(target=main)