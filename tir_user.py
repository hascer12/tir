import os
import tkinter as tk
import html, re, threading, urllib.parse, requests, urllib3
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
        return http_get(url, params=params, headers=headers, timeout=timeout, verify=False)
def http_post(url, data=None, headers=None, timeout=7.5, **kw):
    try:
        return SESSION.post(url, data=data, headers=headers, timeout=timeout, verify=False)
    except Exception:
        return http_post(url, data=data, headers=headers, timeout=timeout, verify=False)
NL = chr(10)
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

LOGS, LAST_DATA = list(), dict()
TOUCH = dict(sy=0, ly=0, moved=False)
IN_READER = False

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
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(str(raw)))).strip()
    return " ".join(p for p in re.split(r"(?<=[.!?])\s+", t) if not any(w in p.lower() for w in AD_WORDS)).strip()
def is_ad(u, t):
    return any(w in (str(u) + " " + str(t)).lower() for w in AD_WORDS)

def extract_topic(q):
    words = [w for w in re.sub(r"[^\w\s-]", " ", q.lower()).split() if w not in STOP_Q and len(w) > 1]
    return " ".join(words).strip() if words else q

def fix_glove_word(w):
    if len(w) < 3: return w
    res = [next(iter(w))]
    for ch in w[1:]:
        prev = res[-1]
        if not any((prev in r and ch in r and abs(r.find(prev) - r.find(ch)) == 1) for r in KB_ROWS):
            res.append(ch)
    return "".join(res) if len(res) >= 2 else w

def make_fuzzy(text):
    return " ".join((w + "~" if len(w) >= 3 else w) for w in re.sub(r"[^\w\s-]", " ", text).split() if len(w) > 1)

BOOKMARKS = [{"title": "Европейская норка", "url": "https://wikipedia.org"}]
CUR_PAGE = {"title": "", "url": ""}
HISTORY = ["Европейская норка", "100 долларов", "переведи breakthrough", "250 * 48"]
def try_weather(q):
    ql = q.lower().strip()
    if not any(w in ql for w in ("погод", "температур", "градус", "прогноз")):
        return ""
    words = [fix_glove_word(w) for w in re.sub(r"[^\w\s-]", " ", ql).split()]
    stop_w = ("какая","какой","сегодня","сеодня","сигодня","севодня","завтра","сейчас","погода","погоду","в","во","на","улице","прогноз","температура","градусов")
    city = " ".join(w for w in words if w not in stop_w and len(w) > 2).strip()
    for cand in ([city, "Москва"] if city else ["Москва"]):
        try:
            g = http_get("https://open-meteo.com", params={"name": cand, "count": 1, "language": "ru"}, timeout=4.5)
            res_g = g.json().get("results", list()) if g.status_code == 200 else list()
            if res_g:
                loc = next(iter(res_g))
                lat, lon, cname = loc.get("latitude"), loc.get("longitude"), loc.get("name", cand)
                w = http_get("https://open-meteo.com", params={"latitude": lat, "longitude": lon, "current_weather": "true"}, timeout=4.5)
                cw = w.json().get("current_weather", dict()) if w.status_code == 200 else dict()
                if "temperature" in cw:
                    temp = cw.get("temperature")
                    wind = cw.get("windspeed")
                    code = cw.get("weathercode", 0)
                    sky = "Ясно" if code == 0 else ("Переменная облачность" if code in (1, 2, 3) else ("Туман" if code in (45, 48) else ("Осадки / дождь" if code < 70 else "Снег")))
                    sign = "+" if float(temp) > 0 else ""
                    return "Погода (" + cname + "): " + sign + str(temp) + "°C, " + sky + ", ветер " + str(wind) + " км/ч"
        except Exception: pass
    try:
        r = http_get("https://wttr.in", params={"format": "%t, %C, ветер %w", "lang": "ru"}, timeout=5.0)
        if r.status_code == 200 and r.text.strip():
            wt = r.text.replace("++", "+").replace("↖", "").replace("↗", "").replace("↘", "").replace("↙", "").replace("↑", "").replace("↓", "").replace("←", "").replace("→", "").strip()
            for en, ru in (("Patchy rain nearby", "местами дождь"), ("Light rain", "небольшой дождь"), ("Partly cloudy", "переменная облачность"), ("Overcast", "пасмурно"), ("Clear", "ясно"), ("Sunny", "солнечно"), ("Light snow", "небольшой снег"), ("Fog", "туман"), ("km/h", "км/ч")):
                wt = wt.replace(en, ru).replace(en.lower(), ru)
            return "Погода (Москва): " + re.sub(r"\s+", " ", wt)
    except Exception: pass
    return ""
def try_smart_tools(q):
    ql = q.lower().strip()
    has_cur = bool(re.search(r"(дол|жол|usd|usa|сша|евр|eur|юан|cny)", ql))
    if has_cur and (any(w in ql for w in ("курс", "волют", "валют", "рубл", "скольк", "цен", "стои", "в ")) or re.search(r"\d", ql)):
        m = re.search(r"(\d+(?:[.,]\d+)?)", ql)
        amt = float(m.group(1).replace(",", ".")) if m else 1.0
        cur = "EUR" if re.search(r"(евр|eur)", ql) else ("CNY" if re.search(r"(юан|cny)", ql) else "USD")
        cname = "евро" if cur == "EUR" else ("юаня" if cur == "CNY" else "доллара")
        val = 0.0
        try:
            r = requests.get("https://rambler.ru", params={"query": "курс " + cur + " к рублю ЦБ РФ"}, headers=H_WEB, timeout=5.0, verify=False)
            if r.status_code == 200:
                txt = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True) if BeautifulSoup else re.sub(r"<[^>]+>", " ", r.text)
                found = re.findall(r"(?:1\s*(?:usd|eur|cny|доллар|евро|юан)[а-я]*\s*=\s*|курс[^0-9]{0,20})(\d{2,3}[.,]\d{2,4})", txt.lower())
                if not found:
                    found = re.findall(r"(?<![\d.,])(\d{2,3}[.,]\d{2,4})(?![\d.,])", short_str(txt, 15000))
                nums = [float(x.replace(",", ".")) for x in found if 45.0 <= float(x.replace(",", ".")) <= 140.0]
                if nums:
                    val = next(iter(nums))
        except Exception: pass
        if val > 0:
            return str(amt) + " " + cur + " = " + str(round(amt * val, 2)) + " RUB (курс: " + str(round(val, 2)) + " руб.)"
    is_tr_cmd = ql.startswith(("переведи ", "перевод ", "как будет ", "что значит "))
    is_eng = bool(re.fullmatch(r"[a-zA-Z\s'.,!?-]{2,60}", q.strip()))
    if is_tr_cmd or is_eng:
        txt = re.sub(r"^(переведи|перевод|как будет по[- ]английски|как будет|что значит слово|что значит)\s+", "", q.strip(), flags=re.I).strip()
        if txt:
            has_ru = bool(re.search(r"[а-яА-ЯёЁ]", txt))
            sl, tl = ("ru", "en") if has_ru else ("en", "ru")
            try:
                p = {"client": "gtx", "sl": sl, "tl": tl, "dt": "t", "q": txt}
                r = requests.get("https://googleapis.com", params=p, headers=H_WEB, timeout=3.0, verify=False)
                if r.status_code == 200 and r.text.strip().startswith("["):
                    parts = r.json()
                    tr = "".join(next(iter(item)) for item in next(iter(parts)) if item and next(iter(item)))
                    if tr and tr.lower() != txt.lower():
                        return "ИИ-перевод (" + sl + " -> " + tl + "): " + tr
            except Exception: pass
            try:
                r2 = requests.get("https://wiktionary.org", params={"action": "query", "prop": "extracts", "explaintext": "1", "exchars": 350, "titles": txt.lower(), "format": "json"}, headers=H_API, timeout=2.5, verify=False)
                pages = r2.json().get("query", dict()).get("pages", dict()) if r2.status_code == 200 else dict()
                for pid in pages:
                    if str(pid) != "-1":
                        ext = clean_ans_text(pages[pid].get("extract", ""))
                        if ext and len(ext) > 15: return "Словарь (" + txt + "): " + short_str(ext, 240)
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
        r = http_get("https://wikipedia.org", params=p, headers=H_API, timeout=7.0, verify=False)
        items = r.json().get("query", dict()).get("search", list()) if r.status_code == 200 else list()
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
            if r.status_code == 200 and r.text.strip().startswith("{"):
                best = str(next(iter(r.json().get("items", list())), dict()).get("text", "")).strip()
                if best and best.lower() != qc.lower() and len(best) <= len(qc) + 8 and not word_exists(qc):
                    return best, True
        except Exception: pass
    if gq != qc.lower() and not word_exists(qc) and word_exists(gq): return gq, True
    return qc, False
def stream_1_ddg(q):
    cards, seen, mode = list(), set(), "runet"
    hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36", "Accept-Language": "ru-RU,ru;q=0.9"}
    try:
        r = http_get("https://rambler.ru", params={"query": q}, headers=hdrs, timeout=7.0, verify=False)
        if BeautifulSoup and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                if len(cards) >= 6: break
                u = a.get("href", "")
                if not u.startswith("http") or "rambler.ru" in u or "yandex." in u or u in seen: continue
                t = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
                if len(t) > 12 and not is_ad(u, t):
                    seen.add(u)
                    par = a.find_parent(["article", "div", "li"])
                    sn = clean_txt(par.get_text(" ", strip=True).replace(t, "", 1)) if par else ""
                    cards.append({"src": "Рунет 1", "url": u, "title": t, "snip": sn})
            if cards: mode = "rambler-bs4"
    except Exception: pass
    if not cards:
        cards = wiki_api_search("ru.ruwiki.ru", "Рунет 1", q)
        if cards: mode = "ruwiki"
    LOGS.append("Поток 1 (Рунет): " + str(len(cards)) + " [" + mode + "]")
    return cards
def wiki_api_search(domain, src_name, q):
    cards = list()
    w_api = "https://" + domain + "/w/api.php"
    try:
        topic = extract_topic(q)
        p = {"action": "query", "list": "search", "srsearch": topic, "srlimit": 5, "format": "json", "utf8": 1}
        r = http_get(w_api, params=p, headers=H_API, timeout=7.0, verify=False)
        items = r.json().get("query", dict()).get("search", list()) if (r.status_code == 200 and r.text.strip().startswith("{")) else list()
        if not items:
            p["srsearch"] = make_fuzzy(topic)
            r = http_get(w_api, params=p, headers=H_API, timeout=7.0, verify=False)
            items = r.json().get("query", dict()).get("search", list()) if (r.status_code == 200 and r.text.strip().startswith("{")) else list()
        for w in items:
            wt, ws = w.get("title", ""), clean_txt(w.get("snippet", ""))
            wu = "https://" + domain + "/wiki/" + urllib.parse.quote(wt)
            if wt and not is_ad(wu, wt): cards.append({"src": src_name, "url": wu, "title": wt, "snip": ws})
        LOGS.append(src_name + ": " + str(len(cards)))
    except Exception as e: LOGS.append(src_name + " сбой: " + str(e))
    return cards
def stream_2_runet(q):
    cards = wiki_api_search("ru.wiktionary.org", "Словарь 2", q)
    tws = [short_str(w, 4) for w in extract_topic(q).split() if len(w) > 2]
    if not tws: return cards
    return [c for c in cards if any(tw in c.get("title", "").lower() or tw in c.get("snip", "").lower() for tw in tws)]
def stream_3_wiki(q): return wiki_api_search("ru.wikipedia.org", "Вики 3", q)

def read_wiki_fast(title, limit=3500):
    if not title: return ""
    try:
        p = {"action": "query", "prop": "extracts", "explaintext": "1", "exintro": "1" if limit < 800 else "0", "titles": title, "format": "json"}
        r = http_get("https://wikipedia.org", params=p, headers=H_API, timeout=7.0, verify=False)
        pages = r.json().get("query", dict()).get("pages", dict())
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
        return next(iter(sents), "")
    scored = list()
    for sc in sents:
        score = sum(3 for tw in tws if tw in sc.lower())
        if need_num and re.search(r"\d", sc):
            score += 9 if re.search(r"\b(лет|год|года|году|месяц|дней|дня|час|мин|сек|кг|г|тонн|км|м|см|мм|%|тыс|млн|млрд)\b", sc.lower()) else 5
        if score >= 5: scored.append((score, sc))
    if scored:
        scored.sort(key=lambda x: next(iter(x)), reverse=True)
        return " ".join(dict.fromkeys(s for _, s in scored[:2]))
    return next(iter(sents), "")

def build_best_answer(uq, mixed, c2, c3):
    wiki_text = ""
    for item in (c3 or list())[:3]:
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

def go_back(e=None):
    if not TOUCH.get("moved"): draw_results()
def open_link(url, title):
    global IN_READER
    IN_READER = True
    CUR_PAGE.update({"title": title, "url": url})
    st = {"done": False, "step": 0}
    def spin():
        if st["done"] or not IN_READER: return
        ch = ("◐", "◓", "◑", "◒")[st["step"] % 4]
        st["step"] += 1
        box.delete("1.0", tk.END)
        box.insert(tk.END, "( <--- НАЗАД К ПОИСКУ )" + NL + NL, "back")
        box.insert(tk.END, ch + " Загружаем страницу..." + NL + NL, "head")
        box.insert(tk.END, title, "muted")
        root.after(150, spin)
    def worker_load():
        body = ""
        try:
            if "wikipedia.org/wiki/" in url:
                body = read_wiki_fast(title, 3500)
            elif "ruwiki.ru/wiki/" in url:
                p = {"action": "query", "prop": "extracts", "explaintext": "1", "titles": title, "format": "json"}
                r = http_get("https://ruwiki.ru", params=p, headers=H_API, timeout=7.0, verify=False)
                pages = r.json().get("query", dict()).get("pages", dict())
                for pid in pages:
                    ext = pages[pid].get("extract", "")
                    if ext and len(ext.strip()) > 20: body = short_str(ext.strip(), 3500)
            if not body:
                r = http_get(url, headers=H_WEB, timeout=8.0, verify=False)
                r.encoding = r.apparent_encoding
                plain = clean_txt(r.text)
                body = short_str(plain, 3500) if len(plain) > 60 else "Текст скрыт сайтом от прямого чтения."
        except Exception as e:
            body = "Ошибка загрузки: " + str(e)
        def render_page():
            st["done"] = True
            if not IN_READER: return
            def copy_cur():
                try:
                    root.clipboard_clear()
                    root.clipboard_append(url)
                    box.insert("3.0", "[ССЫЛКА СКОПИРОВАНА]" + NL + NL, "badge")
                except Exception: pass
            box.delete("1.0", tk.END)
            box.insert(tk.END, "( <--- НАЗАД К ПОИСКУ )" + NL + NL, "back")
            box.insert(tk.END, "( + В ЗАКЛАДКИ )   ", "bm_add")
            box.tag_config("bm_add", foreground="#FBBF24", font=("sans-serif", 11, "bold"), underline=True)
            box.tag_bind("bm_add", "<Button-1>", lambda e: save_bookmark())
            box.insert(tk.END, "( КОПИРОВАТЬ ССЫЛКУ )" + NL + NL, "cp_btn")
            box.tag_config("cp_btn", foreground="#38BDF8", font=("sans-serif", 11, "bold"), underline=True)
            box.tag_bind("cp_btn", "<Button-1>", lambda e: copy_cur())
            box.insert(tk.END, "=== " + title + " ===" + NL, "head")
            box.insert(tk.END, url + NL + NL, "url")
            box.insert(tk.END, body)
        root.after(10, render_page)
    spin()
    root.after(60, lambda: threading.Thread(target=worker_load, daemon=True).start())
def on_press(e):
    TOUCH.update({"sy": e.y, "ly": e.y, "moved": False})
    box.tag_remove("sel", "1.0", tk.END)

def on_drag(e):
    dy = TOUCH.get("ly", e.y) - e.y
    if abs(e.y - TOUCH.get("sy", e.y)) > 14: TOUCH.update({"moved": True})
    if abs(dy) >= 12:
        box.yview_scroll(int(dy / 12), "units")
        TOUCH.update({"ly": e.y})
    box.tag_remove("sel", "1.0", tk.END)
    return "break"
def draw_results():
    global IN_READER
    IN_READER = False
    if not LAST_DATA: return
    box.delete("1.0", tk.END)
    box.insert(tk.END, "БЫСТРЫЙ ОТВЕТ" + NL, "head")
    box.insert(tk.END, " " + str(LAST_DATA.get("ans", "")) + NL + NL, "ans")
    box.insert(tk.END, "НАЙДЕННЫЕ ИСТОЧНИКИ" + NL + NL, "head")
    mixed = LAST_DATA.get("mixed", list())
    if mixed:
        for cnt, item in enumerate(mixed[:10], 1):
            u, t, sn = item.get("url", ""), item.get("title", ""), item.get("snip", "")
            tag = "l_" + str(cnt)
            box.insert(tk.END, "[" + item.get("src", "") + "] ", "badge")
            box.insert(tk.END, t + NL, tag)
            box.insert(tk.END, short_str(u, 52) + ("..." if len(u) > 52 else "") + NL, ("url", tag))
            box.tag_config(tag, foreground=C_LINK, font=("sans-serif", 12, "bold"), underline=True)
            box.tag_bind(tag, "<Button-1>", lambda e, link=u, head=t: open_link(link, head))
            if sn: box.insert(tk.END, short_str(sn, 150) + "..." + NL, "snip")
            box.insert(tk.END, NL)
    else: box.insert(tk.END, "Ничего не найдено." + NL, "muted")
    box.insert(tk.END, "СТАТУС ПОТОКОВ" + NL, "head")
    box.insert(tk.END, NL.join(LAST_DATA.get("logs", list())), "muted")
def show_typo_bar(msg=""):
    if msg:
        lbl_typo.config(text=msg)
        lbl_typo.pack(fill=tk.X, padx=6, pady=(0, 4))
    else: lbl_typo.pack_forget()

def run_search(force_raw=False):
    global IN_READER
    q = entry.get().strip()
    if (IN_READER and LAST_DATA and q == LAST_DATA.get("q", "") and not force_raw) or not q:
        if IN_READER and LAST_DATA: draw_results()
        return
    LOGS.clear()
    if q not in HISTORY: HISTORY.insert(0, q); refresh_chips()
    show_typo_bar("")
    state = {"done": False, "step": 0}
    def animate():
        if state["done"]: return
        ch = ("◐", "◓", "◑", "◒")[state["step"] % 4]
        state["step"] += 1
        box.delete("1.0", tk.END)
        box.insert(tk.END, ch + " Ищем «" + q + "»...\n", "head")
        root.after(180, animate)
    def worker():
        try:
            m_ans = try_math(q) or try_weather(q) or try_smart_tools(q)
            if m_ans:
                LAST_DATA.clear()
                LAST_DATA.update({"q": q, "uq": q, "ans": m_ans, "mixed": list(), "logs": ["Калькулятор: готово"]})
                state["done"] = True
                root.after(10, draw_results)
                return
            uq, has_typo = (q, False) if force_raw else check_typo(q)
            if has_typo: root.after(10, lambda: show_typo_bar("Опечатка! Ищем: «" + uq + "» (нажмите для исходного)"))
            res = {"c1": list(), "c2": list(), "c3": list()}
            t1 = threading.Thread(target=lambda: res.update(c1=stream_1_ddg(uq)))
            t2 = threading.Thread(target=lambda: res.update(c2=stream_2_runet(uq)))
            t3 = threading.Thread(target=lambda: res.update(c3=stream_3_wiki(uq)))
            t1.start(); t2.start(); t3.start()
            t1.join(5.0); t2.join(5.0); t3.join(5.0)
            c1, c2, c3 = res["c1"], res["c2"], res["c3"]
            mixed = [v for grp in zip(c1 + [None]*6, c2 + [None]*6, c3 + [None]*6) for v in grp if v]
            ans = build_best_answer(uq, mixed, c2, c3)
            LAST_DATA.clear()
            LAST_DATA.update({"q": q, "uq": uq, "ans": ans, "mixed": mixed, "logs": list(LOGS)})
            state["done"] = True
            root.after(10, draw_results)
        except Exception as err:
            state["done"] = True
            root.after(10, lambda: (box.delete("1.0", tk.END), box.insert(tk.END, "Сбой: " + str(err), "back")))
    animate()
    threading.Thread(target=worker, daemon=True).start()
KB_OPEN = False
KB_LANG = "RU"
KB_BTNS = list()
ROWS_RU = ["1234567890", "йцукенгшщзх", "фывапролджэ", "ёячсмитьбю"]
ROWS_EN = ["1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm."]
ROWS_SYM = ["1234567890", "+-*/=()[]{}", "?!.,:;@#№%", "<>$₽&~_|\^"]
def do_paste():
    txt = ""
    for fn in (lambda: root.clipboard_get(), lambda: root.selection_get(selection="CLIPBOARD")):
        try:
            txt = fn().strip()
            if txt: break
        except Exception: pass
    if txt:
        entry.insert(tk.END, short_str(txt, 120))
        entry.focus_set()
        entry.icursor(tk.END)
def kb_press(ch):
    global KB_LANG
    if ch == "DEL":
        cur = entry.get()
        if cur: entry.delete(len(cur) - 1, tk.END)
    elif ch == "SPC":
        entry.insert(tk.END, " ")
    elif ch == "LANG":
        KB_LANG = "EN" if KB_LANG == "RU" else "RU"
        update_vkb_labels()
    elif ch == "SYM":
        KB_LANG = "RU" if KB_LANG == "SYM" else "SYM"
        update_vkb_labels()
    elif ch == "GO":
        toggle_vkb(False)
        run_search()
    else:
        entry.insert(tk.END, ch)
    entry.focus_set()
    entry.icursor(tk.END)
def update_vkb_labels():
    rows = ROWS_SYM if KB_LANG == "SYM" else (ROWS_RU if KB_LANG == "RU" else ROWS_EN)
    idx = 0
    for r in rows:
        for ch in r:
            if idx < len(KB_BTNS):
                KB_BTNS[idx].config(text=ch, command=lambda c=ch: kb_press(c))
                idx += 1
    while idx < len(KB_BTNS):
        KB_BTNS[idx].config(text="", command=lambda: None)
        idx += 1
    btn_lang.config(text="EN" if KB_LANG == "RU" else "RU")
    btn_sym.config(text="АБВ" if KB_LANG == "SYM" else "?123")
def init_vkb():
    for r in ROWS_RU:
        rf = tk.Frame(vkb_box, bg=C_TOP); rf.pack(fill=tk.X, pady=1)
        for ch in r:
            b = tk.Button(rf, text=ch, command=lambda c=ch: kb_press(c), bg=C_SEC, fg=C_HEAD, font=("sans-serif", 11, "bold"), relief=tk.FLAT, padx=1, pady=5)
            b.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)
            KB_BTNS.append(b)
    bot = tk.Frame(vkb_box, bg=C_TOP); bot.pack(fill=tk.X, pady=(2, 0))
    global btn_lang, btn_sym
    btn_lang = tk.Button(bot, text="EN", command=lambda: kb_press("LANG"), bg="#475569", fg="#FFFFFF", font=("sans-serif", 9, "bold"), relief=tk.FLAT, padx=6, pady=5)
    btn_lang.pack(side=tk.LEFT, padx=1)
    btn_sym = tk.Button(bot, text="?123", command=lambda: kb_press("SYM"), bg="#334155", fg="#FBBF24", font=("sans-serif", 9, "bold"), relief=tk.FLAT, padx=6, pady=5)
    btn_sym.pack(side=tk.LEFT, padx=1)
    tk.Button(bot, text="ПРОБЕЛ", command=lambda: kb_press("SPC"), bg=C_SEC, fg=C_HEAD, font=("sans-serif", 9, "bold"), relief=tk.FLAT, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)
    tk.Button(bot, text="←", command=lambda: kb_press("DEL"), bg="#7F1D1D", fg="#FCA5A5", font=("sans-serif", 11, "bold"), relief=tk.FLAT, padx=8, pady=5).pack(side=tk.LEFT, padx=1)
    tk.Button(bot, text="ОК", command=lambda: kb_press("GO"), bg=C_BTN, fg="#FFFFFF", font=("sans-serif", 9, "bold"), relief=tk.FLAT, padx=8, pady=5).pack(side=tk.LEFT, padx=1)
def toggle_vkb(force=None):
    global KB_OPEN
    KB_OPEN = (not KB_OPEN) if force is None else force
    if KB_OPEN:
        vkb_box.pack(side=tk.BOTTOM, fill=tk.X, padx=4, pady=(2, 4), before=bot_bar)
    else:
        vkb_box.pack_forget()
    root.update_idletasks()
def show_kb(e=None):
    try:
        entry.focus_set()
        entry.icursor(tk.END)
    except Exception: pass
def paste_clip():
    do_paste()
def clear_and_kb():
    entry.delete(0, tk.END)
    show_kb()

def save_bookmark():
    u, t = CUR_PAGE.get("url", ""), CUR_PAGE.get("title", "")
    if u and not any(b.get("url") == u for b in BOOKMARKS):
        BOOKMARKS.insert(0, {"title": t, "url": u})
        box.insert("3.0", "[СОХРАНЕНО В ЗАКЛАДКИ]" + NL + NL, "badge")
def exit_app():
    try:
        root.quit()
        root.destroy()
    except Exception:
        os._exit(0)
def show_bookmarks():
    global IN_READER
    IN_READER = True
    box.delete("1.0", tk.END)
    box.insert(tk.END, "( <--- НАЗАД К ПОИСКУ )" + NL + NL, "back")
    box.insert(tk.END, "ИЗБРАННЫЕ ЗАКЛАДКИ" + NL + NL, "head")
    for idx, b in enumerate(BOOKMARKS, 1):
        u, t, tag = b.get("url", ""), b.get("title", ""), "bm_" + str(idx)
        box.insert(tk.END, str(idx) + ". " + t + NL, tag)
        box.insert(tk.END, short_str(u, 52) + NL + NL, "url")
        box.tag_config(tag, foreground=C_LINK, font=("sans-serif", 12, "bold"), underline=True)
        box.tag_bind(tag, "<Button-1>", lambda e, link=u, head=t: open_link(link, head))
def quick_pick(val):
    entry.delete(0, tk.END)
    entry.insert(0, val)
    run_search()
def refresh_chips():
    for w in chip_bar.winfo_children(): w.destroy()
    r1 = tk.Frame(chip_bar, bg=C_TOP); r1.pack(fill=tk.X, pady=(0, 3))
    r2 = tk.Frame(chip_bar, bg=C_TOP); r2.pack(fill=tk.X)
    for idx, item in enumerate(HISTORY[:4]):
        row = r1 if idx < 2 else r2
        lbl = item[:17] + (".." if len(item) > 17 else "")
        f_sz = 9 if len(lbl) > 15 else 10
        tk.Button(row, text=lbl, command=lambda v=item: quick_pick(v), bg=C_SEC, fg=C_LINK, font=("sans-serif", f_sz, "bold"), relief=tk.FLAT, pady=4).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
root = tk.Tk()
root.title("Тир " + VERSION)
root.configure(bg=C_TOP)
top_hdr = tk.Frame(root, bg=C_TOP); top_hdr.pack(fill=tk.X, padx=6, pady=4)
tk.Label(top_hdr, text="Браузер Тир " + VERSION, bg=C_TOP, fg=C_HEAD, font=("sans-serif", 11, "bold")).pack(side=tk.LEFT)
tk.Button(top_hdr, text="ВЫХОД", command=exit_app, bg="#7F1D1D", fg="#FCA5A5", font=("sans-serif", 9, "bold"), relief=tk.FLAT, padx=8).pack(side=tk.RIGHT, padx=(4, 0), ipady=2)
tk.Button(top_hdr, text="ЗАКЛАДКИ", command=show_bookmarks, bg=C_SEC, fg="#FBBF24", font=("sans-serif", 9, "bold"), relief=tk.FLAT, padx=8).pack(side=tk.RIGHT, ipady=2)

bar = tk.Frame(root, bg=C_TOP)
bar.pack(fill=tk.X, padx=6, pady=2)
entry = tk.Entry(bar, bg=C_BG, fg=C_HEAD, insertbackground="#FFFFFF", insertwidth=2, relief=tk.SOLID, bd=1, font=("sans-serif", 13))
entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
entry.bind("<Button-1>", show_kb)
entry.bind("<ButtonRelease-1>", show_kb)
btn_x = tk.Button(bar, text="X", command=clear_and_kb, bg=C_SEC, fg=C_HEAD, font=("sans-serif", 11, "bold"), relief=tk.FLAT, padx=8)
btn_x.pack(side=tk.LEFT, padx=(4, 0), ipady=2)

tk.Button(root, text="НАЙТИ", command=run_search, bg=C_BTN, fg="#FFFFFF", font=("sans-serif", 12, "bold"), relief=tk.FLAT).pack(fill=tk.X, padx=6, pady=(2, 6), ipady=3)

chip_bar = tk.Frame(root, bg=C_TOP); chip_bar.pack(fill=tk.X, padx=4, pady=(0, 4)); refresh_chips()
typo_slot = tk.Frame(root, bg=C_TOP)
typo_slot.pack(fill=tk.X)
lbl_typo = tk.Label(typo_slot, text="", bg=C_WARN_BG, fg=C_WARN_FG, pady=4, padx=6, anchor="w")
lbl_typo.bind("<ButtonRelease-1>", lambda e: run_search(force_raw=True))

bot_bar = tk.Frame(root, bg=C_TOP)
bot_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=4)
tk.Button(bot_bar, text="КЛАВИАТУРА", command=toggle_vkb, bg=C_SEC, fg=C_HEAD, font=("sans-serif", 10, "bold"), relief=tk.FLAT, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
tk.Button(bot_bar, text="ВСТАВИТЬ", command=do_paste, bg="#0F766E", fg="#FFFFFF", font=("sans-serif", 10, "bold"), relief=tk.FLAT, padx=12, pady=5).pack(side=tk.LEFT, padx=(3, 0))
vkb_box = tk.Frame(root, bg=C_TOP)
init_vkb()
box = tk.Text(root, wrap=tk.WORD, bg=C_BG, fg=C_TEXT, relief=tk.FLAT, padx=8, pady=6, exportselection=False)
box.pack(fill=tk.BOTH, expand=True)
box.tag_config("head", foreground=C_HEAD, font=("sans-serif", 11, "bold"), spacing1=8, spacing3=4)
box.tag_config("ans", background=C_ANS, foreground="#F1F5F9", font=("sans-serif", 12), lmargin1=8, lmargin2=8, rmargin=8, spacing1=6, spacing3=6)
box.tag_config("badge", foreground="#FBBF24", font=("sans-serif", 10, "bold"))
box.tag_config("url", foreground=C_URL, font=("sans-serif", 10))
box.tag_config("snip", foreground="#CBD5E1", font=("sans-serif", 11), spacing1=2)
box.tag_config("muted", foreground=C_MUTED, font=("sans-serif", 10))
box.tag_config("back", foreground=C_BACK, font=("sans-serif", 12, "bold"), underline=True)
box.tag_bind("back", "<ButtonRelease-1>", go_back)
box.bind("<ButtonPress-1>", on_press)
box.bind("<B1-Motion>", on_drag)
box.bind("<ButtonRelease-1>", lambda e: box.tag_remove("sel", "1.0", tk.END))
box.insert(tk.END, "Версия " + VERSION + " готова.", "head")
root.mainloop()
