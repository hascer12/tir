import sys

# ===== ПРЕДОХРАНИТЕЛЬ =====
REQUIRED = {'flet':'flet','requests':'requests','bs4':'beautifulsoup4','lxml':'lxml'}
missing = [p for m,p in REQUIRED.items() if not __import__('builtins').__dict__ or True]
missing = []
for m,p in REQUIRED.items():
    try: __import__(m)
    except ImportError: missing.append(p)
if missing:
    print("НЕТ БИБЛИОТЕК:", missing); sys.exit(1)

import flet as ft
import requests
from bs4 import BeautifulSoup

def fetch(page, url):
    if not url: return
    if not url.startswith("http"): url = "https://" + url
    page.controls[1].value = "⏳ Загружаю..."
    page.update()
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "lxml")
        title = soup.title.text if soup.title else url
        body = soup.get_text(" ", strip=True)[:1500]
        page.controls[1].value = f"🌐 {title}\n\n{body}"
    except Exception as e:
        page.controls[1].value = f"❌ Ошибка: {e}"
    page.update()

def main(page: ft.Page):
    page.title = "Tir Browser"
    url = ft.TextField(label="Адрес сайта", width=300)
    btn = ft.ElevatedButton("Вперёд", on_click=lambda e: fetch(page, url.value))
    out = ft.Text("Введи адрес и нажми Вперёд", selectable=True)
    page.add(url, btn, out)

ft.app(target=main)