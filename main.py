import re, json, base64, threading, urllib.parse, traceback
import html as html_mod
import requests, urllib3
import flet as ft

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

REP = []


def rep(m):
    REP.append(str(m)[:150])
    del REP[:-40]


try:
    import flet_webview as _fwv
    WV_CLASS = _fwv.WebView
except Exception as e:
    _fwv = None
    WV_CLASS = None
    rep("flet_webview не импортируется: " + str(e))

SESSION = requests.Session()
SESSION.trust_env = False
VERSION = "v18.1"
H_WEB = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/122.0.0.0 Mobile Safari/537.36"}
STOP_Q = ("когда", "где", "кто", "что", "как", "почему", "сколько", "какой", "какая", "какие", "родился", "возраст", "лет", "такое", "это", "ли", "в", "на", "по", "о")
AD_WORDS = ("реклама", "спонсор", "купить", "скидка", "казино", "ставки", "an.yandex", "doubleclick", "cookie", "войти", "регистрация")
VIDEO_HOSTS = ("rutube.ru", "youtube.com", "youtu.be", "vk.com/video", "vkvideo.ru", "ok.ru/video")
S = {"dark": True, "video_ext": False, "text": False}
PAL = {
    True: dict(bg="#0F172A", field="#1E293B", text="#F8FAFC", sub="#94A3B8", link="#60A5FA", btn="#334155", acc="#38BDF8", dim="#64748B"),
    False: dict(bg="#F8FAFC", field="#FFFFFF", text="#0F172A", sub="#475569", link="#2563EB", btn="#E2E8F0", acc="#0284C7", dim="#94A3B8"),
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
            for tag in soup(["script", "style", "nav", "footer", "aside"]):
                tag.decompose()
            blocks = " ".join(el.get_text(" ", strip=True) for el in soup.find_all(["h1", "h2", "h3", "p", "li"]))
            t = re.sub(r"\s+", " ", blocks or soup.get_text(" ", strip=True)).strip()
            return " ".join(p for p in re.split(r"(?<=[.!?])\s+", t) if not any(w in p.lower() for w in AD_WORDS)).strip()
        except Exception:
            pass
    return re.sub(r"<[^>]+>", " ", str(raw)).strip()


def try_weather(q):
    ql = q.lower()
    if not any(w in ql for w in ("погод", "температур", "градус", "прогноз")):
        return ""
    stop = ("какая", "какой", "сегодня", "завтра", "сейчас", "погода", "погоду", "в", "во", "на", "прогноз", "температура")
    city = " ".join(w for w in re.sub(r"[^\w\s-]", " ", ql).split() if w not in stop and len(w) > 2) or "Москва"
    g = http_get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1, "language": "ru"})
    res = g.json().get("results") if g is not None and g.status_code == 200 else None
    if not res:
        return ""
    loc = res[0]
    w = http_get("https://api.open-meteo.com/v1/forecast", params={"latitude": loc.get("latitude"), "longitude": loc.get("longitude"), "current_weather": "true"})
    cw = w.json().get("current_weather") if w is not None and w.status_code == 200 else None
    if not cw:
        return ""
    t, code = cw.get("temperature"), cw.get("weathercode", 0)
    sky = "Ясно" if code == 0 else ("Облачно" if code < 4 else ("Туман" if code < 50 else ("Осадки" if code < 70 else "Снег")))
    return f"Погода ({loc.get('name', city)}): {t}°C, {sky}, ветер {cw.get('windspeed')} км/ч"


def try_smart_tools(q):
    ql = q.lower()
    cur = "EUR" if re.search(r"евр|eur", ql) else "CNY" if re.search(r"юан|cny", ql) else "USD" if re.search(r"дол|usd|сша", ql) else ""
    if not cur or not re.search(r"\d|курс", ql):
        return ""
    m = re.search(r"\d+(?:[.,]\d+)?", ql)
    amt = float(m.group().replace(",", ".")) if m else 1.0
    r = http_get("https://open.er-api.com/v6/latest/" + cur)
    val = float(r.json().get("rates", {}).get("RUB", 0)) if r is not None and r.status_code == 200 else 0
    return f"{amt} {cur} = {round(amt * val, 2)} RUB (курс {round(val, 2)})" if val else ""


def try_math(q):
    expr = q.lower().replace("=", "").replace(",", ".").replace("х", "*").replace("x", "*").replace(":", "/").strip()
    if expr and re.fullmatch(r"[0-9+\-*/().\s]+", expr) and any(op in expr for op in "+-*/"):
        try:
            res = eval(expr, {"__builtins__": None}, {})
            return "Ответ: " + str(int(res) if isinstance(res, float) and res.is_integer() else res)
        except Exception:
            pass
    return ""


def is_ad(u, t):
    return any(w in (str(u) + " " + str(t)).lower() for w in AD_WORDS)


def extract_topic(q):
    words = [w for w in re.sub(r"[^\w\s-]", " ", q.lower()).split() if w not in STOP_Q and len(w) > 1]
    return " ".join(words).strip() if words else q


def get_domain(url):
    return urllib.parse.urlparse(url).netloc or url[:30]


def wiki_summary(q, out):
    try:
        r = http_get("https://ru.wikipedia.org/w/api.php", params={"action": "opensearch", "search": extract_topic(q), "limit": 1, "namespace": 0, "format": "json", "utf8": 1})
        data = r.json() if r is not None and r.status_code == 200 else []
        title = data[1][0] if len(data) > 1 and data[1] else None
        if not title:
            return
        r2 = http_get("https://ru.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title))
        j = r2.json() if r2 is not None and r2.status_code == 200 else {}
        ext = str(j.get("extract", "")).strip()
        if len(ext) > 30:
            out["answer"], out["title"] = ext, title
    except Exception as e:
        rep("Вики-ответ: " + str(e)[:50])


def wiki_search_cards(q, out_list):
    try:
        r = http_get("https://ru.wikipedia.org/w/api.php", params={"action": "query", "list": "search", "srsearch": extract_topic(q), "srlimit": 6, "format": "json", "utf8": 1})
        items = r.json().get("query", {}).get("search", []) if r is not None and r.status_code == 200 else []
        for w in items:
            wt, ws = w.get("title", ""), clean_txt(w.get("snippet", ""))
            out_list.append({"src": "Вики", "url": "https://ru.wikipedia.org/wiki/" + urllib.parse.quote(wt), "title": wt, "snip": ws})
        rep("Вики: %d" % len(out_list))
    except Exception as e:
        rep("Вики: " + str(e)[:50])


def web_one(name, url, params, pat, out):
    r = http_get(url, params=params, headers=H_WEB, timeout=(4.0, 8.0))
    if r is None or r.status_code != 200:
        rep(name + ": " + ("нет ответа" if r is None else str(r.status_code)))
        return
    for m in re.finditer(pat, r.text, re.S):
        a = m.group(1)
        h = re.search(r'href="([^"]+)"', a)
        if not h or len(out) >= 6:
            continue
        u = html_mod.unescape(h.group(1))
        if "bing.com/ck/a" in u:
            b = urllib.parse.parse_qs(urllib.parse.urlparse(u).query).get("u", [""])[0][2:]
            try:
                u = base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode()
            except Exception:
                continue
        t = html_mod.unescape(re.sub(r"<[^>]+>", "", a)).strip()
        if u.startswith("http") and t and not is_ad(u, t):
            out.append({"src": name, "url": u, "title": t, "snip": ""})
    rep("%s: %d, %d байт" % (name, len(out), len(r.text)))


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
        rep("WebView: пакета нет")
        return None
    ev = dict(on_page_started=on_start, on_page_ended=on_end)
    con = dict(ev, enable_javascript=True, on_console_message=lambda e: rep("JS РАБОТАЕТ: " + str(getattr(e, "message", e.data))[:50]))
    for i, kw in enumerate((con, dict(ev, enable_javascript=True), ev, {})):
        try:
            w = WV_CLASS(url=url, expand=True, **kw)
            try:
                w.javascript_enabled = True
            except Exception:
                pass
            rep("WebView %d: OK" % i)
            return w
        except Exception as e:
            rep("WebView %d: %s" % (i, str(e)[:70]))
    return None


def P(k):
    return PAL[S["dark"]].get(k, k)


def load_state(page):
    try:
        d = json.loads(page.client_storage.get("tir3") or "{}")
        S.update(d.get("S", {}))
        HISTORY[:] = d.get("H", HISTORY)
    except Exception:
        pass


def save_state(page):
    try:
        page.client_storage.set("tir3", json.dumps({"S": S, "H": HISTORY[:12]}))
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
        cur.update(url=url, title=title, text_loaded=False)
        if S["video_ext"] and any(h in url for h in VIDEO_HOSTS):
            open_external()
            return
        wv = None if S["text"] else make_webview(url, on_start, on_end)
        r_body.controls.clear()
        cur["wv"] = wv
        web_holder.content = wv
        if reader_view not in page.views:
            page.views.append(reader_view)
        if wv is not None:
            r_spinner.visible = True
            set_mode("web")
        else:
            set_mode("text")
            load_text()

    def open_report():
        d2 = ft.AlertDialog(title=ft.Text("Отчёт"), content=ft.Column([ft.Text("\n".join(REP) or "пусто: открой сайт или сделай поиск", selectable=True, size=12)], scroll=ft.ScrollMode.AUTO, width=320, height=380), actions=[ft.TextButton("Закрыть", on_click=lambda e: page.close(d2))])
        page.open(d2)

    def open_settings():
        def chg(key):
            def h(e):
                S[key] = e.control.value
                save_state(page)
                if key == "dark":
                    page.close(dlg)
                    page.clean()
                    build_ui(page)
            return h

        def row(label, key):
            return ft.Row([ft.Switch(value=S[key], on_change=chg(key)), ft.Text(label, expand=True, size=14)])
        dlg = ft.AlertDialog(title=ft.Text("Настройки"), content=ft.Column([
            row("Тёмная тема", "dark"),
            row("Страницы как текст (вместо сайта)", "text"),
            row("Видеосайты (Rutube, YouTube) во внешнем браузере", "video_ext"),
            ft.TextButton("📋 Отчёт: JavaScript и поиск", on_click=lambda e: (page.close(dlg), open_report())),
        ], tight=True, width=300), actions=[ft.TextButton("Закрыть", on_click=lambda e: page.close(dlg))])
        page.open(dlg)

    def render_card(item):
        title, url, src = item["title"][:60], item["url"], item["src"]
        results.controls.append(ft.Container(
            content=ft.Column([T("🔗 " + title, "link", 13, weight=ft.FontWeight.BOLD), T(get_domain(url) + "  •  " + src, "dim", 10)], spacing=2),
            padding=ft.padding.symmetric(horizontal=8, vertical=6), ink=True,
            on_click=lambda e, u=url, t=title: open_link(u, t)))
        if item["snip"]:
            results.controls.append(ft.Container(T(item["snip"][:120], "sub", 12), padding=ft.padding.only(left=12, right=8)))
        results.controls.append(ft.Divider(color=P("dim"), height=4))

    def run_search():
        q = (ent.value or "").strip()
        if not q:
            return
        if q not in HISTORY:
            HISTORY.insert(0, q)
            save_state(page)
            update_chips()
        if q.startswith(("http://", "https://")) or ("." in q and " " not in q):
            open_link(q)
            return
        results.controls.clear()
        spinner.visible = True
        status.value = "Ищем..."
        page.update()
        try:
            m_ans = try_math(q) or try_smart_tools(q) or try_weather(q)
            if m_ans:
                results.controls.append(T("⚡ Ответ", "acc", 16, weight=ft.FontWeight.BOLD))
                results.controls.append(T(m_ans, "text", 14, selectable=True))
            else:
                ans, cw = {}, []
                srcs = (("Mojeek", "https://www.mojeek.com/search", {"q": q}, r'(<a\b[^>]*class="[^"]*\btitle\b[^>]*>.*?</a>)'),
                        ("Bing", "https://www.bing.com/search", {"q": q, "setlang": "ru"}, r'<li class="b_algo".*?(<a\b[^>]*href="[^"]+"[^>]*>.*?</a>)'))
                outs = [[], []]
                jobs = [lambda: wiki_summary(q, ans), lambda: wiki_search_cards(q, cw)] + [lambda s=s, o=o: web_one(*s, o) for s, o in zip(srcs, outs)]
                ts = [threading.Thread(target=j, daemon=True) for j in jobs]
                for t in ts:
                    t.start()
                for t in ts:
                    t.join(9.0)
                if ans.get("answer"):
                    results.controls.append(T("⚡ Быстрый ответ", "acc", 16, weight=ft.FontWeight.BOLD))
                    results.controls.append(T(ans["answer"][:400], "text", 14, selectable=True))
                results.controls.append(T("🔗 ИСТОЧНИКИ", "acc", 15, weight=ft.FontWeight.BOLD))
                mixed, seen = [], set()
                for v in [x for grp in zip(*[o + [None] * 6 for o in outs]) for x in grp] + cw[:4]:
                    if v and v["url"] not in seen:
                        seen.add(v["url"])
                        mixed.append(v)
                if not mixed:
                    results.controls.append(T("Ничего не найдено.", "sub"))
                for item in mixed[:10]:
                    render_card(item)
        except Exception:
            results.controls.append(T(traceback.format_exc(), "#F87171", 11, selectable=True))
        spinner.visible = False
        status.value = "Готово"
        page.update()

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
        load_state(page)
        build_ui(page)
    except Exception:
        page.controls.clear()
        page.add(ft.Text("Ошибка запуска:\n\n" + traceback.format_exc(), color="#F87171", size=12, selectable=True))
        page.update()


ft.app(target=main)