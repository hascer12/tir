import re, threading, urllib.parse, requests, urllib3, os
import flet as ft

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

SESSION = requests.Session()
SESSION.trust_env = False

def http_get(url, params=None, headers=None, timeout=7.5):
    try:
        return SESSION.get(url, params=params, headers=headers, timeout=timeout, verify=False)
    except Exception:
        return None

VERSION = "v14.6"
H_WEB = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36", "Accept-Language": "ru-RU,ru;q=0.9"}
H_API = {"User-Agent": "TirBrowser/14.6", "Accept": "application/json"}
AD = ("реклама","промо","спонсор","купить","цена","скидка","акция","заказать","казино","ставки","войти","регистрация")
STOP = ("когда","где","кто","что","как","почему","зачем","сколько","какой","это","ли","в","на","по","о")
KB = ("йцукенгшщзхъ","фывапролджэ","ячсмитьбю")
HIST = ["Европейская норка","100 долларов","переведи breakthrough","250 * 48"]
BM = [{"t":"Европейская норка","u":"https://ru.wikipedia.org"}]

def topic(q):
    w = [x for x in re.sub(r"[^\w\s-]"," ",q.lower()).split() if x not in STOP and len(x)>1]
    return " ".join(w) if w else q

def glove(w):
    if len(w)<3: return w
    r = [w[0]]
    for c in w[1:]:
        p = r[-1]
        if not any(p in k and c in k and abs(k.find(p)-k.find(c))==1 for k in KB): r.append(c)
    return "".join(r) if len(r)>=2 else w

def math(q):
    e = q.lower().replace("сколько будет","").replace("посчитай","").replace("=","").replace(",",".").replace("х","*").replace("x","*").replace(":","/").strip()
    if e and re.fullmatch(r"[0-9+\-*/().\s]+",e) and any(o in e for o in "+-*/"):
        try:
            r = eval(e,{"__builtins__":None},{})
            return "Ответ: "+str(int(r) if isinstance(r,float) and r.is_integer() else r)
        except Exception: pass
    return ""

def weather(q):
    ql = q.lower().strip()
    if not any(w in ql for w in ("погод","температур","градус","прогноз")): return ""
    ws = [glove(w) for w in re.sub(r"[^\w\s-]"," ",ql).split()]
    st = ("какая","какой","сегодня","завтра","сейчас","погода","в","на","улице","прогноз","температура","градусов")
    city = " ".join(w for w in ws if w not in st and len(w)>2).strip()
    for c in ([city,"Москва"] if city else ["Москва"]):
        try:
            g = http_get("https://api.open-meteo.com/v1/geocoding",{"name":c,"count":1,"language":"ru"})
            if not g or g.status_code!=200: continue
            rs = g.json().get("results",[])
            if not rs: continue
            l = rs[0]
            w = http_get("https://api.open-meteo.com/v1/forecast",{"latitude":l["latitude"],"longitude":l["longitude"],"current_weather":"true"})
            if not w or w.status_code!=200: continue
            cw = w.json().get("current_weather",{})
            if "temperature" not in cw: continue
            code = cw.get("weathercode",0)
            sky = "Ясно" if code==0 else ("Переменная облачность" if code in(1,2,3) else ("Туман" if code in(45,48) else ("Дождь" if code<70 else "Снег")))
            s = "+" if float(cw["temperature"])>0 else ""
            return f"Погода ({l.get('name',c)}): {s}{cw['temperature']}°C, {sky}, ветер {cw['windspeed']} км/ч"
        except Exception: pass
    return ""

def tools(q):
    ql = q.lower().strip()
    if re.search(r"(дол|usd|евр|eur|юан|cny)",ql) and any(w in ql for w in ("курс","валют","рубл","скольк")):
        m = re.search(r"(\d+(?:[.,]\d+)?)",ql)
        amt = float(m.group(1).replace(",",".")) if m else 1.0
        cur = "EUR" if re.search(r"(евр|eur)",ql) else ("CNY" if re.search(r"(юан|cny)",ql) else "USD")
        try:
            r = http_get("https://open.er-api.com/v6/latest/"+cur)
            if r and r.status_code==200:
                v = r.json().get("rates",{}).get("RUB",0)
                if v: return f"{amt} {cur} = {round(amt*v,2)} RUB (курс {round(v,2)})"
        except Exception: pass
    if ql.startswith(("переведи ","как будет ","что значит ")) or re.fullmatch(r"[a-zA-Z\s'.,!?-]{2,60}",q.strip()):
        txt = re.sub(r"^(переведи|как будет|что значит)\s+","",q.strip(),flags=re.I).strip()
        if txt:
            ru = bool(re.search(r"[а-яА-ЯёЁ]",txt))
            try:
                r = http_get("https://translate.googleapis.com/translate_a/single",{"client":"gtx","sl":"ru" if ru else "en","tl":"en" if ru else "ru","dt":"t","q":txt})
                if r and r.status_code==200 and r.text.strip().startswith("["):
                    tr = "".join(i[0] for i in r.json()[0] if i and i[0])
                    if tr and tr.lower()!=txt.lower(): return f"Перевод: {tr}"
            except Exception: pass
    return ""

def word_exists(w):
    try:
        p = {"action":"query","list":"search","srsearch":w,"srlimit":1,"format":"json"}
        r = http_get("https://ru.wikipedia.org/w/api.php",p)
        items = r.json().get("query",{}).get("search",[]) if r and r.status_code==200 else []
        return any(w.lower() in it.get("title","").lower() for it in items)
    except Exception: return False

def check_typo(q):
    if re.search(r"[a-zA-Z]",q): return " ".join(q.split()), False
    qc = " ".join(q.split())
    if len(qc.split())==1 and word_exists(qc): return qc, False
    gq = " ".join(glove(w) for w in qc.lower().split())
    for cand in ([qc] if gq==qc.lower() else [qc,gq]):
        try:
            r = http_get("https://mail.ru",{"q":cand})
            if r and r.status_code==200 and r.text.strip().startswith("{"):
                best = str(r.json().get("items",[{}])[0].get("text","")).strip()
                if best and best.lower()!=qc.lower() and len(best)<=len(qc)+8 and not word_exists(qc):
                    return best, True
        except Exception: pass
    if gq!=qc.lower() and not word_exists(qc) and word_exists(gq): return gq, True
    return qc, False

def wiki(dom,src,q):
    cards = []
    try:
        p = {"action":"query","list":"search","srsearch":topic(q),"srlimit":5,"format":"json","utf8":1}
        r = http_get(f"https://{dom}/w/api.php",p)
        items = r.json().get("query",{}).get("search",[]) if r and r.status_code==200 else []
        if not items:
            p["srsearch"] = " ".join((w+"~" if len(w)>=3 else w) for w in re.sub(r"[^\w\s-]"," ",topic(q)).split() if len(w)>1)
            r = http_get(f"https://{dom}/w/api.php",p)
            items = r.json().get("query",{}).get("search",[]) if r and r.status_code==200 else []
        for w in items:
            t = w.get("title","")
            sn = re.sub(r"<[^>]+>","",w.get("snippet",""))
            if t and not any(a in (t+sn).lower() for a in AD):
                cards.append({"s":src,"t":t,"u":f"https://{dom}/wiki/"+urllib.parse.quote(t),"sn":sn})
    except Exception: pass
    return cards

def yandex_search(q):
    """Яндекс поиск через HTML"""
    cards = []
    try:
        r = http_get("https://yandex.ru/search",{"text":q,"lr":"213"},H_WEB)
        if not r or r.status_code!=200 or not BeautifulSoup: return cards
        soup = BeautifulSoup(r.text,"html.parser")
        for a in soup.find_all("a",href=True):
            href = a.get("href","")
            if not href.startswith("http"): continue
            bad = ["yandex.ru/search","yandex.ru/turbo","yabs.yandex","an.yandex","googleadservices","doubleclick"]
            if any(b in href for b in bad): continue
            t = a.get_text(" ",strip=True)
            if len(t)<15 or len(t)>200: continue
            if any(ad in (t+href).lower() for ad in AD): continue
            cards.append({"s":"Яндекс","t":t,"u":href,"sn":""})
            if len(cards)>=6: break
    except Exception: pass
    return cards

def ramble_search(q):
    """Rambler поиск"""
    cards = []
    try:
        r = http_get("https://nova.rambler.ru/search",{"query":q},H_WEB)
        if not r or r.status_code!=200 or not BeautifulSoup: return cards
        soup = BeautifulSoup(r.text,"html.parser")
        for a in soup.find_all("a",href=True):
            href = a.get("href","")
            if not href.startswith("http"): continue
            if "rambler.ru" in href and "/search" in href: continue
            t = a.get_text(" ",strip=True)
            if len(t)<15 or len(t)>200: continue
            if any(ad in (t+href).lower() for ad in AD): continue
            cards.append({"s":"Rambler","t":t,"u":href,"sn":""})
            if len(cards)>=6: break
    except Exception: pass
    return cards

def read_wiki_fast(title, limit=3500):
    if not title: return ""
    try:
        p = {"action":"query","prop":"extracts","explaintext":"1","exintro":"1" if limit<800 else "0","titles":title,"format":"json"}
        r = http_get("https://ru.wikipedia.org/w/api.php",p)
        if not r or r.status_code!=200: return ""
        pages = r.json().get("query",{}).get("pages",{})
        for pid in pages:
            ext = pages[pid].get("extract","")
            if ext and len(ext.strip())>20: return ext.strip()[:limit]
    except Exception: pass
    return ""

def clean_ans_text(t):
    t = re.sub(r"\[[^\]]+\]|◆|\?\?|Корень:[^.]+\.|Существительное\.", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def smart_fact_answer(q, text_pool):
    if not text_pool: return ""
    need_num = any(w in q.lower() for w in ("сколько","возраст","лет","года","вес","рост","длина","скорость","температура","когда","год"))
    tws = [w[:5] for w in topic(q).split() if len(w)>2]
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text_pool) if 18<=len(s)<=280]
    if not need_num and sents:
        for sc in sents:
            if any(tw in sc.lower() for tw in tws) and (" — " in sc or " - " in sc or " это " in sc.lower()): return sc
        return sents[0] if sents else ""
    scored = []
    for sc in sents:
        score = sum(3 for tw in tws if tw in sc.lower())
        if need_num and re.search(r"\d", sc):
            score += 9 if re.search(r"\b(лет|год|года|году|месяц|дней|дня|час|мин|сек|кг|г|тонн|км|м|см|мм|%|тыс|млн|млрд)\b", sc.lower()) else 5
        if score>=5: scored.append((score, sc))
    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        return " ".join(dict.fromkeys(s for _, s in scored[:2]))
    return sents[0] if sents else ""

def build_best_answer(uq, mixed, c2, c3):
    wiki_text = ""
    for item in (c3 or [])[:3]:
        cand = read_wiki_fast(item.get("title",""), 900)
        if cand and "уменьшительная форма" not in cand.lower() and "топоним" not in cand.lower() and len(cand)>80:
            wiki_text = clean_ans_text(cand)
            break
    snips = [clean_ans_text(c.get("snip","")) for c in mixed if len(c.get("snip","").strip())>30 and "Существительное" not in c.get("snip","")]
    fact = smart_fact_answer(uq, (wiki_text + " " + " ".join(snips)).strip())
    if fact and len(fact)>35: return clean_ans_text(fact)
    if wiki_text:
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", wiki_text) if len(s.strip())>25]
        return " ".join(sents[:2]) if sents else wiki_text[:350]
    if snips: return " ".join(snips[:2])
    return "Точный ответ не найден. Откройте любую ссылку ниже."

def answer(q):
    res = {"c1":[],"c2":[],"c3":[],"c4":[],"c5":[]}
    def w1(): res["c1"] = wiki("ru.wikipedia.org","Вики",q)
    def w2(): res["c2"] = wiki("ru.wiktionary.org","Словарь",q)
    def w3(): res["c3"] = wiki("ru.ruwiki.ru","Рунет",q)
    def w4(): res["c4"] = yandex_search(q)
    def w5(): res["c5"] = ramble_search(q)
    ts = [threading.Thread(target=f) for f in (w1,w2,w3,w4,w5)]
    for t in ts: t.start()
    for t in ts: t.join(7)
    allc = res["c1"]+res["c2"]+res["c3"]+res["c4"]+res["c5"]
    ans = build_best_answer(q, allc, res["c2"], res["c3"])
    lines = ["══ БЫСТРЫЙ ОТВЕТ ══","",(" "+ans) if ans else "Точный ответ не найден.","","══ ИСТОЧНИКИ ══",""]
    for c in allc[:10]:
        lines.append(f"[{c['s']}] {c['t']}")
        lines.append(c["u"][:52])
        if c.get("sn"): lines.append(c["sn"][:120])
        lines.append("")
    if not allc: lines.append("Ничего не найдено.")
    return "\n".join(lines)

# ==================== FLET ИНТЕРФЕЙС ====================

def main(page: ft.Page):
    page.title = "Браузер Тир "+VERSION
    page.bgcolor = "#0F172A"
    page.padding = 0
    
    ent = ft.TextField(
        label="Запрос или адрес сайта",
        bgcolor="#1E293B",
        color="#F8FAFC",
        cursor_color="#FFF",
        border_color="#334155",
        focused_border_color="#3B82F6",
        expand=True,
        on_submit=lambda e: do_search()
    )
    
    btn_x = ft.IconButton(
        icon=ft.Icons.CLOSE,
        icon_color="#F8FAFC",
        icon_size=20,
        bgcolor="#334155",
        on_click=lambda e: (setattr(ent,"value",""), ent.focus())
    )
    
    btn_find = ft.ElevatedButton(
        "НАЙТИ",
        on_click=lambda e: do_search(),
        bgcolor="#3B82F6",
        color="#FFF",
        height=50
    )
    
    btn_back = ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color="#F8FAFC", icon_size=24, bgcolor="#334155", visible=False)
    btn_fwd = ft.IconButton(icon=ft.Icons.ARROW_FORWARD, icon_color="#F8FAFC", icon_size=24, bgcolor="#334155", visible=False)
    btn_reload = ft.IconButton(icon=ft.Icons.REFRESH, icon_color="#F8FAFC", icon_size=24, bgcolor="#334155", visible=False)
    btn_yt = ft.IconButton(icon=ft.Icons.PLAY_CIRCLE, icon_color="#FF0000", icon_size=24, bgcolor="#334155", visible=False, tooltip="Открыть в YouTube")
    
    header = ft.Container(
        content=ft.Row([
            ft.Text("Браузер Тир "+VERSION, color="#F8FAFC", size=14, weight=ft.FontWeight.BOLD),
            ft.ElevatedButton("ЗАКЛАДКИ", on_click=lambda e: show_bookmarks(), bgcolor="#334155", color="#FBBF24"),
            ft.ElevatedButton("ВЫХОД", on_click=lambda e: None, bgcolor="#7F1D1D", color="#FCA5A5")
        ], spacing=8),
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        bgcolor="#1E293B"
    )
    
    search_row = ft.Container(
        content=ft.Row([ent, btn_x, btn_find], spacing=8),
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        bgcolor="#1E293B"
    )
    
    nav_row = ft.Container(
        content=ft.Row([btn_back, btn_fwd, btn_reload, btn_yt], spacing=8),
        padding=ft.padding.symmetric(horizontal=12, vertical=4),
        bgcolor="#1E293B",
        visible=False
    )
    
    out = ft.Text("Версия "+VERSION+" готова.", color="#F8FAFC", size=14, selectable=True)
    text_view = ft.Column([out], expand=True, scroll=ft.ScrollMode.AUTO)
    text_container = ft.Container(content=text_view, expand=True, padding=ft.padding.all(12), bgcolor="#0F172A")
    
    web_view = ft.WebView(expand=True, visible=False)
    
    chip_row = ft.Row([], wrap=True, spacing=8)
    chip_container = ft.Container(content=chip_row, padding=ft.padding.symmetric(horizontal=12, vertical=6), bgcolor="#1E293B")
    
    bottom_bar = ft.Container(
        content=ft.Row([
            ft.ElevatedButton("КЛАВИАТУРА", on_click=lambda e: ent.focus(), bgcolor="#334155", color="#F8FAFC", expand=True),
            ft.ElevatedButton("ВСТАВИТЬ", on_click=lambda e: paste_clip(), bgcolor="#0F766E", color="#FFF", expand=True)
        ], spacing=8),
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        bgcolor="#1E293B"
    )
    
    page.add(header, search_row, nav_row, text_container, web_view, chip_container, bottom_bar)
    
    page.current_url = ""
    page.web_history = []
    page.web_pos = -1
    
    def update_chips():
        chip_row.controls.clear()
        for h in HIST[:4]:
            chip_row.controls.append(ft.ElevatedButton(
                h[:17]+(".." if len(h)>17 else ""),
                on_click=lambda e,v=h: (setattr(ent,"value",v), do_search()),
                bgcolor="#334155",
                color="#38BDF8"
            ))
        page.update()
    
    update_chips()
    
    def paste_clip():
        try:
            if hasattr(page, 'clipboard') and page.clipboard:
                txt = page.clipboard.get_data()
                if txt:
                    ent.value = (ent.value or "") + txt
                    page.update()
        except Exception: pass
    
    def show_bookmarks():
        lines = ["ИЗБРАННЫЕ ЗАКЛАДКИ",""]
        for idx, b in enumerate(BM, 1):
            lines.append(f"{idx}. {b['t']}")
            lines.append(b['u'])
            lines.append("")
        out.value = "\n".join(lines)
        out.color = "#F8FAFC"
        text_container.visible = True
        web_view.visible = False
        nav_row.visible = False
        page.update()
    
    def open_webview(url):
        page.current_url = url
        page.web_history.append(url)
        page.web_pos = len(page.web_history)-1
        text_container.visible = False
        web_view.visible = True
        nav_row.visible = True
        is_yt = "youtube.com" in url or "youtu.be" in url
        btn_yt.visible = is_yt
        btn_back.visible = True
        btn_fwd.visible = True
        btn_reload.visible = True
        web_view.url = url
        page.update()
    
    def do_search():
        q = (ent.value or "").strip()
        if not q: return
        if q not in HIST: HIST.insert(0,q); update_chips()
        
        if q.startswith("http://") or q.startswith("https://") or ("." in q and " " not in q):
            if not q.startswith("http"): q = "https://" + q
            open_webview(q)
            return
        
        out.value = "◐ Ищем «"+q+"»..."
        out.color = "#F8FAFC"
        text_container.visible = True
        web_view.visible = False
        nav_row.visible = False
        page.update()
        
        def worker():
            r = math(q) or weather(q) or tools(q)
            if r: txt = "══ ОТВЕТ ══\n\n "+r
            else: txt = answer(q)
            out.value = txt
            out.color = "#E2E8F0"
            page.update()
        
        threading.Thread(target=worker, daemon=True).start()

ft.app(target=main)