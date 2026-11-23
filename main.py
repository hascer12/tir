import re, threading, urllib.parse, traceback
import html as html_mod
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
    _fwv = None
    WV_CLASS = None

SESSION = requests.Session()
SESSION.trust_env = False
VERSION = "v17.9"
H_WEB = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/122.0.0.0 Mobile Safari/537.36"}
H_API = {"User-Agent": "TirBrowser/17.9", "Accept": "application/json"}
AD_WORDS = ("реклама", "промо", "спонсор", "купить", "скидка", "акция", "кредит", "займ", "казино", "ставки", "an.yandex", "googleadservices", "doubleclick", "yabs.yandex", "cookie", "политика конфиденциальности", "войти", "регистрация")
STOP_Q = ("когда", "где", "кто", "что", "как", "почему", "зачем", "сколько", "какой", "какая", "какие", "родился", "возраст", "лет", "года", "такое", "значит", "это", "ли", "в", "на", "по", "о", "об")
VIDEO_HOSTS = ("rutube.ru", "youtube.com", "youtu.be", "vk.com/video", "vkvideo.ru", "ok.ru/video")
S = {"dark": True, "video_ext": True, "text": False}
PAL = {
    True: dict(bg="#0F172A", field="#1E293B", text="#F8FAFC", sub="#94A3B8", link="#60A5FA", btn="#334155", acc="#38BDF8", warn="#FBBF24", dim="#64748B"),
    False: dict(bg="#F8FAFC", field="#FFFFFF", text="#0F172A", sub="#475569", link="#2563EB", btn="#E2E8F0", acc="#0284C7", warn="#B45309", dim="#94A3B8"),
}
HISTORY = ["Европейская норка", "100 долларов", "погода в Москве", "250 * 48"]


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
            blocks = " ".join(el.get_text(" ", strip=True) for el in soup.find_all(["h1", "h2", "h3", "p", "li"]))
            t = re.sub(r"\s+", " ", blocks or soup.get_text(" ", strip=True)).strip()
            return " ".join(p for p in re.split(r"(?<=[.!?])\s+", t) if not any(w in p.lower() for w in AD_WORDS)).strip()
        except Exception:
            pass
    return re.sub(r"<[^>]+>", " ", str(raw)).strip()


def is_ad(u, t):
    return any(w in (str(u) + " " + str(t)).lower() for w in AD_WORDS)


def extract_topic(q):
    words = [w for w in re.sub(r"[^\w\s-]", " ", q.lower()).split() if w not in STOP_Q and len(w) > 1]
    return " ".join(words).strip() if words else q


def get_domain(url):
    return urllib.parse.urlparse(url).netloc or url[:30]


def try_weather(q):
    ql = q.lower().strip()
    if not any(w in ql for w in ("погод", "температур", "градус", "прогноз")):
        return ""
    words = re.sub(r"[^\w\s-]", " ", ql).split()
    stop_w = ("какая", "какой", "сегодня", "завтра", "сейчас", "погода", "погоду", "в", "во", "на", "прогноз", "температура")
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


def ddg_cards(q, out_list):
    r = http_get("https://html.duckduckgo.com/html/", params={"q": q, "kl": "ru-ru"}, headers=H_WEB, timeout=(4.0, 8.0))
    if r is None or r.status_code != 200:
        return
    for m in re.finditer(r"<a\b[^>]*result__a[^>]*>.*?</a>", r.text, re.S):
        a = m.group(0)
        h = re.search(r'href="([^"]+)"', a)
        if not h or len(out_list) >= 6:
            continue
        u = html_mod.unescape(h.group(1))
        if "uddg=" in u:
            u = urllib.parse.unquote(u.split("uddg=", 1)[1].split("&", 1)[0])
        t = html_mod.unescape(re.sub(r"<[^>]+>", "", a)).strip()
        if u.startswith("http") and t and not is_ad(u, t):
            out_list.append({"src": "DDG", "url": u, "title": t, "snip": ""})


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
    for kw in (dict(on_page_started=on_start, on_page_ended=on_end, enable_javascript=True), dict(on_page_started=on_start, on_page_ended=on_end), dict()):
        try:
            return WV_CLASS(url=url, expand=True, **kw)
        except Exception:
            continue
    return None


def P(k):
    return PAL[S["dark"]].get(k, k)


def force_js(wv):
    m = getattr(_fwv, "JavaScriptMode", None) or getattr(ft, "JavaScriptMode", None)
    try:
        if m is not None:
            wv.set_javascript_mode(m.UNRESTRICTED)
            wv.update()
            wv.reload()
    except Exception:
        pass


def T(text, c="text", size=13, **kw):
    return ft.Text(text, color=P(c), size=size, **kw)


def B(text, fn, bg="btn", c="text"):
    return ft.ElevatedButton(text, on_click=lambda e: fn(), bgcolor=P(bg), color=P(c))


def build_ui(page: ft.Page):
    page.title = "Браузер Тир " + VERSION
    page.bgcolor = P("bg")
    page.theme_mode = ft.ThemeMode.DARK if S["dark"] else ft.ThemeMode.LIGHT
    page.padding = ft.padding.only(left=10, top=36, right=10, bottom=10)
    del page.views[1:]
    cur = {"url": "", "title": "", "wv": None, "text_loaded": False}

    ent = ft.TextField(label="Запрос", bgcolor=P("field"), color=P("text"), border_color=P("dim"), focused_border_color="#3B82F6", expand=True, on_submit=lambda e: run_search())
    spinner = ft.ProgressRing(width=24, height=24, color=P("acc"), visible=False)
    status = T("Готов", "sub")
    results = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=8)
    chip = ft.Row([], wrap=True, spacing=8)
    page.add(ft.Column([
        ft.Row([T("🌐 Tir Browser " + VERSION, "text", 16, weight=ft.FontWeight.BOLD, expand=True),
                ft.IconButton(ft.Icons.SETTINGS, icon_color=P("sub"), on_click=lambda e: open_settings())]),
        ft.Row([ent, B("НАЙТИ", lambda: run_search(), "#3B82F6", "#FFFFFF")]),
        chip, ft.Row([spinner, status], spacing=8), results,
    ], expand=True))

    r_spinner = ft.ProgressRing(width=20, height=20, color=P("acc"), visible=False)
    r_body = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)
    r_wrap = ft.Container(r_body, expand=True, visible=False, padding=ft.padding.only(left=12, right=12, top=56, bottom=12))
    web_holder = ft.Container(expand=True)
    menu = ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, icon_color="#FFFFFF", items=[
        ft.PopupMenuItem(text="◀ Назад по сайту", on_click=lambda e: web_back()),
        ft.PopupMenuItem(text="⟳ Обновить", on_click=lambda e: web_reload()),
        ft.PopupMenuItem(text="🌐 В обычном браузере", on_click=lambda e: open_external()),
        ft.PopupMenuItem(text="✖ Закрыть", on_click=lambda e: close_reader()),
    ])
    reader_view = ft.View("/reader", controls=[ft.SafeArea(ft.Stack([
        web_holder, r_wrap, ft.Container(r_spinner, left=12, top=12),
        ft.Container(menu, right=6, top=6, bgcolor="#88000000", border_radius=24)], expand=True), expand=True)],
        padding=0, bgcolor=P("bg"))
    page.on_view_pop = lambda e: close_reader()

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
        web_holder.visible = (m == "web")
        r_wrap.visible = (m == "text")
        page.update()

    def load_text():
        if cur["text_loaded"]:
            return
        cur["text_loaded"] = True
        url = cur["url"]
        r_body.controls.clear()
        r_body.controls.append(T("Загружаем текст страницы...", "sub"))
        r_spinner.visible = True
        page.update()

        def worker():
            try:
                body = load_page_text(url)
            except Exception as ex:
                body = "Ошибка загрузки: " + str(ex)
            r_body.controls.clear()
            r_body.controls.append(T(body, "text", 14, selectable=True))
            r_spinner.visible = False
            page.update()

        threading.Thread(target=worker, daemon=True).start()

    def close_reader():
        web_holder.content = None
        cur["wv"] = None
        if reader_view in page.views:
            page.views.remove(reader_view)
        page.update()

    def open_link(url, title=""):
        if not url.startswith("http"):
            url = "https://" + url
        url = url.replace("//ru.wikipedia.org", "//ru.m.wikipedia.org")
        cur.update(url=url, title=title, text_loaded=False)
        if S["video_ext"] and any(h in url for h in VIDEO_HOSTS):
            open_external()
            return
        r_body.controls.clear()
        wv = None if S["text"] else make_webview(url, on_start, on_end)
        cur["wv"] = wv
        web_holder.content = wv
        if reader_view not in page.views:
            page.views.append(reader_view)
        if wv is not None:
            r_spinner.visible = True
            set_mode("web")
            threading.Timer(1.0, lambda: force_js(wv)).start()
        else:
            set_mode("text")
            load_text()

    def open_settings():
        def chg(key):
            def h(e):
                S[key] = e.control.value
                if key == "dark":
                    page.close(dlg)
                    page.clean()
                    build_ui(page)
            return h
        dlg = ft.AlertDialog(title=ft.Text("Настройки"), content=ft.Column([
            ft.Switch(label="Тёмная тема", value=S["dark"], on_change=chg("dark")),
            ft.Switch(label="Страницы как текст (вместо сайта)", value=S["text"], on_change=chg("text")),
            ft.Switch(label="Видеосайты (Rutube, YouTube) во внешнем браузере", value=S["video_ext"], on_change=chg("video_ext")),
        ], tight=True), actions=[ft.TextButton("Закрыть", on_click=lambda e: page.close(dlg))])
        page.open(dlg)

    def render_card(item):
        title, url, src = item.get("title", "")[:60], item.get("url", ""), item.get("src", "")
        snip = item.get("snip", "")[:120]
        results.controls.append(ft.Container(
            content=ft.Column([T("🔗 " + title, "link", 13, weight=ft.FontWeight.BOLD), T(get_domain(url) + "  •  " + src, "dim", 10)], spacing=2),
            padding=ft.padding.symmetric(horizontal=8, vertical=6), ink=True,
            on_click=lambda e, u=url, t=title: open_link(u, t)))
        if snip:
            results.controls.append(ft.Container(T(snip, "sub", 12), padding=ft.padding.only(left=12, right=8)))
        results.controls.append(ft.Divider(color=P("dim"), height=4))

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
                    results.controls.append(T("⚡ Ответ", "acc", 16, weight=ft.FontWeight.BOLD))
                    results.controls.append(T(m_ans, "text", 14, selectable=True))
                else:
                    ans, ev = {}, threading.Event()
                    threading.Thread(target=wiki_summary, args=(q, ans, ev), daemon=True).start()
                    ev.wait(6.0)
                    if ans.get("answer"):
                        results.controls.append(T("⚡ Быстрый ответ", "acc", 16, weight=ft.FontWeight.BOLD))
                        results.controls.append(T(clean_txt(ans["answer"])[:400], "text", 14, selectable=True))
                        if ans.get("src"):
                            results.controls.append(ft.TextButton("📖 Читать полностью", on_click=lambda e, u=ans["src"], t=ans.get("title", ""): open_link(u, t)))
                        results.controls.append(ft.Divider(color=P("dim")))
                    results.controls.append(T("🔗 ИСТОЧНИКИ", "warn", 15, weight=ft.FontWeight.BOLD))
                    page.update()
                    cw, cd = [], []
                    jobs = [lambda: wiki_search_cards(q, cw), lambda: ddg_cards(q, cd)]
                    ts = [threading.Thread(target=j, daemon=True) for j in jobs]
                    for t in ts:
                        t.start()
                    for t in ts:
                        t.join(8.0)
                    mixed, seen = [], set()
                    for grp in zip(cd + [None] * 6, cw + [None] * 6):
                        for v in grp:
                            if v and v.get("url") not in seen:
                                seen.add(v.get("url"))
                                mixed.append(v)
                    if not mixed and not ans.get("answer"):
                        results.controls.append(T("Ничего не найдено (проверьте интернет).", "sub"))
                    for item in mixed[:10]:
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
            chip.controls.append(ft.ElevatedButton(h[:20], on_click=lambda e, v=h: pick(v), bgcolor=P("btn"), color=P("acc")))
        page.update()

    update_chips()


def main(page: ft.Page):
    try:
        build_ui(page)
    except Exception:
        page.controls.clear()
        page.add(ft.Text("Ошибка запуска:\n\n" + traceback.format_exc(), color="#F87171", size=12, selectable=True))
        page.update()


ft.app(target=main)