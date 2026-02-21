import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import asyncio
import threading
import time

# --- KONFIGURASI ---
st.set_page_config(page_title="Deni Smart Dashboard", layout="wide")

# Mengambil API Key dari Streamlit Secrets
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
except:
    st.error("Konfigurasi Secrets (Token/ID) Belum Lengkap!")
    st.stop()

# Daftar Aset Lengkap
LIST_CRYPTO = ['BTC/IDR', 'ETH/IDR', 'SOL/IDR', 'BNB/IDR', 'XRP/IDR']
LIST_FOREX = ['GC=F', 'EURUSD=X', 'GBPUSD=X', 'USDJPY=X']

# Global State untuk kontrol bot
if 'bot_run' not in st.session_state:
    st.session_state['bot_run'] = True

# --- FUNGSI ANALISIS DATA ---
def fetch_and_logic():
    results = []
    notif = ""
    
    # 1. Crypto - Indodax
    ex = ccxt.indodax()
    for k in LIST_CRYPTO:
        try:
            bars = ex.fetch_ohlcv(k, timeframe='1h', limit=50)
            df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
            rsi = ta.rsi(df['close'], length=14).iloc[-1]
            ema = ta.ema(df['close'], length=20).iloc[-1]
            price = df['close'].iloc[-1]
            
            status = "TUNGGU"
            if rsi < 35 and price > ema: status = "🚀 BELI"
            elif rsi > 70: status = "⚠️ JUAL"
            
            results.append({"Aset": k, "Harga": f"Rp{price:,.0f}", "Sinyal": status})
            if status != "TUNGGU":
                notif += f"🟢 {status}: `{k}` @ Rp{price:,.0f}\n"
        except: continue

    # 2. Forex & Gold - Yahoo Finance
    for f in LIST_FOREX:
        try:
            data = yf.download(f, period="2d", interval="1h", progress=False, auto_adjust=True)
            close = data['Close'].iloc[:, 0] if isinstance(data['Close'], pd.DataFrame) else data['Close']
            p, r, e = close.iloc[-1], ta.rsi(close, length=14).iloc[-1], ta.ema(close, length=20).iloc[-1]
            
            status = "TUNGGU"
            if r < 35 and p > e: status = "🚀 BELI"
            elif r > 70: status = "⚠️ JUAL"
            
            name = "GOLD" if "GC=F" in f else f.replace('=X','')
            results.append({"Aset": name, "Harga": f"{p:,.2f}", "Sinyal": status})
            if status != "TUNGGU":
                notif += f"🔵 {status}: `{name}` @ {p:,.2f}\n"
        except: continue
        
    return results, notif

# --- TELEGRAM COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st.session_state['bot_run'] = True
    await update.message.reply_text("✅ Bot Dinyalakan! Sinyal akan dikirim otomatis jika terdeteksi.")

async def status_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🟢 Bot Aktif" if st.session_state['bot_run'] else "🔴 Bot Nonaktif"
    await update.message.reply_text(f"Status saat ini: {msg}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st.session_state['bot_run'] = False
    await update.message.reply_text("🛑 Bot Dimatikan. Gunakan /start untuk menyalakan kembali.")

# --- BACKGROUND PROCESSES ---
def run_telegram_listener():
    """Mendengarkan perintah /start, /status, /stop dari Telegram"""
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_bot))
    app.add_handler(CommandHandler("stop", stop))
    app.run_polling(close_loop=False)

def run_auto_scanner():
    """Memindai pasar dan mengirim notif otomatis setiap 5 menit"""
    bot = Bot(token=TOKEN)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while True:
        if st.session_state['bot_run']:
            _, notif = fetch_and_logic()
            if notif:
                full_msg = f"🛰️ *DENI SIGNAL DETECTOR*\n\n{notif}"
                loop.run_until_complete(bot.send_message(chat_id=CHAT_ID, text=full_msg, parse_mode='Markdown'))
        time.sleep(300)

# Jalankan Thread di latar belakang server (hanya sekali)
if "threads_active" not in st.runtime.get_instance()._session_mgr.__dict__:
    threading.Thread(target=run_telegram_listener, daemon=True).start()
    threading.Thread(target=run_auto_scanner, daemon=True).start()
    st.runtime.get_instance()._session_mgr.__dict__["threads_active"] = True

# --- TAMPILAN WEB ---
st.title("🛰️ Deni Smart Trading Monitor")
st.write(f"Update: {time.strftime('%H:%M:%S')} WIB")

res, _ = fetch_and_logic()
if res:
    st.table(pd.DataFrame(res))

time.sleep(60)
st.rerun()
