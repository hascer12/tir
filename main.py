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

# ============ ПОИСКОВЫЕ ИСТОЧНИКИ ============

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
    """Яндекс через HTML-парсинг (как Яндекс.Браузер)"""
    cards = []
    try:
        r = http_get("https://yandex.ru/search",{"text":q,"lr":"213"},H_WEB)
        if not r or r.status_code!=200 or not BeautifulSoup: return cards
        soup = BeautifulSoup(r.text,"html.parser")
        for item in soup.select(".serp-item, .OrganicTitle, .serp-item__title"):
            a = item.find("a", href=True) if item.name!="a" else item
            if not a: continue
            href = a.get("href","")
            if href.startswith("/"): href = "https://yandex.ru"+href
            if not href.startswith("http"): continue
            if any(b in href for b in ("yandex.ru/search","yandex.