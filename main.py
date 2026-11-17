import re, threading, urllib.parse, requests, urllib3
import flet as ft

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

SESSION = requests.Session()
SESSION.trust_env = False

def http_get(url, params=None, headers=None, timeout=7.5, **kw):
    try:
        return SESSION.get(url, params=params, headers=headers, timeout=timeout, verify=False)
    except Exception:
        return None

VERSION = "v14.5"
C_BG, C_TOP, C_ANS = "#0F172A", "#1E293B", "#172554"
C_WARN_BG, C_WARN_FG = "#451A03", "#FCD34D"
C_LINK, C_URL, C_HEAD = "#38BDF8", "#4ADE80", "#F8FAFC"
C_TEXT, C_MUTED, C_BTN, C_SEC, C_BACK = "#E2E8F0", "#94A3B8", "#3B82F6", "#334155", "#F87171"

AD_WORDS = ("реклама","промо","спонсор","купить","цена","скидка","акция","заказать","доставка","кредит","займ","казино","ставки","услуги","прайс","an.yandex","googleadservices","doubleclick","yabs.yandex","cookie","политика конфиденциальности","войти","регистрация")
STOP_Q = ("когда","кагда","где","кто","что","што","как","почему","зачем","сколько","какой","какая","какие","родился","радился","возраст","лет","года","живет","живут","умер","такое","значит","это","ли","в","на","по","о","об")
KB_ROWS = ("йцукенгшщзхъ", "фывапролджэ", "ячсмитьбю")
H_WEB = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"}
H_API = {"User-Agent": "TirBrowser/14.5 (Android; Python-requests)", "Accept": "application/json"}

LOGS, LAST_DATA = [], {}
BOOKMARKS = [{"title": "Европейская норка", "url": "https://wikipedia.org"}]
HISTORY = ["Европейская норка", "100 долларов", "переведи breakthrough", "250 * 48"]
IN_READER = False
CUR_PAGE = {"title": "", "url": ""}

def short_str(txt, limit):
    return str(txt)[:limit]

def clean_txt(raw):
    if not raw: return ""
    if BeautifulSoup:
        try:
            soup = BeautifulSoup(str(raw), "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
                tag.decompose()
            blocks = [el.get_text(" ", strip=True) for el in soup.find_all(["h1", "h2", "h3", "p", "li"])]
            t = " ".join(b for b in blocks if len(b) > 25) if blocks else soup.get_text(" ", strip=True)
            t = re.sub(r"\s+", " ", t).strip()
            return " ".join(p for p in re.split(r"(?<=[.!?])\s+", t) if not any(w in p.lower() for w in AD_WORDS)).strip()
        except Exception: pass
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()
    return " ".join(p for p in re.split(r"(?<=[.!?])\s+", t) if not any(w in p.lower() for w in AD_WORDS)).strip()

def is_ad(u, t):
    return any(w in (str(u) + " " + str(t)).lower() for w in AD_WORDS)

def extract_topic(q):
    words = [w for w in re.sub(r"[^\w\s-]", " ", q.lower()).split() if w not in STOP_Q and len(w) > 1]
    return " ".join(words).strip() if words else q

def fix_glove_word(w):
    if len(w) < 3: return w
    res = [w[0]]
    for ch in w[1:]:
        prev = res[-1]
        if not any((prev in r and ch in r and abs(r.find(prev) - r.find(ch)) == 1) for r in KB_ROWS):
            res.append(ch)
    return "".join(res) if len(res) >= 2 else w

def make_fuzzy(text):
    return " ".join((w + "~" if len(w) >= 3 else w) for w in re.sub(r"[^\w\s-]", " ", text).split() if len(w) > 1)

def try_weather(q):
    ql = q.lower().strip()
    if not any(w in ql for w in ("погод", "температур", "градус", "прогноз")): return ""
    words = [fix_glove_word(w) for w in re.sub(r"[^\w\s-]", " ", ql).split()]
    stop_w = ("какая","какой","сегодня","сеодня","сигодня","севодня","завтра","сейчас","погода","погоду","в","во","на","улице","прогноз","температура","градусов")
    city = " ".join(w for w in words if w not in stop_w and len(w) > 2).strip()
    for cand in ([city, "Москва"] if city else ["Москва"]):
        try:
            g = http_get("https://open-meteo.com", params={"name": cand, "count": 1, "language": "ru"}, timeout=4.5)
            if not g or g.status_code != 200: continue
            res_g = g.json().get("results", [])
            if not res_g: continue
            loc = res_g[0]
            lat, lon, cname = loc.get("latitude"), loc.get("longitude"), loc.get("name", cand)
            w = http_get("https://open-meteo.com", params={"latitude": lat, "longitude": lon, "current_weather": "true"}, timeout=4.5)
            if not w or w.status_code != 200: continue
            cw = w.json().get("current_weather", {})
            if "temperature" not in cw: continue
            temp, wind, code = cw.get("temperature"), cw.get("windspeed"), cw.get("weathercode", 0)
            sky = "Ясно" if code == 0 else ("Переменная облачность" if code in (1, 2, 3) else ("Туман" if code in (45, 48) else ("Осадки / дождь" if code < 70 else "Снег")))
            sign = "+" if float(temp) > 0 else ""
            return f"Погода ({cname}): {sign}{temp}°C, {sky}, ветер {wind} км/ч"
        except Exception: pass
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
            r = requests.get("https://rambler.ru", params={"query": "курс " + cur + " к рублю ЦБ РФ"}, headers=H_WEB, timeout=5.0, verify=False)
            if r.status_code == 200:
                txt = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True) if BeautifulSoup else re.sub(r"<[^>]+>", " ", r.text)
                found = re.findall(r"(?:1\s*(?:usd|eur|cny|доллар|евро|юан)[а-я]*\s*=\s*|курс[^0-9]{0,20})(\d{2,3}[.,]\d{2,4})", txt.lower())
                if not found: found = re.findall(r"(?<![\d.,])(\d{2,3}[.,]\d{2,4})(?![\d.,])", short_str(txt, 15000))
                nums = [float(x.replace(",", ".")) for x in found if 45.0 <= float(x.replace(",", ".")) <= 140.0]
                if nums: val = nums[0]
        except Exception: pass
        if val > 0: return f"{amt} {cur} = {round(amt * val, 2)} RUB (курс: {round(val, 2)} руб.)"
    is_tr_cmd = ql.startswith(("переведи ", "перевод ", "как будет ", "что значит "))
    is_eng = bool(re.fullmatch(r"[a-zA-Z\s'.,!?-]{2,60}", q.strip()))
    if is_tr_cmd or is_eng:
        txt = re.sub(r"^(переведи|перевод|как будет по[- ]английски|как будет|что значит слово|что значит)\s+", "", q.strip(), flags=re.I).strip()
        if txt:
            has_ru = bool(re.search(r"[а-яА-ЯёЁ]", txt))
            sl, tl = ("ru", "en") if has_ru else ("en", "ru")
            try:
                p = {"client": "gtx", "sl": sl, "tl": tl, "dt": "t", "q": txt}
                r = requests.get("https://translate.googleapis.com", params=p, headers=H_WEB, timeout=3.0, verify=False)
                if r.status_code == 200 and r.text.strip().startswith("["):
                    parts = r.json()
                    tr = "".join(item[0] for item in parts[0] if item and item[0])
                    if tr and tr.lower() != txt.lower(): return f"ИИ-перевод ({sl} -> {tl}): {tr}"
            except Exception: pass
    return ""

def try_math(q):
    expr = q.lower().replace("сколько будет","").replace("посчитай","").replace("=","").replace(",",".").replace("х","*").replace("x","*").replace(":","/").strip()
    if expr and re.fullmatch(r"[0-9+\-*/().\s]+", expr) and any(op in expr for op in "+-*/"):
        try:
            res = eval(expr, {"__builtins__": None}, {})
            return "Ответ: " + str(int(res) if isinstance(res, float) and res.is_integer() else res)
        except Exception: pass
    return ""

def word_exists(w):
    try:
        p = {"action": "query", "list": "search", "srsearch": w, "srlimit": 1, "format": "json"}
        r = http_get("https://ru.wikipedia.org", params=p, headers=H_API, timeout=7.0, verify=False)
        items = r.json().get("query", {}).get("search", []) if r and r.status_code == 200 else []
        return any(w.lower() in it.get("title", "").lower() for it in items)
    except Exception: return False

def check_typo(q):
    if re.search(r"[a-zA-Z]", q): return " ".join(q.split()), False
    qc = " ".join(q.split())
    if len(qc.split()) == 1 and word_exists(qc): return qc, False
    gq = " ".join(fix_glove_word(w) for w in qc.lower().split())
    for cand in ([qc] if gq == qc.lower() else [qc, gq]):
        try:
            r = http_get("https://mail.ru", params={"q": cand}, headers=H_WEB, timeout=7.0, verify=False)
            if r and r.status_code == 200 and r.text.strip().startswith("{"):
                best = str(r.json().get("items", [{}])[0].get("text", "")).strip()
                if best and best.lower() != qc.lower() and len(best) <= len(qc) + 8 and not word_exists(qc):
                    return best, True
        except Exception: pass
    if gq != qc.lower() and not word_exists(qc) and word_exists(gq): return gq, True
    return qc, False

def wiki_api_search(domain, src_name, q):
    cards = []
    w_api = "https://" + domain + "/w/api.php"
    try:
        topic = extract_topic(q)
        p = {"action": "query", "list": "search", "srsearch": topic, "srlimit": 5, "format": "json", "utf8": 1}
        r = http_get(w_api, params=p, headers=H_API, timeout=7.0, verify=False)
        items = r.json().get("query", {}).get("search", []) if (r and r.status_code == 200 and r.text.strip().startswith("{")) else []
        if not items:
            p["srsearch"] = make_fuzzy(topic)
            r = http_get(w_api, params=p, headers=H_API, timeout=7.0, verify=False)
            items = r.json().get("query", {}).get("search", []) if (r and r.status_code == 200 and r.text.strip().startswith("{")) else []
        for w in items:
            wt, ws = w.get("title", ""), clean_txt(w.get("snippet", ""))
            wu = "https://" + domain + "/wiki/" + urllib.parse.quote(wt)
            if wt and not is_ad(wu, wt): cards.append({"src": src_name, "url": wu, "title": wt, "snip": ws})
    except Exception: pass
    return cards

def stream_1_ddg(q):
    cards = wiki_api_search("ru.ruwiki.ru", "Рунет 1", q)
    LOGS.append("Поток 1 (Рунет): " + str(len(cards)))
    return cards

def stream_2_runet(q):
    cards = wiki_api_search("ru.wiktionary.org", "Словарь 2", q)
    tws = [short_str(w, 4) for w in extract_topic(q).split() if len(w) > 2]
    if not tws: return cards
    return [c for c in cards if any(tw in c.get("title", "").lower() or tw in c.get("snip", "").lower() for tw in tws)]

def stream_3_wiki(q):
    return wiki_api_search("ru.wikipedia.org", "Вики 3", q)

def read_wiki_fast(title, limit=3500):
    if not title: return ""
    try:
        p = {"action": "query", "prop": "extracts", "explaintext": "1", "exintro": "1" if limit < 800 else "0", "titles": title, "format": "json"}
        r = http_get("https://ru.wikipedia.org", params=p, headers=H_API, timeout=7.0, verify=False)
        if not r or r.status_code != 200: return ""
        pages = r.json().get("query", {}).get("pages", {})
        for pid in pages:
            ext = pages[pid].get("extract", "")
            if ext and len(ext.strip()) > 20: return short_str(ext.strip(), limit)
    except Exception: pass
    return ""

def clean_ans_text(t):
    t = re.sub(r"\[[^\]]+\]|◆|\?\?|Корень:[^.]+\.|Существительное\.", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def smart_fact_answer(q, text_pool):
    if not text_pool: return ""
    need_num = any(w in q.lower() for w in ("сколько","возраст","лет","года","вес","рост","длина","скорость","температура","когда","год"))
    tws = [short_str(w, 5) for w in extract_topic(q).split() if len(w) > 2]
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text_pool) if 18 <= len(s.strip()) <= 280]
    if not need_num and sents:
        for sc in sents:
            if any(tw in sc.lower() for tw in tws) and (" — " in sc or " - " in sc or " это " in sc.lower()): return sc
        return sents[0] if sents else ""
    scored = []
    for sc in sents:
        score = sum(3 for tw in tws if tw in sc.lower())
        if need_num and re.search(r"\d", sc):
            score += 9 if re.search(r"\b(лет|год|года|году|месяц|дней|дня|час|мин|сек|кг|г|тонн|км|м|см|мм|%|тыс|млн|млрд)\b", sc.lower()) else 5
        if score >= 5: scored.append((score, sc))
    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        return " ".join(dict.fromkeys(s for _, s in scored[:2]))
    return sents[0] if sents else ""

def build_best_answer(uq, mixed, c2, c3):
    wiki_text = ""
    for item in (c3 or [])[:3]:
        cand = read_wiki_fast(item.get("title", ""), 900)
        if cand and "уменьшительная форма" not in cand.lower() and "топоним" not in cand.lower() and len(cand) > 80:
            wiki_text = clean_ans_text(cand)
            break
    snips = [clean_ans_text(c.get("snip", "")) for c in mixed if len(c.get("snip", "").strip()) > 30 and "Существительное" not in c.get("snip", "")]
    fact = smart_fact_answer(uq, (wiki_text + " " + " ".join(snips)).strip())
    if fact and len(fact) > 35: return clean_ans_text(fact)
    if wiki_text:
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", wiki_text) if len(s.strip()) > 25]
        return " ".join(sents[:2]) if sents else short_str(wiki_text, 350)
    if snips: return " ".join(snips[:2])
    return "Точный ответ не найден. Откройте любую ссылку ниже."

# ==================== FLET ИНТЕРФЕЙС (как tkinter, но лучше) ====================

def main(page: ft.Page):
    global IN_READER, LAST_DATA, HISTORY
    
    page.title = "Браузер Тир " + VERSION
    page.bgcolor = C_TOP
    page.padding = 0
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE)
    
    # Поле ввода
    entry = ft.TextField(
        value="",
        label="Адрес сайта / запрос",
        bgcolor=C_BG,
        color=C_HEAD,
        cursor_color="#FFFFFF",
        border_color=C_SEC,
        focused_border_color=C_BTN,
        text_size=14,
        height=50,
        expand=True,
        on_submit=lambda e: run_search()
    )
    
    # Кнопка X (очистить)
    btn_x = ft.IconButton(
        icon=ft.Icons.CLOSE,
        icon_color=C_HEAD,
        icon_size=20,
        bgcolor=C_SEC,
        on_click=lambda e: (entry.__setattr__("value", ""), entry.focus())
    )
    
    # Строка поиска
    search_row = ft.Container(
        content=ft.Row([entry, btn_x], spacing=8),
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        bgcolor=C_TOP
    )
    
    # Кнопка НАЙТИ
    btn_find = ft.ElevatedButton(
        "НАЙТИ",
        on_click=lambda e: run_search(),
        bgcolor=C_BTN,
        color="#FFFFFF",
        height=45,
        style=ft.ButtonStyle(
            text_style=ft.TextStyle(size=14, weight=ft.FontWeight.BOLD),
            shape=ft.RoundedRectangleBorder(radius=8)
        )
    ).expand(True)
    
    find_row = ft.Container(
        content=ft.Row([btn_find], spacing=0),
        padding=ft.padding.symmetric(horizontal=12, vertical=4)
    )
    
    # Чипы истории
    chip_row = ft.Row([], wrap=True, spacing=8)
    chip_container = ft.Container(content=chip_row, padding=ft.padding.symmetric(horizontal=12, vertical=6))
    
    # Полоса опечатки
    typo_bar = ft.Container(
        content=ft.Text("", color=C_WARN_FG, size=12),
        bgcolor=C_WARN_BG,
        padding=ft.padding.symmetric(horizontal=12, vertical=6),
        visible=False
    )
    
    # Основной вывод
    output = ft.Text(
        "Версия " + VERSION + " готова.",
        color=C_HEAD,
        size=14,
        selectable=True,
        font_family="monospace"
    )
    
    output_scroll = ft.Column(
        [output],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=0
    )
    
    output_container = ft.Container(
        content=output_scroll,
        expand=True,
        padding=ft.padding.all(12),
        bgcolor=C_BG
    )
    
    # Нижняя панель
    btn_kb = ft.ElevatedButton(
        "КЛАВИАТУРА",
        bgcolor=C_SEC,
        color=C_HEAD,
        height=40,
        expand=True,
        style=ft.ButtonStyle(text_style=ft.TextStyle(size=12, weight=ft.FontWeight.BOLD))
    )
    
    btn_paste = ft.ElevatedButton(
        "ВСТАВИТЬ",
        bgcolor="#0F766E",
        color="#FFFFFF",
        height=40,
        expand=True,
        style=ft.ButtonStyle(text_style=ft.TextStyle(size=12, weight=ft.FontWeight.BOLD))
    )
    
    bottom_bar = ft.Container(
        content=ft.Row([btn_kb, btn_paste], spacing=8),
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        bgcolor=C_TOP
    )
    
    # Верхняя панель
    header = ft.Container(
        content=ft.Row([
            ft.Text("Браузер Тир " + VERSION, color=C_HEAD, size=14, weight=ft.FontWeight.BOLD),
            ft.ElevatedButton(
                "ЗАКЛАДКИ",
                on_click=lambda e: show_bookmarks(),
                bgcolor=C_SEC,
                color="#FBBF24",
                height=35,
                style=ft.ButtonStyle(text_style=ft.TextStyle(size=11, weight=ft.FontWeight.BOLD))
            ),
            ft.ElevatedButton(
                "ВЫХОД",
                on_click=lambda e: page.window_close(),
                bgcolor="#7F1D1D",
                color="#FCA5A5",
                height=35,
                style=ft.ButtonStyle(text_style=ft.TextStyle(size=11, weight=ft.FontWeight.BOLD))
            )
        ], spacing=8),
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        bgcolor=C_TOP
    )
    
    # Собрать всё вместе
    page.add(
        header,
        search_row,
        find_row,
        chip_container,
        typo_bar,
        output_container,
        bottom_bar
    )
    
    # Обновить чипы
    def update_chips():
        chip_row.controls.clear()
        for h in HISTORY[:4]:
            lbl = h[:17] + (".." if len(h) > 17 else "")
            chip_row.controls.append(
                ft.ElevatedButton(
                    lbl,
                    on_click=lambda e, v=h: (entry.__setattr__("value", v), run_search()),
                    bgcolor=C_SEC,
                    color=C_LINK,
                    height=35,
                    style=ft.ButtonStyle(text_style=ft.TextStyle(size=11, weight=ft.FontWeight.BOLD))
                )
            )
        page.update()
    
    update_chips()
    
    def show_typo(msg):
        if msg:
            typo_bar.content.value = msg
            typo_bar.visible = True
        else:
            typo_bar.visible = False
        page.update()
    
    def draw_results():
        global IN_READER
        IN_READER = False
        if not LAST_DATA: return
        lines = ["══ БЫСТРЫЙ ОТВЕТ ══", "", " " + str(LAST_DATA.get("ans", "")), "", "══ НАЙДЕННЫЕ ИСТОЧНИКИ ══", ""]
        mixed = LAST_DATA.get("mixed", [])
        if mixed:
            for cnt, item in enumerate(mixed[:10], 1):
                u, t, sn = item.get("url", ""), item.get("title", ""), item.get("snip", "")
                lines.append(f"[{item.get('src', '')}] {t}")
                lines.append(short_str(u, 52))
                if sn: lines.append(short_str(sn, 150))
                lines.append("")
        else:
            lines.append("Ничего не найдено.")
        lines.append("══ СТАТУС ПОТОКОВ ══")
        lines.extend(LAST_DATA.get("logs", []))
        output.value = "\n".join(lines)
        output.color = C_TEXT
        page.update()
    
    def run_search():
        global IN_READER, LAST_DATA
        q = entry.value.strip()
        if not q: return
        if q not in HISTORY: HISTORY.insert(0, q); update_chips()
        show_typo("")
        output.value = "◐ Ищем «" + q + "»..."
        output.color = C_HEAD
        page.update()
        
        def worker():
            global LAST_DATA
            LOGS.clear()
            try:
                m_ans = try_math(q) or try_weather(q) or try_smart_tools(q)
                if m_ans:
                    LAST_DATA = {"q": q, "uq": q, "ans": m_ans, "mixed": [], "logs": ["Калькулятор: готово"]}
                    page.run_task(draw_results)
                    return
                uq, has_typo = (q, False) if False else check_typo(q)
                if has_typo:
                    page.run_task(lambda: show_typo("Опечатка! Ищем: «" + uq + "»"))
                res = {"c1": [], "c2": [], "c3": []}
                t1 = threading.Thread(target=lambda: res.update(c1=stream_1_ddg(uq)))
                t2 = threading.Thread(target=lambda: res.update(c2=stream_2_runet(uq)))
                t3 = threading.Thread(target=lambda: res.update(c3=stream_3_wiki(uq)))
                t1.start(); t2.start(); t3.start()
                t1.join(5.0); t2.join(5.0); t3.join(5.0)
                c1, c2, c3 = res["c1"], res["c2"], res["c3"]
                mixed = [v for grp in zip(c1 + [None]*6, c2 + [None]*6, c3 + [None]*6) for v in grp if v]
                ans = build_best_answer(uq, mixed, c2, c3)
                LAST_DATA = {"q": q, "uq": uq, "ans": ans, "mixed": mixed, "logs": list(LOGS)}
                page.run_task(draw_results)
            except Exception as err:
                page.run_task(lambda: (output.__setattr__("value", "Сбой: " + str(err)), page.update()))
        
        threading.Thread(target=worker, daemon=True).start()
    
    def show_bookmarks():
        global IN_READER
        IN_READER = True
        lines = ["( <--- НАЗАД К ПОИСКУ )", "", "ИЗБРАННЫЕ ЗАКЛАДКИ", ""]
        for idx, b in enumerate(BOOKMARKS, 1):
            lines.append(f"{idx}. {b['title']}")
            lines.append(short_str(b['url'], 52))
            lines.append("")
        output.value = "\n".join(lines)
        output.color = C_TEXT
        page.update()

ft.app(target=main)