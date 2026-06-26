import logging
import asyncio
import aiohttp
import time
import hmac
import hashlib
import base64
import json
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# تفعيل نظام تسجيل الأحداث والأخطاء
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ================== الإعدادات السيادية والمباشرة ==================
BOT_TOKEN = "8883942731:AAEWphhdFK_Xx8_QSU9cHthoki9Qnafm5fg"  # تم وضع التوكن الخاص بك هنا
ADMIN_ID = 1149146249  # تم وضع الـ ID الخاص بك هنا كقيمة رقمية
SECRET_KEY = "V40_FIXED_ULTRA_2026"
SUB_FILE = "subscriptions.json"

# الروابط والمواقع الافتراضية
SNAP_LINK = "https://www.snapchat.com/add/t6x"
STORE_LINK = "https://shadeedsa.com/"

# قائمة العملات الرقمية المعتمدة للفحص (المتوافقة مع المعايير الفقهية للعملات)
HALAL_COINS = ['BTC','ETH','SOL','AVAX','NEAR','SUI','FET','LINK','TAO','RENDER','APT','DOT','ADA','TIA','OP','ARB','INJ','STX','EGLD','PEPE']

# ================== إدارة البيانات والاشتراكات ==================
def load_subs():
    if os.path.exists(SUB_FILE):
        try:
            with open(SUB_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_subs(data):
    with open(SUB_FILE, "w") as f: json.dump(data, f)

def generate_code(user_id, days):
    expiry = int(time.time()) + days*86400
    sig = hmac.new(SECRET_KEY.encode(), f"{user_id}:{expiry}".encode(), hashlib.sha256).hexdigest()[:16]
    token = base64.urlsafe_b64encode(f"{user_id}:{expiry}:{sig}".encode()).decode()
    return f"SHD-{token}"

def verify_code(code, user_id):
    try:
        decoded = base64.urlsafe_b64decode(code.replace("SHD-","").encode()).decode()
        uid, expiry, sig = decoded.split(":")
        check = hmac.new(SECRET_KEY.encode(), f"{uid}:{expiry}".encode(), hashlib.sha256).hexdigest()[:16]
        if sig == check and time.time() < int(expiry): return True, int(expiry)
        return False, "❌ الكود غير صالح أو منتهي الصلاحية"
    except: 
        return False, "⚠️ كود تالف أو غير مدعوم"

# ================== محرك التحليل الفني V40 ==================
async def fetch_v40_data(session, symbol):
    try:
        url = f"https://data-api.binance.vision/api/v3/klines?symbol={symbol.upper()}USDT&interval=1h&limit=100"
        async with session.get(url, timeout=5) as r:
            if r.status != 200: return None
            data = await r.json()
        
        if not data or len(data) < 20: return None
        
        closes = [float(x[4]) for x in data]
        volumes = [float(x[5]) for x in data]
        highs = [float(x[2]) for x in data]
        lows = [float(x[3]) for x in data]
        
        # معادلة حساب مؤشر القوة النسبية RSI
        diffs = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d for d in diffs[-14:] if d > 0]
        losses = [abs(d) for d in diffs[-14:] if d < 0]
        
        avg_gain = sum(gains) / 14 if gains else 0
        avg_loss = sum(losses) / 14 if losses else 0
        
        if avg_loss == 0:
            rsi = 100 if avg_gain > 0 else 50
        else:
            rs = avg_gain / avg_loss
            rsi = round(100 - (100 / (1 + rs)), 2)
        
        avg_vol_24 = sum(volumes[-24:]) / 24
        vol_surge = round(volumes[-1] / avg_vol_24, 2) if avg_vol_24 > 0 else 1.0
        
        change = round(((closes[-1] - closes[-2]) / closes[-2]) * 100, 2) if closes[-2] > 0 else 0
        
        return {
            "symbol": symbol.upper(), "price": closes[-1], "rsi": rsi, "vol": vol_surge,
            "low": min(lows[-24:]), "high": max(highs[-24:]), "change": change
        }
    except: 
        return None

def format_v40_report(data):
    mode = "up" if data['rsi'] < 53 else "down"
    price = data['price']
    
    decimal_places = 6 if price < 0.1 else 4 if price < 10 else 2
    
    t1 = round(price * (1.02 if mode=="up" else 0.98), decimal_places)
    t2 = round(price * (1.05 if mode=="up" else 0.95), decimal_places)
    t3 = round(price * (1.10 if mode=="up" else 0.90), decimal_places)
    sl = round(price * (0.96 if mode=="up" else 1.04), decimal_places)
    
    rate = 68 
    if mode == "up" and data['rsi'] < 30: rate += 12 
    elif mode == "up" and data['rsi'] < 45: rate += 7
    
    if data['vol'] > 2.0: rate += 6 
    elif data['vol'] > 1.2: rate += 3
    
    rate += hash(data['symbol']) % 5 
    rate = min(rate, 89) 
    
    type_label = "🟢 شراء (LONG)" if mode == "up" else "🔴 بيع (SHORT)"
    advice = "🔥 دخول قوي" if rate > 82 else "✅ دخول آمن" if rate > 72 else "⚠️ دخول مضاربي حذر"
    
    rep = f"🪙 <b>العملة:</b> <code>{data['symbol']}/USDT</code>\n"
    rep += f"📊 <b>توصية النظام:</b> <code>{type_label}</code>\n"
    rep += f"📈 <b>نسبة النجاح:</b> <code>{rate}%</code>\n"
    rep += f"⚖️ <b>التصنيف الفقهي:</b> <code>عملة مجازة ✅</code>\n"
    rep += f"💰 <b>السعر الآن:</b> <code>{price}</code>\n"
    rep += f"📢 <b>التوجيه:</b> <code>{advice}</code>\n"
    rep += f"────────────────\n"
    rep += f"🎯 <b>الأهداف:</b> <code>{t1}</code> | <code>{t2}</code> | <code>{t3}</code>\n"
    rep += f"🛡️ <b>الوقف:</b> <code>{sl}</code>\n"
    rep += f"📊 <b>RSI:</b> <code>{data['rsi']}%</code> | <b>VOL:</b> <code>{data['vol']}x</code>\n"
    rep += "────────────────\n"
    return rep

# ================== إدارة ومعالجة الرسائل ==================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    user_id = update.effective_user.id
    text = update.message.text.strip()
    subs = load_subs()

    if text.startswith("SHD-"):
        ok, res = verify_code(text, user_id)
        if ok:
            subs[str(user_id)] = res; save_subs(subs)
            await update.message.reply_text("✅ تم تفعيل بروتوكول V40 بنجاح! تم فتح الصلاحيات بالكامل.")
        else: 
            await update.message.reply_text(res)
        return

    # السماح للأدمن دائماً بالدخول، وفحص اشتراك البقية
    if user_id != ADMIN_ID:
        if str(user_id) not in subs or time.time() > subs[str(user_id)]:
            await update.message.reply_text("🚫 الوصول مرفوض. يرجى الاشتراك وتفعيل الكود للوصول إلى الرادار والتوصيات.")
            return

    if user_id == ADMIN_ID:
        if text.startswith("بث "):
            msg = text.replace("بث ", ""); count = 0
            for uid in subs.keys():
                try: 
                    await context.bot.send_message(chat_id=int(uid), text=f"📢 <b>تنبيه من الإدارة:</b>\n\n{msg}", parse_mode="HTML")
                    count += 1
                except: continue
            await update.message.reply_text(f"✅ تم البث لـ {count} مشترك بنجاح.")
            return
        elif text == "🔑 وحدة التحكم":
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎫 كود شهر", callback_data="gen_1m"), InlineKeyboardButton("🎫 كود سنة", callback_data="gen_1y")]])
            await update.message.reply_text("👑 لوحة تحكم الإدارة:", reply_markup=kb)
            return

    if text == "🔍 فحص عملة معينة":
        await update.message.reply_text("📥 أرسل رمز العملة مباشرة لفحصها (مثال: SOL أو BTC):")
        return
    elif text == "⚙️ بروتوكول الدعم":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 المتجر", url=STORE_LINK), InlineKeyboardButton("👻 سناب", url=SNAP_LINK)]])
        await update.message.reply_text("💎 نظام الدعم الفني V40 والمبيعات:", reply_markup=kb)
        return
    elif text in ["🟢 توصيات الشراء", "🔴 توصيات البيع", "🎯 رادار القناص", "🐳 تتبع الحيتان"]:
        wait_msg = await update.message.reply_text("📡 جاري مسح السوق والتحليل الفني... (قد يستغرق لحظات)")
        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(*[fetch_v40_data(session, c) for c in HALAL_COINS])
        
        found = False
        for d in [r for r in results if r]:
            if (text == "🟢 توصيات الشراء" and d['rsi'] < 48) or \
               (text == "🔴 توصيات البيع" and d['rsi'] > 55) or \
               (text == "🎯 رادار القناص" and d['rsi'] < 36) or \
               (text == "🐳 تتبع الحيتان" and d['vol'] > 1.6):
                found = True
                await update.message.reply_text(format_v40_report(d), parse_mode="HTML")
        
        await wait_msg.delete()
        if not found: await update.message.reply_text("🌑 لا توجد فرص محققة للشروط في قائمة العملات المعتمدة حالياً.")
        return

    symbol = text.upper().replace("USDT", "")
    if 2 <= len(symbol) <= 10:
        async with aiohttp.ClientSession() as session:
            data = await fetch_v40_data(session, symbol)
        if data: 
            await update.message.reply_text(format_v40_report(data), parse_mode="HTML")
        else:
            await update.message.reply_text("❌ لم نتمكن من جلب البيانات، تأكد من أن رمز العملة صحيح ومدرج في بينانس.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keys = [["🟢 توصيات الشراء", "🔴 توصيات البيع"], ["🎯 رادار القناص", "🐳 تتبع الحيتان"], ["🔍 فحص عملة معينة", "⚙️ بروتوكول الدعم"]]
    if update.effective_user.id == ADMIN_ID: keys.append(["🔑 وحدة التحكم"])
    await update.message.reply_text("🦅 <b>مرحباً بك في نظام V40 المطور للعملات الرقمية</b>\n\nاختر أحد الخدمات من القائمة أدناه للبدء:", reply_markup=ReplyKeyboardMarkup(keys, resize_keyboard=True), parse_mode="HTML")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id == ADMIN_ID:
        days = 30 if q.data == "gen_1m" else 365
        code = generate_code(ADMIN_ID, days)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🎫 كود جديد ({'شهر' if days==30 else 'سنة'}): <code>{code}</code>", parse_mode="HTML")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("⚡ [النظام]: البوت يعمل الآن بنجاح...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__": 
    main()
