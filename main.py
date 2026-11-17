import re, threading, urllib.parse, requests, urllib3
import flet as ft

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

S = requests.Session()
S.trust_env = False
def get(url, params=None, headers=None, t=7.5):
    try: return S.get(url, params=params, headers=headers, timeout=t, verify=False)
    except Exception: return None

VER = "v14.5"
UA = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}
API = {"User-Agent":"TirBrowser/14.5","Accept":"application/json"}
AD = ("реклама","промо","спонсор","купить","цена","скидка","акция","заказать","казино","ставки","войти","регистрация")
STOP = ("когда","где","кто","что","как","почему","зачем","сколько","какой","это","ли","в","на","по","о")
KB = ("йцукенгшщзхъ","фывапролджэ","ячсмитьбю")
HIST = ["Европейская норка","100 долларов","переведи breakthrough","250 * 48"]
BM = [{"t":"Европейская норка","u":"https://ru.ruwiki.ru"}]

def topic(q):
    w=[x for x in re.sub(r"[^\w\s-]"," ",q.lower()).split() if x not in STOP and len(x)>1]
    return " ".join(w) if w else q

def glove(w):
    if len(w)<3: return w
    r=[w[0]]
    for c in w[1:]:
        p=r[-1]
        if not any(p in k and c in k and abs(k.find(p)-k.find(c))==1 for k in KB): r.append(c)
    return "".join(r) if len(r)>=2 else w

def math(q):
    e=q.lower().replace("сколько будет","").replace("посчитай","").replace("=","").replace(",",".").replace("х","*").replace("x","*").replace(":","/").strip()
    if e and re.fullmatch(r"[0-9+\-*/().\s]+",e) and any(o in e for o in "+-*/"):
        try:
            r=eval(e,{"__builtins__":None},{})
            return "Ответ: "+str(int(r) if isinstance(r,float) and r.is_integer() else r)
        except Exception: pass
    return ""

def weather(q):
    ql=q.lower().strip()
    if not any(w in ql for w in ("погод","температур","градус","прогноз")): return ""
    ws=[glove(w) for w in re.sub(r"[^\w\s-]"," ",ql).split()]
    st=("какая","какой","сегодня","завтра","сейчас","погода","в","на","улице","прогноз","температура","градусов")
    city=" ".join(w for w in ws if w not in st and len(w)>2).strip()
    for c in ([city,"Москва"] if city else ["Москва"]):
        try:
            g=get("https://api.open-meteo.com/v1/geocoding",{"name":c,"count":1,"language":"ru"},t=4.5)
            if not g or g.status_code!=200: continue
            rs=g.json().get("results",[])
            if not rs: continue
            l=rs[0]
            w=get("https://api.open-meteo.com/v1/forecast",{"latitude":l["latitude"],"longitude":l["longitude"],"current_weather":"true"},t=4.5)
            if not w or w.status_code!=200: continue
            cw=w.json().get("current_weather",{})
            if "temperature" not in cw: continue
            code=cw.get("weathercode",0)
            sky="Ясно" if code==0 else ("Переменная облачность" if code in(1,2,3) else ("Туман" if code in(45,48) else ("Дождь" if code<70 else "Снег")))
            s="+" if float(cw["temperature"])>0 else ""
            return f"Погода ({l.get('name',c)}): {s}{cw['temperature']}°C, {sky}, ветер {cw['windspeed']} км/ч"
        except Exception: pass
    return ""

def tools(q):
    ql=q.lower().strip()
    if re.search(r"(дол|usd|евр|eur|юан|cny)",ql) and any(w in ql for w in ("курс","валют","рубл","скольк")):
        m=re.search(r"(\d+(?:[.,]\d+)?)",ql)
        amt=float(m.group(1).replace(",",".")) if m else 1.0
        cur="EUR" if re.search(r"(евр|eur)",ql) else ("CNY" if re.search(r"(юан|cny)",ql) else "USD")
        try:
            r=get("https://open.er-api.com/v6/latest/"+cur,t=5.0)
            if r and r.status_code==200:
                v=r.json().get("rates",{}).get("RUB",0)
                if v: return f"{amt} {cur} = {round(amt*v,2)} RUB (курс {round(v,2)})"
        except Exception: pass
    if ql.startswith(("переведи ","как будет ","что значит ")) or re.fullmatch(r"[a-zA-Z\s'.,!?-]{2,60}",q.strip()):
        txt=re.sub(r"^(переведи|как будет|что значит)\s+","",q.strip(),flags=re.I).strip()
        if txt:
            ru=bool(re.search(r"[а-яА-ЯёЁ]",txt))
            try:
                r=get("https://translate.googleapis.com/translate_a/single",{"client":"gtx","sl":"ru" if ru else "en","tl":"en" if ru else "ru","dt":"t","q":txt},UA,3.0)
                if r and r.status_code==200 and r.text.strip().startswith("["):
                    tr="".join(i[0] for i in r.json()[0] if i and i[0])
                    if tr and tr.lower()!=txt.lower(): return f"Перевод: {tr}"
            except Exception: pass
    return ""

def wiki(dom,src,q):
    cards=[]
    try:
        p={"action":"query","list":"search","srsearch":topic(q),"srlimit":5,"format":"json","utf8":1}
        r=get(f"https://{dom}/w/api.php",p,API)
        items=r.json().get("query",{}).get("search",[]) if r and r.status_code==200 else []
        for w in items:
            t=w.get("title","")
            sn=re.sub(r"<[^>]+>","",w.get("snippet",""))
            if t and not any(a in (t+sn).lower() for a in AD):
                cards.append({"s":src,"t":t,"u":f"https://{dom}/wiki/"+urllib.parse.quote(t),"sn":sn})
    except Exception: pass
    return cards

def answer(q):
    res={"c1":[],"c2":[],"c3":[]}
    def w1(): res["c1"]=wiki("ru.wikipedia.org","Вики",q)
    def w2(): res["c2"]=wiki("ru.wiktionary.org","Словарь",q)
    def w3(): res["c3"]=wiki("ru.ruwiki.ru","Рунет",q)
    ts=[threading.Thread(target=f) for f in (w1,w2,w3)]
    for t in ts: t.start()
    for t in ts: t.join(6)
    allc=res["c1"]+res["c2"]+res["c3"]
    tws=[w[:5] for w in topic(q).split() if len(w)>2]
    best=""
    for c in res["c1"][:3]:
        try:
            r=get("https://ru.wikipedia.org/w/api.php",{"action":"query","prop":"extracts","explaintext":"1","exintro":"1","titles":c["t"],"format":"json"},API)
            if r and r.status_code==200:
                pg=r.json().get("query",{}).get("pages",{})
                for pid in pg:
                    ext=pg[pid].get("extract","")
                    if ext and len(ext)>80:
                        sents=[s.strip() for s in re.split(r"(?<=[.!?])\s+",ext) if 18<=len(s)<=280]
                        for s in sents:
                            if any(tw in s.lower() for tw in tws): best=s; break
                        if not best and sents: best=sents[0]
                        if best: break
        except Exception: pass
        if best: break
    lines=["══ БЫСТРЫЙ ОТВЕТ ══","",(" "+best) if best else "Точный ответ не найден.","","══ ИСТОЧНИКИ ══",""]
    for c in allc[:8]:
        lines.append(f"[{c['s']}] {c['t']}")
        lines.append(c["u"][:52])
        if c.get("sn"): lines.append(c["sn"][:120])
        lines.append("")
    if not allc: lines.append("Ничего не найдено.")
    return "\n".join(lines)

def main(page: ft.Page):
    page.title="Браузер Тир "+VER
    page.bgcolor="#0F172A"
    page.padding=10
    ent=ft.TextField(label="Запрос или адрес",bgcolor="#1E293B",color="#F8FAFC",cursor_color="#FFF",border_color="#334155",focused_border_color="#3B82F6",expand=True,on_submit=lambda e:do(None))
    out=ft.Text("Версия "+VER+" готова.",color="#F8FAFC",size=14,selectable=True)
    sc=ft.Column([out],expand=True,scroll=ft.ScrollMode.AUTO)
    def do(e):
        q=(ent.value or "").strip()
        if not q: return
        if q not in HIST: HIST.insert(0,q); chips()
        out.value="◐ Ищем «"+q+"»..."; out.color="#F8FAFC"; page.update()
        def w():
            r=math(q) or weather(q) or tools(q)
            if r: txt="══ ОТВЕТ ══\n\n "+r
            else: txt=answer(q)
            out.value=txt; out.color="#E2E8F0"; page.update()
        threading.Thread(target=w,daemon=True).start()
    def chips():
        for c in chip.controls[:]: c.controls=[]
        for h in HIST[:4]:
            chip.controls.append(ft.ElevatedButton(h[:17]+(".." if len(h)>17 else ""),on_click=lambda e,v=h:(ent.__setattr__("value",v),do(None)),bgcolor="#334155",color="#38BDF8",style=ft.ButtonStyle(padding=5)))
        page.update()
    chip=ft.Row([],wrap=True)
    page.add(
        ft.Row([ft.Text("Браузер Тир "+VER,color="#F8FAFC",size=14,weight=ft.FontWeight.BOLD),ft.ElevatedButton("ЗАКЛАДКИ",on_click=lambda e:(out.value="\n".join(f"{i+1}. {b['t']} — {b['u']}" for i,b in enumerate(BM))),bgcolor="#334155",color="#FBBF24"),ft.ElevatedButton("ВЫХОД",on_click=lambda e:page.window_close(),bgcolor="#7F1D1D",color="#FCA5A5")]),
        ft.Row([ent,ft.ElevatedButton("НАЙТИ",on_click=do,bgcolor="#3B82F6",color="#FFF",style=ft.ButtonStyle(text_style=ft.TextStyle(size=14,weight=ft.FontWeight.BOLD)))]),
        chip, sc
    )
    chips()

ft.app(target=main)