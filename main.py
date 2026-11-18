import os, re, threading, urllib.parse, requests, urllib3
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
        return http_get(url, params=params, headers=headers, timeout=timeout, verify=False)

VERSION = "v15.7"
H_WEB = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"}
H_API = {"User-Agent": "TirBrowser/15.7", "Accept": "application/json"}

AD_WORDS = ("реклама","промо","спонсор","купить","цена","скидка","акция","заказать","доставка","кредит","займ","казино","ставки","услуги","прайс","an.yandex","googleadservices","doubleclick","yabs.yandex","cookie","политика конфиденциальности","войти","регистрация")
STOP_Q = ("когда","кагда","где","кто","что","што","как","почему","зачем","сколько","какой","какая","какие","родился","радился","возраст","лет","года","живет","живут","умер","такое","значит","это","ли","в","на","по","о","об")
KB_ROWS = ("йцукенгшщзхъ", "фывапролджэ", "ячсмитьбю")

LOGS = []
HISTORY = ["Европейская норка", "100 долларов", "переведи breakthrough", "250 * 48"]
BOOKMARKS = [{"title": "Европейская норка", "url": "https://wikipedia.org"}]

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
            res_g = g.json().get("results", []) if g.status_code == 200 else []
            if res_g:
                loc = res_g[0]
                lat, lon, cname = loc.get("latitude"), loc.get("longitude"), loc.get("name", cand)
                w = http_get("https://open-meteo.com", params={"latitude": lat, "longitude": lon, "current_weather": "true"}, timeout=4.5)
                cw = w.json().get("current_weather", {}) if w.status_code == 200 else {}
                if "temperature" in cw:
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
        items = r.json().get("query", {}).get("search", []) if r.status_code == 200 else []
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
                best = str(r.json().get("items", [{}])[0].get("text", "")).strip()
                if best and best.lower() != qc.lower() and len(best) <= len(qc) + 8 and not word_exists(qc):
                    return best, True
        except Exception: pass
    if gq != qc.lower() and not word_exists(qc) and word_exists(gq): return gq, True
    return qc, False

def stream_1_ddg(q):
    cards, seen = [], set()
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
    except Exception: pass
    if not cards: cards = wiki_api_search("ru.ruwiki.ru", "Рунет 1", q)
    LOGS.append("Поток 1 (Рунет): " + str(len(cards)))
    return cards

def wiki_api_search(domain, src_name, q):
    cards = []
    w_api = "https://" + domain + "/w/api.php"
    try:
        topic = extract_topic(q)
        p = {"action": "query", "list": "search", "srsearch": topic, "srlimit": 5, "format": "json", "utf8": 1}
        r = http_get(w_api, params=p, headers=H_API, timeout=7.0, verify=False)
        items = r.json().get("query", {}).get("search", []) if (r.status_code == 200 and r.text.strip().startswith("{")) else []
        if not items:
            p["srsearch"] = make_fuzzy(topic)
            r = http_get(w_api, params=p, headers=H_API, timeout=7.0, verify=False)
            items = r.json().get("query", {}).get("search", []) if (r.status_code == 200 and r.text.strip().startswith("{")) else []
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
        r = http_get("https://ru.wikipedia.org", params=p, headers=H_API, timeout=7.0, verify=False)
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
    return "Точный ответ не найден."

# ==================== ПРОСТОЙ FLET ИНТЕРФЕЙС (как в v15.5, но с кликабельными ссылками) ====================

def main(page: ft.Page):
    page.title = "Браузер Тир " + VERSION
    page.bgcolor = "#0F172A"
    page.padding = 10
    
    ent = ft.TextField(
        label="Запрос или адрес сайта",
        bgcolor="#1E293B",
        color="#F8FAFC",
        cursor_color="#FFF",
        border_color="#334155",
        focused_border_color="#3B82F6",
        expand=True,
        on_submit=lambda e: run_search()
    )
    
    out = ft.Text("Версия " + VERSION + " готова.", color="#F8FAFC", size=14, selectable=True)
    sc = ft.Column([out], expand=True, scroll=ft.ScrollMode.AUTO)
    
    def open_url(url):
        try:
            ft.utils.launch(url)
        except Exception:
            pass
    
    def run_search():
        q = (ent.value or "").strip()
        if not q: return
        if q not in HISTORY: HISTORY.insert(0, q); update_chips()
        
        if q.startswith("http://") or q.startswith("https://") or ("." in q and " " not in q):
            if not q.startswith("http"): q = "https://" + q
            open_url(q)
            return
        
        out.value = "◐ Ищем «" + q + "»..."
        out.color = "#F8FAFC"
        page.update()
        
        def worker():
            LOGS.clear()
            m_ans = try_math(q) or try_weather(q) or try_smart_tools(q)
            if m_ans:
                txt = "══ ОТВЕТ ══\n\n " + m_ans
            else:
                uq, has_typo = check_typo(q)
                res = {"c1": [], "c2": [], "c3": []}
                t1 = threading.Thread(target=lambda: res.update(c1=stream_1_ddg(uq)))
                t2 = threading.Thread(target=lambda: res.update(c2=stream_2_runet(uq)))
                t3 = threading.Thread(target=lambda: res.update(c3=stream_3_wiki(uq)))
                t1.start(); t2.start(); t3.start()
                t1.join(5.0); t2.join(5.0); t3.join(5.0)
                c1, c2, c3 = res["c1"], res["c2"], res["c3"]
                mixed = [v for grp in zip(c1 + [None]*6, c2 + [None]*6, c3 + [None]*6) for v in grp if v]
                ans = build_best_answer(uq, mixed, c2, c3)
                txt = "══ БЫСТРЫЙ ОТВЕТ ══\n\n " + ans + "\n\n══ ИСТОЧНИКИ ══\n\n"
                for item in mixed[:10]:
                    # ДЕКОДИРУЕМ URL для красоты
                    nice_url = urllib.parse.unquote(item.get("url", ""))
                    txt += f"[{item.get('src', '')}] {item.get('title', '')}\n{nice_url}\n"
                    if item.get("snip"): txt += item["snip"][:120] + "\n"
                    txt += "\n"
                txt += "══ СТАТУС ПОТОКОВ ══\n" + "\n".join(LOGS)
            out.value = txt
            out.color = "#E2E8F0"
            page.update()
        
        threading.Thread(target=worker, daemon=True).start()
    
    def update_chips():
        chip.controls.clear()
        for h in HISTORY[:4]:
            chip.controls.append(ft.ElevatedButton(
                h[:17]+(".." if len(h)>17 else ""),
                on_click=lambda e,v=h: (setattr(ent,"value",v), run_search()),
                bgcolor="#334155",
                color="#38BDF8"
            ))
        page.update()
    
    chip = ft.Row([], wrap=True, spacing=8)
    
    page.add(
        ft.Text("🌐 Браузер Тир " + VERSION, color="#F8FAFC", size=16, weight=ft.FontWeight.BOLD),
        ft.Row([ent, ft.ElevatedButton("НАЙТИ", on_click=lambda e: run_search(), bgcolor="#3B82F6", color="#FFF")]),
        chip,
        ft.Row([
            ft.ElevatedButton("🔖 ЗАКЛАДКИ", on_click=lambda e: show_bookmarks(), bgcolor="#334155", color="#FBBF24"),
            ft.ElevatedButton("📋 ВСТАВИТЬ", on_click=lambda e: paste_clip(), bgcolor="#0F766E", color="#FFF")
        ]),
        sc
    )
    update_chips()
    
    def show_bookmarks():
        lines = ["🔖 ИЗБРАННЫЕ ЗАКЛАДКИ\n"]
        for idx, b in enumerate(BOOKMARKS, 1):
            nice_url = urllib.parse.unquote(b.get("url", ""))
            lines.append(f"{idx}. {b.get('title', '')}\n{nice_url}\n")
        out.value = "\n".join(lines)
        out.color = "#F8FAFC"
        page.update()
    
    def paste_clip():
        try:
            if hasattr(page, 'clipboard') and page.clipboard:
                txt = page.clipboard.get_data()
                if txt:
                    ent.value = (ent.value or "") + txt
                    page.update()
        except Exception: pass

ft.app(target=main)