import re, threading, urllib.parse, traceback
import requests, urllib3
import flet as ft

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

try:
    import flet_webview as _fwv
    WV_CLASS = _fwv.WebView
except Exception:
    WV_CLASS = None

SESSION = requests.Session()
SESSION.trust_env = False
VERSION = "v17.5"
H_WEB = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/122.0.0.0 Mobile Safari/537.36"}
H_API = {"User-Agent": "TirBrowser/17.5", "Accept": "application/json"}
AD_WORDS = ("реклама", "промо", "спонсор", "купить", "цена", "скидка", "акция", "заказать", "доставка", "кредит", "займ", "казино", "ставки", "услуги", "прайс", "an.yandex", "googleadservices", "doubleclick", "yabs.yandex", "cookie", "политика конфиденциальности", "войти", "регистрация")
STOP_Q = ("когда", "кагда", "где", "кто", "что", "што", "как", "почему", "зачем", "сколько", "какой", "какая", "какие", "родился", "радился", "возраст", "лет", "года", "живет", "живут", "умер", "такое", "значит", "это", "ли", "в", "на", "по", "о", "об")
HISTORY = ["Европейская норка", "100 долларов", "переведи breakthrough", "250 * 48"]


def http_get(url, params=None, headers=None, timeout=(3.0, 6.0)):
    try:
        return SESSION.get(url, params=params, headers=headers, timeout=timeout, verify=False)
    except Exception:
        return None


def clean_txt(raw):
    if not raw:
        return ""
    if BeautifulSoup:
        try:
            soup = BeautifulSoup(str(raw), "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
                tag.decompose()
            t = re.sub(r"\s+", " ", " ".join(el.get_text(" ", strip=True) for el in soup.find_all(["h1", "h2", "h3", "p", "li"]))).strip()
            return " ".join(p for p in re.split(r"(?<=[.!?])\s+", t) if not any(w in p.lower() for w in AD_WORDS)).strip()
        except Exception:
            pass
    return re.sub(r"<[^>]+>", " ", str(raw)).strip()


def is_ad(u, t):
    return any(w in (str(u) + " " + str(t)).lower() for w in AD_WORDS)


def extract_topic(q):
    words = [w for w in re.sub(r"[^\w\s-]", " ", q.lower()).split() if w not in STOP_Q and len(w) > 1]
    return " ".join(words).strip() if words else q


def chunk_text(text, size=700):
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]


def get_domain(url):
    return urllib.parse.urlparse(url).netloc or url[:30]


def try_weather(q):
    ql = q.lower().strip()
    if not any(w in ql for w in ("погод", "температур", "градус", "прогноз")):
        return ""
    words = re.sub(r"[^\w\s-]", " ", ql).split()
    stop_w = ("какая", "какой", "сегодня", "сеодня", "сигодня", "завтра", "сейчас", "погода", "погоду", "в", "во", "на", "улице", "прогноз", "температура", "градусов")
    city = " ".join(w for w in words if w not in stop_w and len(w) > 2).strip()
    for cand in ([city, "Москва"] if city else ["Москва"]):
        g = http_get("https://geocoding-api.open-meteo.com/v1/search", params={"name": cand, "count": 1, "language": "ru"})
        res_g = g.json().get("results", []) if g is not None and g.status_code == 200 else []
        if res_g:
            loc = res_g[0]
            w = http_get("https://api.open-meteo.com/v1/forecast", params={"latitude": loc.get("latitude"), "longitude": loc.get("longitude"), "current_weather": "true"})
            cw = w.json().get("current_weather", {}) if w is not None and w.status_code == 200 else {}
            if "temperature" in cw:
                temp, wind, code = cw.get("temperature"), cw.get("windspeed"), cw.get("weathercode", 0)
                sky = "Ясно" if code == 0 else ("Облачно" if code < 4 else ("Туман" if code < 50 else ("Осадки" if code < 70 else "Снег")))
                return f"Погода ({loc.get('name', cand)}): {'+' if float(temp) > 0 else ''}{temp}°C, {sky}, ветер {wind} км/ч"
    return ""


def try_smart_tools(q):
    ql = q.lower().strip()
    has_cur = bool(re.search(r"(дол|жол|usd|usa|сша|евр|eur|юан|cny)", ql))
    if has_cur and (any(w in ql for w in ("курс", "волют", "валют", "рубл", "скольк", "цен", "стои", "в ")) or re.search(r"\d", ql)):
        m = re.search(r"(\d+(?:[.,]\d+)?)", ql)
        amt = float(m.group(1).replace(",", ".")) if m else 1.0
        cur = "EUR" if re.search(r"(евр|eur)", ql) else ("CNY" if re.search(r"(юан|cny)", ql) else "USD")
        val = 0.0
        try:
            r = SESSION.get("https://open.er-api.com/v6/latest/" + cur, timeout=(3.0, 6.0), verify=False)
            if r.status_code == 200:
                val = float(r.json().get("rates", {}).get("RUB", 0))
        except Exception:
            pass
        if val > 0:
            return f"{amt} {cur} = {round(amt * val, 2)} RUB (курс: {round(val, 2)} руб.)"
    if ql.startswith(("переведи ", "перевод ", "как будет ", "что значит ")) or re.fullmatch(r"[a-zA-Z\s'.,!?-]{2,60}", q.strip()):
        txt = re.sub(r"^(переведи|перевод|как будет по[- ]английски|как будет|что значит слово|что значит)\s+", "", q.strip(), flags=re.I).strip()
        if txt:
            sl, tl = ("ru", "en") if re.search(r"[а-яА-ЯёЁ]", txt) else ("en", "ru")
            r = http_get("https://translate.googleapis.com/translate_a/single", params={"client": "gtx", "sl": sl, "tl": tl, "dt": "t", "q": txt}, headers=H_WEB)
            if r is not None and r.status_code == 200 and r.text.strip().startswith("["):
                try:
                    tr = "".join(i[0] for i in r.json()[0] if i and i[0])
                    if tr and tr.lower() != txt.lower():
                        return f"ИИ-перевод ({sl} -> {tl}): {tr}"
                except Exception:
                    pass
    return ""


def try_math(q):
    expr = q.lower().replace("сколько будет", "").replace("посчитай", "").replace("=", "").replace(",", ".").replace("х", "*").replace("x", "*").replace(":", "/").strip()
    if expr and re.fullmatch(r"[0-9+\-*/().\s]+", expr) and any(op in expr for op in "+-*/"):
        try:
            res = eval(expr, {"__builtins__": None}, {})
            return "Ответ: " + str(int(res) if isinstance(res, float) and res.is_integer() else res)
        except Exception:
            pass
    return ""


def wiki_summary(q, out, ev):
    try:
        r = http_get("https://ru.wikipedia.org/w/api.php", params={"action": "opensearch", "search": extract_topic(q), "limit": 1, "namespace": 0, "format": "json", "utf8": 1}, headers=H_API)
        if r is None or r.status_code != 200:
            return
        data = r.json()
        title = data[1][0] if len(data) > 1 and data[1] else None
        if not title:
            return
        s = http_get("https://ru.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title), headers=H_API)
        if s is None or s.status_code != 200:
            return
        j = s.json()
        ext = str(j.get("extract", "")).strip()
        if ext and len(ext) > 30 and "уменьшительная форма" not in ext.lower():
            out["answer"], out["title"] = ext, title
            out["src"] = j.get("content_urls", {}).get("desktop", {}).get("page", "")
            ev.set()
    except Exception:
        pass


def wiki_search_cards(q, out_list):
    try:
        r = http_get("https://ru.wikipedia.org/w/api.php", params={"action": "query", "list": "search", "srsearch": extract_topic(q), "srlimit": 6, "format": "json", "utf8": 1}, headers=H_API)
        items = r.json().get("query", {}).get("search", []) if r is not None and r.status_code == 200 else []
        for w in items:
            wt, ws = w.get("title", ""), clean_txt(w.get("snippet", ""))
            wu = "https://ru.wikipedia.org/wiki/" + urllib.parse.quote(wt)
            if wt and not is_ad(wu, wt):
                out_list.append({"src": "Вики", "url": wu, "title": wt, "snip": ws})
    except Exception:
        pass


def rambler_cards(q, out_list):
    seen = set()
    try:
        r = http_get("https://nova.rambler.ru/search", params={"query": q}, headers=H_WEB)
        if BeautifulSoup is not None and r is not None and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                if len(out_list) >= 6:
                    break
                u = a.get("href", "")
                if not u.startswith("http") or "rambler.ru" in u or "yandex." in u or u in seen:
                    continue
                t = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
                if len(t) > 12 and not is_ad(u, t):
                    seen.add(u)
                    out_list.append({"src": "Рунет", "url": u, "title": t, "snip": ""})
    except Exception:
        pass


def load_page_text(url):
    r = http_get(url, headers=H_WEB, timeout=(4.0, 10.0))
    if r is None:
        return "Не удалось загрузить страницу (нет связи или сайт не отвечает)."
    try:
        r.encoding = r.apparent_encoding
    except Exception:
        pass
    plain = clean_txt(r.text)
    return plain[:8000] if len(plain) > 60 else "Текст скрыт сайтом от прямого чтения."


def make_webview(url, on_start, on_end):
    if WV_CLASS is None:
        return None
    for kw in (dict(on_page_started=on_start, on_page_ended=on_end), dict()):
        try:
            return WV_CLASS(url=url, expand=True, **kw)
        except Exception:
            continue
    return None


def T(text, color="#E2E8F0", size=13, **kw):
    return ft.Text(text, color=color, size=size, **kw)


def B(text, fn, bg="#334155", color="#F8FAFC"):
    return ft.ElevatedButton(text, on_click=lambda e: fn(), bgcolor=bg, color=color)


def build_ui(page: ft.Page):
    page.title = "Браузер Тир " + VERSION
    page.bgcolor = "#0F172A"
    page.padding = ft.padding.only(left=10, top=36, right=10, bottom=10)
    cur = {"url": "", "title": "", "wv": None, "text_loaded": False, "mode": "web"}

    ent = ft.TextField(label="Запрос", bgcolor="#1E293B", color="#F8FAFC", border_color="#334155", focused_border_color="#3B82F6", expand=True, on_submit=lambda e: run_search())
    spinner = ft.ProgressRing(width=24, height=24, color="#38BDF8", visible=False)
    status = T("Готов", "#94A3B8")
    results = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=8)
    chip = ft.Row([], wrap=True, spacing=8)
    search_view = ft.Column([
        T("🌐 Tir Browser " + VERSION, "#F8FAFC", 16, weight=ft.FontWeight.BOLD),
        ft.Row([ent, B("НАЙТИ", lambda: run_search(), "#3B82F6", "#FFFFFF")]),
        chip, ft.Row([spinner, status], spacing=8), results,
    ], expand=True)

    r_spinner = ft.ProgressRing(width=20, height=20, color="#38BDF8", visible=False)
    r_title = T("", "#F8FAFC", 14, weight=ft.FontWeight.BOLD, selectable=True, max_lines=2)
    r_url = T("", "#4ADE80", 10, selectable=True, max_lines=1)
    r_body = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=10, visible=False)
    web_holder = ft.Container(expand=True, visible=True)
    btn_mode = B("📄 Текст", lambda: toggle_mode(), color="#FBBF24")
    reader_view = ft.Column([
        ft.Row([B("← Поиск", lambda: close_reader(), color="#F87171"), B("◀", lambda: web_back()), B("⟳", lambda: web_reload()),
                B("🌐", lambda: open_external(), color="#38BDF8"), btn_mode, r_spinner], wrap=True, spacing=6),
        r_title, r_url, ft.Divider(color="#1E293B", height=4), web_holder, r_body,
    ], expand=True, visible=False)
    page.add(search_view, reader_view)

    def on_start(e):
        r_spinner.visible = True
        page.update()

    def on_end(e):
        r_spinner.visible = False
        page.update()

    def open_external():
        try:
            if cur["url"]:
                page.launch_url(cur["url"])
        except Exception:
            pass

    def web_back():
        try:
            if cur["wv"] is not None:
                cur["wv"].go_back()
        except Exception:
            pass

    def web_reload():
        if cur["url"]:
            open_link(cur["url"], cur["title"])

    def set_mode(m):
        cur["mode"] = m
        web_holder.visible = (m == "web")
        r_body.visible = (m == "text")
        btn_mode.text = "📄 Текст" if m == "web" else "🌍 Сайт"
        btn_mode.visible = cur["wv"] is not None
        page.update()

    def load_text():
        if cur["text_loaded"]:
            return
        cur["text_loaded"] = True
        url = cur["url"]
        r_body.controls.clear()
        r_body.controls.append(T("Загружаем текст страницы...", "#94A3B8"))
        r_spinner.visible = True
        page.update()

        def worker():
            try:
                body = load_page_text(url)
            except Exception as ex:
                body = "Ошибка загрузки: " + str(ex)
            r_body.controls.clear()
            for part in chunk_text(body):
                r_body.controls.append(T(part, size=14, selectable=True))
            r_spinner.visible = False
            page.update()

        threading.Thread(target=worker, daemon=True).start()

    def toggle_mode():
        if cur["mode"] == "web":
            set_mode("text")
            load_text()
        else:
            set_mode("web")

    def close_reader():
        web_holder.content = None
        cur["wv"] = None
        reader_view.visible = False
        search_view.visible = True
        page.update()

    def open_link(url, title=""):
        if not url.startswith("http"):
            url = "https://" + url
        cur.update(url=url, title=title, text_loaded=False)
        r_title.value = title or get_domain(url)
        r_url.value = url
        r_body.controls.clear()
        search_view.visible = False
        reader_view.visible = True
        wv = make_webview(url, on_start, on_end)
        cur["wv"] = wv
        if wv is not None:
            web_holder.content = wv
            r_spinner.visible = True
            set_mode("web")
        else:
            web_holder.content = None
            set_mode("text")
            load_text()

    def render_card(item):
        title, url, src = item.get("title", "")[:60], item.get("url", ""), item.get("src", "")
        snip = item.get("snip", "")[:120]
        results.controls.append(ft.Container(
            content=ft.Column([T("🔗 " + title, "#60A5FA", 13, weight=ft.FontWeight.BOLD), T(get_domain(url) + "  •  " + src, "#64748B", 10)], spacing=2),
            padding=ft.padding.symmetric(horizontal=8, vertical=6), ink=True,
            on_click=lambda e, u=url, t=title: open_link(u, t)))
        if snip:
            results.controls.append(ft.Container(T(snip, "#CBD5E1", 12), padding=ft.padding.only(left=12, right=8)))
        results.controls.append(ft.Divider(color="#1E293B", height=4))

    def run_search():
        q = (ent.value or "").strip()
        if not q:
            return
        if q not in HISTORY:
            HISTORY.insert(0, q)
            update_chips()
        if q.startswith(("http://", "https://")) or ("." in q and " " not in q):
            open_link(q)
            return
        spinner.visible = True
        status.value = "Ищем..."
        results.controls.clear()
        page.update()

        def worker():
            try:
                m_ans = try_math(q) or try_smart_tools(q) or try_weather(q)
                if m_ans:
                    results.controls.append(T("⚡ Ответ", "#38BDF8", 16, weight=ft.FontWeight.BOLD))
                    results.controls.append(T(m_ans, "#F8FAFC", 14, selectable=True))
                else:
                    ans, ev = {}, threading.Event()
                    threading.Thread(target=wiki_summary, args=(q, ans, ev), daemon=True).start()
                    ev.wait(6.0)
                    if ans.get("answer"):
                        results.controls.append(T("⚡ Быстрый ответ", "#38BDF8", 16, weight=ft.FontWeight.BOLD))
                        results.controls.append(T(clean_txt(ans["answer"])[:400], "#F8FAFC", 14, selectable=True))
                        if ans.get("src"):
                            results.controls.append(ft.TextButton("📖 Читать полностью", on_click=lambda e, u=ans["src"], t=ans.get("title", ""): open_link(u, t)))
                        results.controls.append(ft.Divider(color="#334155"))
                    results.controls.append(T("🔗 ИСТОЧНИКИ", "#FBBF24", 15, weight=ft.FontWeight.BOLD))
                    page.update()
                    cw, cr = [], []
                    ts = [threading.Thread(target=f, args=(q, c), daemon=True) for f, c in ((wiki_search_cards, cw), (rambler_cards, cr))]
                    for t in ts:
                        t.start()
                    for t in ts:
                        t.join(8.0)
                    mixed, seen = [], set()
                    for grp in zip(cw + [None] * 6, cr + [None] * 6):
                        for v in grp:
                            if v and v.get("url") not in seen:
                                seen.add(v.get("url"))
                                mixed.append(v)
                    if not mixed and not ans.get("answer"):
                        results.controls.append(T("Ничего не найдено (проверьте интернет).", "#94A3B8"))
                    for item in mixed[:8]:
                        render_card(item)
                spinner.visible = False
                status.value = "Готово"
                page.update()
            except Exception:
                spinner.visible = False
                status.value = "Ошибка поиска"
                results.controls.append(T(traceback.format_exc(), "#F87171", 11, selectable=True))
                page.update()

        threading.Thread(target=worker, daemon=True).start()

    def pick(v):
        ent.value = v
        run_search()

    def update_chips():
        chip.controls.clear()
        for h in HISTORY[:4]:
            chip.controls.append(ft.ElevatedButton(h[:20], on_click=lambda e, v=h: pick(v), bgcolor="#334155", color="#38BDF8"))
        page.update()

    update_chips()


def main(page: ft.Page):
    try:
        build_ui(page)
    except Exception:
        page.controls.clear()
        page.add(T("Ошибка запуска:\n\n" + traceback.format_exc(), "#F87171", 12, selectable=True))
        page.update()


ft.app(target=main)