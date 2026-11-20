import re, threading, urllib.parse, traceback
import requests, urllib3
import flet as ft

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

SESSION = requests.Session()
SESSION.trust_env = False


def http_get(url, params=None, headers=None, timeout=(3.0, 6.0)):
    try:
        return SESSION.get(url, params=params, headers=headers, timeout=timeout, verify=False)
    except Exception:
        return None


VERSION = "v17.4"
H_WEB = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/122.0.0.0 Mobile Safari/537.36"}
H_API = {"User-Agent": "TirBrowser/17.4", "Accept": "application/json"}

AD_WORDS = ("реклама", "промо", "спонсор", "купить", "цена", "скидка", "акция", "заказать", "доставка", "кредит", "займ", "казино", "ставки", "услуги", "прайс", "an.yandex", "googleadservices", "doubleclick", "yabs.yandex", "cookie", "политика конфиденциальности", "войти", "регистрация")
STOP_Q = ("когда", "кагда", "где", "кто", "что", "што", "как", "почему", "зачем", "сколько", "какой", "какая", "какие", "родился", "радился", "возраст", "лет", "года", "живет", "живут", "умер", "такое", "значит", "это", "ли", "в", "на", "по", "о", "об")
KB_ROWS = ("йцукенгшщзхъ", "фывапролджэ", "ячсмитьбю")

LOGS = []
HISTORY = ["Европейская норка", "100 долларов", "переведи breakthrough", "250 * 48"]


def short_str(t, n):
    return str(t)[:n]


def clean_txt(raw):
    if not raw:
        return ""
    if BeautifulSoup:
        try:
            soup = BeautifulSoup(str(raw), "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
                tag.decompose()
            blocks = [el.get_text(" ", strip=True) for el in soup.find_all(["h1", "h2", "h3", "p", "li"])]
            t = " ".join(b for b in blocks if len(b) > 25) if blocks else soup.get_text(" ", strip=True)
            t = re.sub(r"\s+", " ", t).strip()
            return " ".join(p for p in re.split(r"(?<=[.!?])\s+", t) if not any(w in p.lower() for w in AD_WORDS)).strip()
        except Exception:
            pass
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(raw))).strip()


def is_ad(u, t):
    return any(w in (str(u) + " " + str(t)).lower() for w in AD_WORDS)


def extract_topic(q):
    words = [w for w in re.sub(r"[^\w\s-]", " ", q.lower()).split() if w not in STOP_Q and len(w) > 1]
    return " ".join(words).strip() if words else q


def fix_glove_word(w):
    if len(w) < 3:
        return w
    res = [w[0]]
    for ch in w[1:]:
        prev = res[-1]
        if not any((prev in r and ch in r and abs(r.find(prev) - r.find(ch)) == 1) for r in KB_ROWS):
            res.append(ch)
    return "".join(res) if len(res) >= 2 else w


def chunk_text(text, size=700):
    """Режет длинный текст на абзацы по границам предложений."""
    parts, cur = [], ""
    for s in re.split(r"(?<=[.!?])\s+", text):
        if len(cur) + len(s) > size and cur:
            parts.append(cur.strip())
            cur = ""
        cur += s + " "
    if cur.strip():
        parts.append(cur.strip())
    return parts


def try_weather(q):
    ql = q.lower().strip()
    if not any(w in ql for w in ("погод", "температур", "градус", "прогноз")):
        return ""
    words = [fix_glove_word(w) for w in re.sub(r"[^\w\s-]", " ", ql).split()]
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
                sky = "Ясно" if code == 0 else ("Переменная облачность" if code in (1, 2, 3) else ("Туман" if code in (45, 48) else ("Осадки" if code < 70 else "Снег")))
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
    is_tr_cmd = ql.startswith(("переведи ", "перевод ", "как будет ", "что значит "))
    is_eng = bool(re.fullmatch(r"[a-zA-Z\s'.,!?-]{2,60}", q.strip()))
    if is_tr_cmd or is_eng:
        txt = re.sub(r"^(переведи|перевод|как будет по[- ]английски|как будет|что значит слово|что значит)\s+", "", q.strip(), flags=re.I).strip()
        if txt:
            has_ru = bool(re.search(r"[а-яА-ЯёЁ]", txt))
            sl, tl = ("ru", "en") if has_ru else ("en", "ru")
            r = http_get("https://translate.googleapis.com/translate_a/single", params={"client": "gtx", "sl": sl, "tl": tl, "dt": "t", "q": txt}, headers=H_WEB)
            if r is not None and r.status_code == 200 and r.text.strip().startswith("["):
                try:
                    tr = "".join(item[0] for item in r.json()[0] if item and item[0])
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


def ddg_instant(q, out, done_ev):
    try:
        r = http_get("https://api.duckduckgo.com/", params={"q": q, "format": "json", "no_html": 1, "skip_disambig": 1, "kl": "ru-ru"})
        if r is not None and r.status_code == 200:
            d = r.json()
            ans = str(d.get("Answer") or d.get("AbstractText") or d.get("Definition") or "").strip()
            if ans and len(ans) > 15:
                out["answer"] = ans
                out["src"] = d.get("AbstractURL") or ""
                done_ev.set()
    except Exception:
        pass


def wiki_summary(q, out, done_ev):
    try:
        topic = extract_topic(q)
        r = http_get("https://ru.wikipedia.org/w/api.php", params={"action": "opensearch", "search": topic, "limit": 1, "namespace": 0, "format": "json", "utf8": 1}, headers=H_API)
        if r is None or r.status_code != 200:
            return
        data = r.json()
        title = data[3][0] if len(data) > 3 and data[3] else None
        if not title:
            return
        title = urllib.parse.unquote(title.rsplit("/", 1)[-1]) if title.startswith("http") else title
        s = http_get("https://ru.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title), headers=H_API)
        if s is None or s.status_code != 200:
            return
        j = s.json()
        ext = str(j.get("extract", "")).strip()
        if ext and len(ext) > 30 and "уменьшительная форма" not in ext.lower():
            out["answer"] = ext
            out["src"] = j.get("content_urls", {}).get("desktop", {}).get("page", "")
            out["title"] = title
            done_ev.set()
    except Exception:
        pass


def wiki_search_cards(q, out_list):
    try:
        topic = extract_topic(q)
        r = http_get("https://ru.wikipedia.org/w/api.php", params={"action": "query", "list": "search", "srsearch": topic, "srlimit": 6, "format": "json", "utf8": 1}, headers=H_API)
        items = r.json().get("query", {}).get("search", []) if r is not None and r.status_code == 200 else []
        for w in items:
            wt, ws = w.get("title", ""), clean_txt(w.get("snippet", ""))
            wu = "https://ru.wikipedia.org/wiki/" + urllib.parse.quote(wt)
            if wt and not is_ad(wu, wt):
                out_list.append({"src": "Вики", "url": wu, "title": wt, "snip": ws})
        LOGS.append("Вики: " + str(len(out_list)))
    except Exception:
        LOGS.append("Вики: сбой")


def rambler_cards(q, out_list):
    cards, seen = [], set()
    try:
        r = http_get("https://nova.rambler.ru/search", params={"query": q}, headers=H_WEB)
        if BeautifulSoup is not None and r is not None and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                if len(cards) >= 6:
                    break
                u = a.get("href", "")
                if not u.startswith("http") or "rambler.ru" in u or "yandex." in u or u in seen:
                    continue
                t = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
                if len(t) > 12 and not is_ad(u, t):
                    seen.add(u)
                    par = a.find_parent(["article", "div", "li"])
                    sn = clean_txt(par.get_text(" ", strip=True).replace(t, "", 1)) if par else ""
                    cards.append({"src": "Рунет", "url": u, "title": t, "snip": sn})
    except Exception:
        pass
    out_list.extend(cards)
    LOGS.append("Рунет: " + str(len(cards)))


def ddg_related(q, out_list):
    try:
        r = http_get("https://api.duckduckgo.com/", params={"q": q, "format": "json", "no_html": 1, "kl": "ru-ru"})
        if r is not None and r.status_code == 200:
            d = r.json()
            for t in d.get("RelatedTopics", [])[:4]:
                if isinstance(t, dict) and t.get("FirstURL") and t.get("Text"):
                    txt = str(t["Text"]).strip()
                    if len(txt) > 15 and not is_ad(t["FirstURL"], txt):
                        out_list.append({"src": "DDG", "url": t["FirstURL"], "title": txt[:60], "snip": txt})
    except Exception:
        pass


def get_domain(url):
    try:
        return urllib.parse.urlparse(url).netloc or url[:30]
    except Exception:
        return url[:30]


def load_page_text(url, title):
    """Достаёт читаемый текст страницы. Для Википедии — через API."""
    if "wikipedia.org/wiki/" in url:
        host = urllib.parse.urlparse(url).netloc
        t = urllib.parse.unquote(url.split("/wiki/", 1)[1].split("#")[0].split("?")[0]).replace("_", " ")
        r = http_get("https://" + host + "/w/api.php", params={"action": "query", "prop": "extracts", "explaintext": "1", "titles": t, "format": "json", "redirects": 1}, headers=H_API, timeout=(4.0, 10.0))
        if r is not None and r.status_code == 200:
            for p in r.json().get("query", {}).get("pages", {}).values():
                ext = str(p.get("extract", "")).strip()
                if len(ext) > 20:
                    return short_str(ext, 8000)
    r = http_get(url, headers=H_WEB, timeout=(4.0, 10.0))
    if r is None:
        return "Не удалось загрузить страницу (нет связи или сайт не отвечает)."
    try:
        r.encoding = r.apparent_encoding
    except Exception:
        pass
    plain = clean_txt(r.text)
    return short_str(plain, 8000) if len(plain) > 60 else "Текст скрыт сайтом от прямого чтения. Нажмите «В браузере»."


def build_ui(page: ft.Page):
    page.title = "Браузер Тир " + VERSION
    page.bgcolor = "#0F172A"
    page.padding = 10

    cur = {"url": "", "title": ""}

    # ---------- ВИД 1: ПОИСК ----------
    ent = ft.TextField(label="Запрос", bgcolor="#1E293B", color="#F8FAFC", border_color="#334155",
                       focused_border_color="#3B82F6", expand=True, on_submit=lambda e: run_search())
    spinner = ft.ProgressRing(width=24, height=24, color="#38BDF8", visible=False)
    status = ft.Text("Готов", color="#94A3B8", size=13)
    results = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=8)
    chip = ft.Row([], wrap=True, spacing=8)

    search_view = ft.Column([
        ft.Text("🌐 Tir Browser " + VERSION, color="#F8FAFC", size=16, weight=ft.FontWeight.BOLD),
        ft.Row([ent, ft.ElevatedButton("НАЙТИ", on_click=lambda e: run_search(), bgcolor="#3B82F6", color="#FFFFFF")]),
        chip,
        ft.Row([spinner, status], spacing=8),
        results,
    ], expand=True)

    # ---------- ВИД 2: ЧТЕНИЕ СТРАНИЦЫ ----------
    r_spinner = ft.ProgressRing(width=20, height=20, color="#38BDF8", visible=False)
    r_title = ft.Text("", color="#F8FAFC", size=15, weight=ft.FontWeight.BOLD, selectable=True)
    r_url = ft.Text("", color="#4ADE80", size=11, selectable=True)
    r_body = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)

    reader_view = ft.Column([
        ft.Row([
            ft.ElevatedButton("← Назад", on_click=lambda e: close_reader(), bgcolor="#334155", color="#F87171"),
            ft.ElevatedButton("🌐 В браузере", on_click=lambda e: open_external(), bgcolor="#334155", color="#38BDF8"),
            r_spinner,
        ], wrap=True, spacing=6),
        ft.Row([
            ft.TextButton("📋 Копировать ссылку", on_click=lambda e: copy_link()),
        ]),
        r_title,
        r_url,
        ft.Divider(color="#1E293B", height=4),
        r_body,
    ], expand=True, visible=False)

    page.add(search_view, reader_view)

    # ---------- ЛОГИКА ----------
    def set_status(text):
        status.value = text
        page.update()

    def open_external():
        try:
            if cur["url"]:
                page.launch_url(cur["url"])
        except Exception as ex:
            set_status("Ошибка: " + str(ex))

    def copy_link():
        try:
            page.set_clipboard(cur["url"])
            r_url.value = cur["url"] + "   [скопировано]"
            page.update()
        except Exception:
            pass

    def close_reader():
        reader_view.visible = False
        search_view.visible = True
        page.update()

    def open_link(url, title=""):
        if not url.startswith("http"):
            url = "https://" + url
        cur["url"], cur["title"] = url, title
        r_title.value = title or get_domain(url)
        r_url.value = url
        r_body.controls.clear()
        r_body.controls.append(ft.Text("Загружаем страницу...", color="#94A3B8", size=13))
        r_spinner.visible = True
        search_view.visible = False
        reader_view.visible = True
        page.update()

        def worker():
            try:
                body = load_page_text(url, title)
            except Exception as ex:
                body = "Ошибка загрузки: " + str(ex)
            r_body.controls.clear()
            for part in chunk_text(body):
                r_body.controls.append(ft.Text(part, color="#E2E8F0", size=14, selectable=True))
            r_spinner.visible = False
            page.update()

        threading.Thread(target=worker, daemon=True).start()

    def render_card(item):
        title = item.get("title", "")[:60]
        url = item.get("url", "")
        snip = item.get("snip", "")[:120]
        src = item.get("src", "")
        results.controls.append(ft.Container(
            content=ft.Column([
                ft.Text("🔗 " + title, color="#60A5FA", size=13, weight=ft.FontWeight.BOLD),
                ft.Text(get_domain(url) + "  •  " + src, color="#64748B", size=10),
            ], spacing=2),
            padding=ft.padding.symmetric(horizontal=8, vertical=6),
            ink=True,
            on_click=lambda e, u=url, t=title: open_link(u, t),
        ))
        if snip:
            results.controls.append(ft.Container(ft.Text(snip, color="#CBD5E1", size=12), padding=ft.padding.only(left=12, right=8)))
        results.controls.append(ft.Divider(color="#1E293B", height=4))

    def run_search():
        q = (ent.value or "").strip()
        if not q:
            return
        if q not in HISTORY:
            HISTORY.insert(0, q)
            update_chips()

        if q.startswith("http://") or q.startswith("https://") or ("." in q and " " not in q):
            open_link(q)
            return

        spinner.visible = True
        status.value = "Ищем..."
        results.controls.clear()
        page.update()

        def worker():
            try:
                LOGS.clear()
                m_ans = try_math(q) or try_smart_tools(q) or try_weather(q)
                if m_ans:
                    results.controls.append(ft.Text("⚡ Ответ", color="#38BDF8", size=16, weight=ft.FontWeight.BOLD))
                    results.controls.append(ft.Text(m_ans, color="#F8FAFC", size=14, selectable=True))
                    spinner.visible = False
                    status.value = "Готово"
                    page.update()
                    return

                ans_slot = {}
                ans_ev = threading.Event()
                threading.Thread(target=ddg_instant, args=(q, ans_slot, ans_ev), daemon=True).start()
                threading.Thread(target=wiki_summary, args=(q, ans_slot, ans_ev), daemon=True).start()
                ans_ev.wait(6.0)

                if ans_slot.get("answer"):
                    results.controls.append(ft.Text("⚡ Быстрый ответ", color="#38BDF8", size=16, weight=ft.FontWeight.BOLD))
                    results.controls.append(ft.Text(clean_txt(ans_slot["answer"])[:400], color="#F8FAFC", size=14, selectable=True))
                    if ans_slot.get("src"):
                        results.controls.append(ft.TextButton("📖 Читать полностью", on_click=lambda e, u=ans_slot["src"], t=ans_slot.get("title", ""): open_link(u, t)))
                    results.controls.append(ft.Divider(color="#334155"))
                    page.update()

                results.controls.append(ft.Text("🔗 ИСТОЧНИКИ", color="#FBBF24", size=15, weight=ft.FontWeight.BOLD))
                page.update()

                cards_wiki, cards_ramb, cards_ddg = [], [], []
                ts = [
                    threading.Thread(target=wiki_search_cards, args=(q, cards_wiki), daemon=True),
                    threading.Thread(target=rambler_cards, args=(q, cards_ramb), daemon=True),
                    threading.Thread(target=ddg_related, args=(q, cards_ddg), daemon=True),
                ]
                for t in ts:
                    t.start()
                for t in ts:
                    t.join(8.0)

                mixed, seen = [], set()
                for grp in zip(cards_wiki + [None] * 6, cards_ramb + [None] * 6, cards_ddg + [None] * 6):
                    for v in grp:
                        if v and v.get("url") not in seen:
                            seen.add(v.get("url"))
                            mixed.append(v)

                if not mixed and not ans_slot.get("answer"):
                    results.controls.append(ft.Text("Ничего не найдено (проверьте интернет).", color="#94A3B8", size=13))

                for item in mixed[:8]:
                    render_card(item)

                spinner.visible = False
                status.value = "Готово"
                page.update()
            except Exception:
                spinner.visible = False
                status.value = "Ошибка поиска"
                results.controls.append(ft.Text(traceback.format_exc(), color="#F87171", size=11, selectable=True))
                page.update()

        threading.Thread(target=worker, daemon=True).start()

    def update_chips():
        chip.controls.clear()
        for h in HISTORY[:4]:
            chip.controls.append(ft.ElevatedButton(h[:20], on_click=lambda e, v=h: pick(v), bgcolor="#334155", color="#38BDF8"))
        page.update()

    def pick(v):
        ent.value = v
        run_search()

    update_chips()


def main(page: ft.Page):
    # Если при старте что-то упадёт — вместо белого экрана покажем текст ошибки.
    try:
        build_ui(page)
    except Exception:
        page.controls.clear()
        page.add(ft.Text("Ошибка запуска:\n\n" + traceback.format_exc(), color="#F87171", size=12, selectable=True))
        page.update()


ft.app(target=main)