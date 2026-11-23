"""LINE OA bot: stock quotes, market overview and news summaries (Thai + US markets).

Claude picks tools (get_quote / market_overview / get_news), the bot sends
Flex price cards plus a short Thai answer. Information only, not investment advice.

  python bot.py            # run webhook server on :8000  (POST /callback)
  python bot.py chat       # chat in the terminal, no LINE needed
  python bot.py selftest   # offline checks, no network / API calls
  python bot.py richmenu   # upload rich_menu.jpg as the default rich menu
  python bot.py webhook <tunnel-url>   # point LINE webhook at the tunnel and test it
"""
import base64, hashlib, hmac, json, os, sys, threading, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).parent
from dotenv import load_dotenv
load_dotenv(HERE / ".env")

MODEL = os.getenv("MODEL", "claude-opus-5-5")
LINE_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
BKK = timezone(timedelta(hours=7))
UA = {"User-Agent": "Mozilla/5.0"}
DISCLAIMER = "ข้อมูลเพื่อประกอบการตัดสินใจ ไม่ใช่คำแนะนำการลงทุน"

# ---------- market data ----------
def http_get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15).read()

def quote(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=5d&interval=1d"
    res = json.loads(http_get(url))["chart"]["result"][0]
    m = res["meta"]
    closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
    price = m["regularMarketPrice"]
    prev = closes[-2] if len(closes) >= 2 else m.get("chartPreviousClose", price)
    return {"symbol": symbol, "name": m.get("longName") or m.get("shortName") or symbol,
            "price": round(price, 2), "change": round(price - prev, 2) + 0.0,  # +0.0 turns -0.0 into 0.0
            "change_pct": round((price - prev) / prev * 100, 2) + 0.0 if prev else 0.0,
            "day_high": m.get("regularMarketDayHigh"), "day_low": m.get("regularMarketDayLow"),
            "currency": m.get("currency", ""),
            "time": datetime.fromtimestamp(m["regularMarketTime"], BKK).strftime("%d/%m %H:%M")}

OVERVIEW = [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq"), ("^DJI", "Dow Jones"), ("^RUT", "Russell 2000"),
            ("^VIX", "VIX"), ("^TNX", "US 10Y (%)")]

def news(query, lang):
    loc = {"hl": "th", "gl": "TH", "ceid": "TH:th"} if lang == "th" else {"hl": "en-US", "gl": "US", "ceid": "US:en"}
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": query + " when:2d", **loc})
    items = ET.fromstring(http_get(url)).findall(".//item")[:8]
    return [{"title": i.findtext("title"), "date": i.findtext("pubDate")} for i in items]

MOVERS = [("day_gainers", "🚀 บวกแรง"), ("day_losers", "📉 ลบแรง"), ("most_actives", "🔥 ซื้อขายมากสุด")]

def movers():
    out = {}
    for scr, label in MOVERS:
        url = f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?scrIds={scr}&count=5"
        qs = json.loads(http_get(url))["finance"]["result"][0]["quotes"]
        out[label] = [{"symbol": q["symbol"], "name": q.get("shortName", ""), "price": q.get("regularMarketPrice"),
                       "change_pct": round(q.get("regularMarketChangePercent", 0), 2) + 0.0} for q in qs]
    return out

# ---------- Flex cards ----------
def fmt(n):
    return f"{n:,.2f}" if isinstance(n, (int, float)) else "-"

def quote_bubble(q):
    up = q["change"] >= 0
    color = "#06C755" if up else "#E53935"
    sign = "+" if up else ""
    return {"type": "bubble", "size": "kilo",
        "header": {"type": "box", "layout": "vertical", "backgroundColor": "#1E293B", "contents": [
            {"type": "text", "text": q["symbol"], "color": "#FFFFFF", "weight": "bold", "size": "lg"},
            {"type": "text", "text": q["name"], "color": "#CBD5E1", "size": "xs", "wrap": True, "maxLines": 2}]},
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
            {"type": "text", "text": f'{fmt(q["price"])} {q["currency"]}', "size": "xxl", "weight": "bold"},
            {"type": "text", "text": f'{"▲" if up else "▼"} {sign}{fmt(q["change"])} ({sign}{q["change_pct"]:.2f}%)', "color": color, "weight": "bold"},
            {"type": "separator", "margin": "md"},
            {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
                {"type": "text", "text": f'สูงสุด {fmt(q["day_high"])}', "size": "xs", "color": "#555555"},
                {"type": "text", "text": f'ต่ำสุด {fmt(q["day_low"])}', "size": "xs", "color": "#555555", "align": "end"}]},
            {"type": "text", "text": f'อัปเดต {q["time"]} (เวลาไทย)', "size": "xxs", "color": "#999999"}]},
        "footer": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": DISCLAIMER, "size": "xxs", "color": "#999999", "wrap": True, "align": "center"}]}}

def pct_row(label, price, pct):
    up = pct >= 0
    return {"type": "box", "layout": "horizontal", "contents": [
        {"type": "text", "text": label, "size": "sm", "flex": 3, "weight": "bold"},
        {"type": "text", "text": fmt(price), "size": "sm", "flex": 3, "align": "end"},
        {"type": "text", "text": f'{"+" if up else ""}{pct:.2f}%', "size": "sm", "flex": 2, "align": "end",
         "color": "#06C755" if up else "#E53935"}]}

def list_bubble(title, contents):
    return {"type": "bubble",
        "header": {"type": "box", "layout": "vertical", "backgroundColor": "#1E293B", "contents": [
            {"type": "text", "text": title, "color": "#FFFFFF", "weight": "bold", "size": "lg"},
            {"type": "text", "text": datetime.now(BKK).strftime("%d/%m/%Y %H:%M (เวลาไทย)"), "color": "#CBD5E1", "size": "xs"}]},
        "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": contents},
        "footer": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": DISCLAIMER, "size": "xxs", "color": "#999999", "wrap": True, "align": "center"}]}}

def flex(bubbles, alt):
    contents = bubbles[0] if len(bubbles) == 1 else {"type": "carousel", "contents": bubbles[:10]}
    return {"type": "flex", "altText": alt, "contents": contents}

# ---------- tools ----------
def run_tool(name, inp, cards):
    if name == "get_quote":
        out = []
        for s in inp["symbols"][:5]:
            try:
                q = quote(s)
                cards.append(quote_bubble(q))
                out.append(q)
            except Exception as e:
                out.append({"symbol": s, "error": f"ไม่พบข้อมูล ({type(e).__name__})"})
        return out
    if name == "market_overview":
        rows = []
        for sym, label in OVERVIEW:
            try:
                rows.append({"label": label, **quote(sym)})
            except Exception:
                pass
        if rows:
            cards.append(list_bubble("ดัชนีตลาด US", [pct_row(r["label"], r["price"], r["change_pct"]) for r in rows]))
        return rows
    if name == "top_movers":
        m = movers()
        body = []
        for label, qs in m.items():
            body += [{"type": "text", "text": label, "weight": "bold", "size": "sm", "margin": "lg"}]
            body += [pct_row(q["symbol"], q["price"], q["change_pct"]) for q in qs]
        cards.append(list_bubble("หุ้นเด่นวันนี้ (US)", body))
        return m
    if name == "get_news":
        return news(inp["query"], inp["lang"])
    raise ValueError(f"unknown tool {name}")

TOOLS = [
    {"name": "get_quote", "strict": True,
     "description": "ราคาล่าสุดของหุ้น/ดัชนี/สินทรัพย์ ใช้สัญลักษณ์แบบ Yahoo Finance: หุ้นไทยเติม .BK (PTT.BK, CPALL.BK), หุ้นสหรัฐฯ ใช้ตัวย่อ (AAPL, NVDA), ทองคำ GC=F, น้ำมัน CL=F, บิตคอยน์ BTC-USD, ค่าเงิน THB=X",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["symbols"],
                      "properties": {"symbols": {"type": "array", "items": {"type": "string"}, "description": "1-5 สัญลักษณ์"}}}},
    {"name": "market_overview", "strict": True,
     "description": "ดัชนีตลาดสหรัฐฯ: S&P 500, Nasdaq, Dow Jones, Russell 2000, VIX, US 10Y yield",
     "input_schema": {"type": "object", "additionalProperties": False, "required": [], "properties": {}}},
    {"name": "top_movers", "strict": True,
     "description": "หุ้นสหรัฐฯ ที่เคลื่อนไหวเด่นวันนี้: บวกแรง ลบแรง และซื้อขายมากสุด อย่างละ 5 ตัว (ข้อมูลจาก Yahoo screener)",
     "input_schema": {"type": "object", "additionalProperties": False, "required": [], "properties": {}}},
    {"name": "get_news", "strict": True,
     "description": "หัวข้อข่าว 2 วันล่าสุดจาก Google News query เป็นคำค้น lang=en ข่าวสหรัฐฯ เช่น 'stock market today', 'US CPI jobs report Fed', 'NVDA stock' lang=th ข่าวภาษาไทย",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["query", "lang"],
                      "properties": {"query": {"type": "string"}, "lang": {"type": "string", "enum": ["th", "en"]}}}},
]

SYSTEM = f"""คุณคือผู้ช่วยข้อมูลตลาดหุ้นสหรัฐฯ ใน LINE OA ตอบภาษาไทย สั้น กระชับ เป็นกันเอง
- เน้นตลาด US เป็นหลัก ถ้าไม่ระบุตลาดให้ถือว่าหมายถึง US
- ใช้เครื่องมือดึงข้อมูลจริงทุกครั้งที่ถามราคา ดัชนี หุ้นเด่น หรือข่าว ห้ามเดาตัวเลข
- ระบบจะส่งการ์ดให้ผู้ใช้เอง ข้อความของคุณไม่ต้องลอกตัวเลขทั้งหมด ให้สรุปประเด็นสำคัญ 1-3 บรรทัด
- วิเคราะห์ข่าว: ดึงข่าว 2 ชุด คือข่าวตลาดหุ้น ('stock market today') และข่าวตัวเลขเศรษฐกิจ ('US economic data CPI jobs Fed') คัดเฉพาะข่าวสำคัญ 3-5 ข้อ แปลสรุปเป็นไทยพร้อมวันที่ แต่ละข้อบอกสั้นๆ ว่าตลาดจับตาประเด็นนี้เพราะอะไร
- หุ้นเด่นวันนี้: คือหุ้นที่เคลื่อนไหวแรงหรือซื้อขายมาก ไม่ใช่หุ้นแนะนำ ถ้ามีข่าวอธิบายตัวที่เด่นที่สุดได้ ให้ดึงข่าวมาประกอบ 1-2 ตัว
- ห้ามแนะนำให้ซื้อ ขาย หรือถือหุ้น ห้ามทำนายราคา ถ้าถูกถามให้บอกว่าให้ข้อมูลได้อย่างเดียว
- ห้ามใช้ markdown (ไม่มี ** หรือ #) เพราะ LINE ไม่แสดงผล
- ถ้าดึงข้อมูลไม่ได้ ให้บอกตรงๆ
ลงท้ายคำตอบที่มีราคาหรือข่าวด้วย: "* {DISCLAIMER}" """

_client = None
HISTORY = {}  # user_id -> messages (in-memory; ponytail: move to Redis/DB if running >1 process)

def ask(user_id, text):
    global _client
    import anthropic
    _client = _client or anthropic.Anthropic()
    hist = HISTORY.setdefault(user_id, [])
    if len(hist) > 40:
        hist.clear()  # start a fresh conversation instead of editing old turns
    hist.append({"role": "user", "content": text})
    cards = []
    for _ in range(5):
        r = _client.beta.messages.create(
            model=MODEL, max_tokens=4000,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            tools=TOOLS, messages=hist,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        hist.append({"role": "assistant", "content": r.content})
        if r.stop_reason == "refusal":
            return "ขออภัย เรื่องนี้ตอบให้ไม่ได้ครับ", cards
        if r.stop_reason != "tool_use":
            break
        results = []
        for b in r.content:
            if b.type == "tool_use":
                try:
                    out = run_tool(b.name, b.input, cards)
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(out, ensure_ascii=False)})
                except Exception as e:
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": f"error: {e}", "is_error": True})
        hist.append({"role": "user", "content": results})
    reply = "".join(b.text for b in r.content if b.type == "text").strip()
    return reply or "ดึงข้อมูลไม่สำเร็จ ลองใหม่อีกครั้งนะครับ", cards

# ---------- LINE ----------
QUICK = {"items": [{"type": "action", "action": {"type": "message", "label": l, "text": t}} for l, t in [
    ("📰 วิเคราะห์ข่าว", "วิเคราะห์ข่าวตลาด US วันนี้"), ("🔥 หุ้นเด่นวันนี้", "หุ้นเด่นวันนี้"),
    ("📊 ดัชนี US", "ดัชนีตลาด US วันนี้"), ("💬 ราคา NVDA", "ราคา NVDA")]]}

def line_api(path, body=None, data=None, ctype="application/json", host="https://api.line.me/v2/bot/", method=None):
    if data is None:
        data = json.dumps(body).encode() if body is not None else b""
    req = urllib.request.Request(host + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")

RICH_MENU = ["วิเคราะห์ข่าวตลาด US วันนี้", "หุ้นเด่นวันนี้", "ดัชนีตลาด US วันนี้"]

def setup_rich_menu():
    """Create 3-button compact rich menu from rich_menu.jpg (2500x843) and make it the default for all users."""
    w = 2500 // 3
    areas = [{"bounds": {"x": i * w, "y": 0, "width": w + (i == 2), "height": 843},
              "action": {"type": "message", "text": t}} for i, t in enumerate(RICH_MENU)]
    rid = line_api("richmenu", {"size": {"width": 2500, "height": 843}, "selected": True,
                                "name": "main", "chatBarText": "เมนู", "areas": areas})["richMenuId"]
    line_api(f"richmenu/{rid}/content", data=(HERE / "rich_menu.jpg").read_bytes(), ctype="image/jpeg",
             host="https://api-data.line.me/v2/bot/")
    line_api(f"user/all/richmenu/{rid}")
    print("rich menu set:", rid)

def valid_signature(body: bytes, sig: str):
    mac = base64.b64encode(hmac.new(LINE_SECRET.encode(), body, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(mac, sig or "")

def handle_event(ev):
    try:
        if ev["type"] == "follow":
            msgs = [{"type": "text", "quickReply": QUICK, "text":
                     "สวัสดีครับ 📈 ติดตามตลาดหุ้นสหรัฐฯ ได้จากเมนูด้านล่าง หรือพิมพ์ถามเองได้เลย\nเช่น \"ราคา AAPL\" \"ข่าว NVDA ล่าสุด\"\n* " + DISCLAIMER}]
        elif ev["type"] == "message" and ev["message"]["type"] == "text":
            uid = ev["source"].get("userId", "anon")
            try:
                line_api("chat/loading/start", {"chatId": uid, "loadingSeconds": 20})
            except Exception:
                pass  # loading animation is cosmetic (1:1 chats only)
            reply, cards = ask(uid, ev["message"]["text"])
            msgs = ([flex(cards, "ข้อมูลราคา")] if cards else []) + [{"type": "text", "text": reply, "quickReply": QUICK}]
        else:
            return
        line_api("message/reply", {"replyToken": ev["replyToken"], "messages": msgs})
    except Exception as e:
        print("event error:", repr(e), file=sys.stderr)

def serve():
    from flask import Flask, abort, request
    app = Flask(__name__)

    @app.post("/callback")
    def callback():
        body = request.get_data()
        if not valid_signature(body, request.headers.get("X-Line-Signature")):
            abort(400)
        for ev in json.loads(body).get("events", []):
            threading.Thread(target=handle_event, args=(ev,), daemon=True).start()
        return "OK"  # ack fast; replies go out from the worker thread

    app.run(port=int(os.getenv("PORT", 8000)))

def set_webhook(base):
    url = base.rstrip("/") + "/callback"
    line_api("channel/webhook/endpoint", {"endpoint": url}, method="PUT")
    try:
        r = line_api("channel/webhook/test", {"endpoint": url})
        print("webhook set:", url, "->", "OK" if r.get("success") else r)
    except Exception as e:
        print("webhook set:", url, "(test failed:", e, ")")

def up():
    """Start a cloudflared quick tunnel, point the LINE webhook at it, then serve. Ctrl+C stops both."""
    import re, shutil, subprocess
    exe = shutil.which("cloudflared") or r"C:\Program Files (x86)\cloudflared\cloudflared.exe"
    port = os.getenv("PORT", "8000")
    cf = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--url", f"http://localhost:{port}"],
                          stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    for line in cf.stderr:
        m = re.search(r"https://[\w-]+\.trycloudflare\.com", line)
        if m:
            break
    else:
        sys.exit("cloudflared exited before giving a tunnel URL")
    threading.Thread(target=lambda: [None for _ in cf.stderr], daemon=True).start()  # keep draining the pipe
    threading.Timer(8, set_webhook, [m.group(0)]).start()  # new tunnel takes a few seconds to become reachable
    try:
        serve()
    finally:
        cf.terminate()

def selftest():
    global LINE_SECRET
    LINE_SECRET = "s3cret"
    body = b'{"events":[]}'
    sig = base64.b64encode(hmac.new(b"s3cret", body, hashlib.sha256).digest()).decode()
    assert valid_signature(body, sig) and not valid_signature(body, "bad")
    q = {"symbol": "PTT.BK", "name": "PTT", "price": 37.4, "change": -0.5, "change_pct": -1.32,
         "day_high": 37.7, "day_low": 37.2, "currency": "THB", "time": "21/11 16:30"}
    b = quote_bubble(q)["body"]["contents"]
    assert b[1]["color"] == "#E53935" and b[1]["text"].startswith("▼ -0.50")
    assert flex([quote_bubble(q)] * 2, "x")["contents"]["type"] == "carousel"
    print("selftest ok")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "selftest":
        selftest()
    elif cmd == "richmenu":
        setup_rich_menu()
    elif cmd == "webhook":  # python bot.py webhook https://xxxx.trycloudflare.com
        set_webhook(sys.argv[2])
    elif cmd == "up":
        up()
    elif cmd == "chat":
        while True:
            try:
                q = input("คุณ: ")
            except EOFError:
                break
            reply, cards = ask("cli", q)
            print(f"[{len(cards)} การ์ด]" if cards else "", "บอท:", reply)
    else:
        serve()
