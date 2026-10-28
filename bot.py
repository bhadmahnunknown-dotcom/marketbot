import os, json, urllib.request, asyncio
from telegram import Update
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ["BOT_TOKEN"]
NEWS_URL = "https://api.jornalmongo.com/api"  # placeholder replaced below

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "marketbot"})
    return json.loads(urllib.request.urlopen(req, timeout=15).read())

def market_summary():
    lines = []
    try:
        d = fetch("https://api.frankfurter.app/latest?from=USD&to=EUR,GBP,NGN")
        r = d["rates"]
        lines.append(f"FX: USD/EUR {r['EUR']} | USD/GBP {r['GBP']} | USD/NGN {r['NGN']}")
    except Exception as e:
        lines.append(f"FX: unavailable ({e})")
    try:
        d = fetch("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true")
        for coin, v in d.items():
            ch = v.get("usd_24h_change", 0)
            lines.append(f"{coin.upper()}: ${v['usd']:,.0f} ({ch:+.1f}% 24h)")
    except Exception as e:
        lines.append(f"crypto: unavailable ({e})")
    return "\n".join(lines)

def geopolitics_summary():
    # BBC world rss, top headlines
    try:
        import xml.etree.ElementTree as ET
        req = urllib.request.Request("https://feeds.bbci.co.uk/news/world/rss.xml", headers={"User-Agent": "marketbot"})
        xml = urllib.request.urlopen(req, timeout=15).read()
        root = ET.fromstring(xml)
        items = root.findall(".//item")[:6]
        return "\n".join(f"- {i.find('title').text}" for i in items)
    except Exception as e:
        return f"news: unavailable ({e})"


def crypto_heatmap():
    try:
        d = fetch("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&sparkline=false&price_change_percentage=24h")
        d = [c for c in d if c["symbol"].upper() not in ("USDT", "USDC", "DAI", "FDUSD", "USDE", "FIGR_HELOC")]
        rows = sorted(d, key=lambda x: x.get("price_change_percentage_24h") or 0)
        lines = ["crypto heatmap (24h):"]
        for c in rows:
            p = c.get("price_change_percentage_24h") or 0
            bar = "🟩" * min(4, max(1, int(abs(p) / 2.5))) if p >= 0 else "🟥" * min(4, max(1, int(abs(p) / 2.5)))
            lines.append(f"{bar} {c['symbol'].upper()}: ${c['current_price']:,.4g} {p:+.1f}%")
        return "\n".join(lines)
    except Exception as e:
        return f"crypto heatmap: unavailable ({e})"

def forex_heatmap():
    try:
        majors = ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "USD/CAD"]
        import datetime as dt
        today = dt.datetime.utcnow().date()
        d2 = (today - dt.timedelta(days=5)).isoformat()
        d = fetch(f"https://api.frankfurter.app/{d2}..?from=USD&to=EUR,GBP,JPY,CHF,AUD,CAD")
        dates = sorted(d["rates"])
        prev, last = d["rates"][dates[0]], d["rates"][dates[-1]]
        # convert to conventional pairs
        inv = {"EUR": True, "GBP": True, "AUD": True}
        rows = []
        for cur in ["EUR", "GBP", "JPY", "CHF", "AUD", "CAD"]:
            p0, p1 = prev[cur], last[cur]
            if cur in inv:
                ch = (p0 / p1 - 1) * 100  # EUR/USD etc, usd side
                name = f"{cur}/USD"
            else:
                ch = (p1 / p0 - 1) * 100
                name = f"USD/{cur}"
            rows.append((name, ch))
        rows.sort(key=lambda r: r[1])
        lines = ["forex heatmap (% vs prev close):"]
        for name, ch in rows:
            bar = ("🟩" if ch >= 0 else "🟥") * min(4, max(1, int(abs(ch) / 0.3)))
            lines.append(f"{bar} {name} {ch:+.2f}%")
        return "\n".join(lines)
    except Exception as e:
        return f"forex heatmap: unavailable ({e})"



def rss_titles(url, n=6):
    import xml.etree.ElementTree as ET
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 marketbot"})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=15).read())
    items = root.findall(".//item")[:n]
    return "\n".join(f"- {i.find('title').text}" for i in items)

def yahoo(sym):
    import json as _json
    u=f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=2d&interval=1d"
    r=urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"})
    d=_json.loads(urllib.request.urlopen(r,timeout=15).read())
    m=d["chart"]["result"][0]["meta"]
    return m["regularMarketPrice"], m["chartPreviousClose"]

def commodities_heatmap():
    items=[("gold","GC=F"),("silver","SI=F"),("wti oil","CL=F"),("brent","BZ=F")]
    rows=[]
    for name,s in items:
        try:
            p,c=yahoo(s); rows.append((name,(p/c-1)*100,p))
        except Exception: pass
    rows.sort(key=lambda r:r[1])
    lines=["commodities:"]
    for name,ch,p in rows:
        bar=("🟩" if ch>=0 else "🟥")*min(4,max(1,int(abs(ch)/0.5)))
        lines.append(f"{bar} {name}: {p:,.2f} {ch:+.2f}%")
    return "\n".join(lines) if rows else "commodities: unavailable"

def indices_heatmap():
    items=[("s&p 500","^GSPC"),("nasdaq","^IXIC"),("dow","^DJI"),("ftse 100","^FTSE")]
    rows=[]
    for name,s in items:
        try:
            p,c=yahoo(s); rows.append((name,(p/c-1)*100,p))
        except Exception: pass
    rows.sort(key=lambda r:r[1])
    lines=["indices:"]
    for name,ch,p in rows:
        bar=("🟩" if ch>=0 else "🟥")*min(4,max(1,int(abs(ch)/0.5)))
        lines.append(f"{bar} {name}: {p:,.2f} {ch:+.2f}%")
    return "\n".join(lines) if rows else "indices: unavailable"


def nigeria_news():
    try:
        return "nigeria politics (premium times):\n" + rss_titles("https://www.premiumtimesng.com/feed")
    except Exception as e:
        return f"nigeria news: unavailable ({e})"

def stock_news():
    try:
        return "stock market news (marketwatch):\n" + rss_titles("https://feeds.content.dowjones.io/public/rss/mw_topstories")
    except Exception as e:
        return f"stock news: unavailable ({e})"


def ngn_rates():
    try:
        d = fetch("https://open.er-api.com/v6/latest/USD")
        r = d["rates"]
        upd = d.get("time_last_update_utc", "")
        return ("naira rates (live reference, updated " + upd.split(",")[0] + "):\n"
            + f"1 USD = ₦{r['NGN']:,.2f}\n"
            + f"1 EUR = ₦{r['NGN']/r['EUR']:,.2f}\n"
            + f"1 GBP = ₦{r['NGN']/r['GBP']:,.2f}\n"
            + f"1 CAD = ₦{r['NGN']/r['CAD']:,.2f}")
    except Exception as e:
        return f"ngn rates: unavailable ({e})"


SECTIONS = [("📊 markets","markets"),("🔥 crypto","crypto"),("💱 forex","forex"),("🛢 commodities","commodities"),("📈 indices","indices"),("🇳🇬 nigeria","nigeria"),("📰 stocks","stocks"),("₦ ngn","ngn"),("🌍 world news","news"),("💱 fx news","fxnews"),("📺 al jazeera","aljazeera"),("📡 cnn","cnn"),("🧾 all","all")]

def menu_kb():
    rows=[[InlineKeyboardButton(t, callback_data="cmd:"+c) for t,c in SECTIONS[i:i+2]] for i in range(0,len(SECTIONS),2)]
    return InlineKeyboardMarkup(rows)

async def on_button(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    data = q.data.replace("cmd:", "")
    text = {"markets": market_summary, "crypto": crypto_heatmap, "forex": forex_heatmap,
            "commodities": commodities_heatmap, "indices": indices_heatmap,
            "nigeria": nigeria_news, "stocks": stock_news, "ngn": ngn_rates,
            "news": geopolitics_summary, "fxnews": fx_news, "aljazeera": aljazeera_news, "cnn": cnn_news}.get(data)
    if data == "all":
        await q.message.reply_text(market_summary() + "\n\n" + crypto_heatmap() + "\n\n" + forex_heatmap() + "\n\n" + commodities_heatmap() + "\n\n" + indices_heatmap() + "\n\n" + nigeria_news() + "\n\n" + ngn_rates() + "\n\n" + fx_news() + "\n\n" + aljazeera_news() + "\n\n" + cnn_news() + "\n\n" + stock_news() + "\n\n" + geopolitics_summary())
    elif text:
        await q.message.reply_text(text())


def fx_news():
    out = []
    try:
        out.append("fx news (investing.com):\n" + rss_titles("https://www.investing.com/rss/news_1.rss", 6))
    except Exception:
        out.append("fx news: unavailable rn")
    return "\n\n".join(out)

def aljazeera_news():
    try:
        return "al jazeera:\n" + rss_titles("https://www.aljazeera.com/xml/rss/all.xml")
    except Exception:
        return "al jazeera: unavailable rn"

def cnn_news():
    try:
        return "cnn:\n" + rss_titles("http://rss.cnn.com/rss/cnn_world.rss")
    except Exception:
        return "cnn: unavailable rn"

async def cmd_start(update: Update, ctx):
    await update.message.reply_text("menu 👇 tap a button:\n(or use /markets /crypto /forex /commodities /indices /nigeria /stocks /ngn /news /all /subscribe)", reply_markup=menu_kb())

async def cmd_markets(update: Update, ctx):
    await update.message.reply_text(market_summary())

async def cmd_news(update: Update, ctx):
    await update.message.reply_text(geopolitics_summary())

async def cmd_all(update: Update, ctx):
    await update.message.reply_text(market_summary() + "\n\n" + crypto_heatmap() + "\n\n" + forex_heatmap() + "\n\n" + commodities_heatmap() + "\n\n" + indices_heatmap() + "\n\n" + nigeria_news() + "\n\n" + ngn_rates() + "\n\n" + fx_news() + "\n\n" + aljazeera_news() + "\n\n" + cnn_news() + "\n\n" + stock_news() + "\n\n" + geopolitics_summary())

async def daily_brief(ctx: ContextTypes.DEFAULT_TYPE):
    for chat_id in SUBSCRIBERS:
        try:
            await ctx.bot.send_message(chat_id, "daily brief:\n\n" + market_summary() + "\n\n" + geopolitics_summary())
        except Exception:
            pass

SUBSCRIBERS = set()
try:
    with open(os.path.expanduser("~/.folk/marketbot/subs.json")) as f:
        SUBSCRIBERS = set(json.load(f))
except Exception:
    pass

async def cmd_subscribe(update: Update, ctx):
    SUBSCRIBERS.add(update.effective_chat.id)
    with open(os.path.expanduser("~/.folk/marketbot/subs.json"), "w") as f:
        json.dump(list(SUBSCRIBERS), f)
    await update.message.reply_text("u'll get the daily brief at 8am utc. /all for it right now")

async def _reply(u, text):
    await u.message.reply_text(text)

def main():
    app = Application.builder().token(TOKEN).build()
    for c, h in [("start", cmd_start), ("markets", cmd_markets), ("news", cmd_news), ("all", cmd_all), ("subscribe", cmd_subscribe), ("crypto", lambda u, x: _reply(u, crypto_heatmap())), ("forex", lambda u, x: _reply(u, forex_heatmap())), ("commodities", lambda u, x: _reply(u, commodities_heatmap())), ("fxnews", lambda u, x: _reply(u, fx_news())), ("aljazeera", lambda u, x: _reply(u, aljazeera_news())), ("cnn", lambda u, x: _reply(u, cnn_news())), ("indices", lambda u, x: _reply(u, indices_heatmap())), ("nigeria", lambda u, x: _reply(u, nigeria_news())), ("stocks", lambda u, x: _reply(u, stock_news())), ("ngn", lambda u, x: _reply(u, ngn_rates()))]:
        app.add_handler(CommandHandler(c, h))
    app.add_handler(CallbackQueryHandler(on_button))
    app.job_queue.run_daily(daily_brief, time=__import__("datetime").time(hour=8, minute=0))
    webhook_url = os.environ.get("WEBHOOK_URL")
    if webhook_url:
        port = int(os.environ.get("PORT", "10000"))
        app.run_webhook(
            listen="0.0.0.0", port=port, url_path=TOKEN,
            webhook_url=f"{webhook_url}/{TOKEN}",
            secret_token=os.environ.get("WEBHOOK_SECRET", "change-me"),
        )
    else:
        app.run_polling()

if __name__ == "__main__":
    main()
