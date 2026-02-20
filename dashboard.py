import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from telegram import Bot
import asyncio
import threading
import time

# --- CONFIG ---
st.set_page_config(page_title="Deni 24/7 Bot", layout="wide")

TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
bot = Bot(token=TELEGRAM_TOKEN)

# Variabel Global untuk menyimpan data terakhir (agar UI bisa nampilin)
if 'last_update' not in st.session_state:
    st.session_state['last_update'] = "Belum ada data"

# --- FUNGSI LOGIKA & DATA ---
def get_logic(price, rsi, ema):
    if rsi < 35 and price > ema: return "🚀 BELI"
    if rsi < 30: return "🛒 CICIL"
    if rsi > 70: return "⚠️ JUAL"
    if price < ema: return "❌ JANGAN BELI"
    return "⚖️ TUNGGU"

# --- WORKER: INI YANG JALAN 24 JAM DI SERVER ---
def background_worker():
    """Fungsi ini berjalan di thread terpisah, tidak peduli tab dibuka atau tidak"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        try:
            # Contoh Scan BTC
            exchange = ccxt.indodax()
            bars = exchange.fetch_ohlcv('BTC/IDR', timeframe='1h', limit=50)
            df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
            rsi = ta.rsi(df['close'], length=14).iloc[-1]
            ema = ta.ema(df['close'], length=20).iloc[-1]
            price = df['close'].iloc[-1]
            
            status = get_logic(price, rsi, ema)
            
            # Kirim Telegram HANYA jika sinyal Beli/Jual
            if "BELI" in status or "JUAL" in status:
                msg = f"🔔 *NOTIF 24/7*\nBTC: Rp{price:,.0f}\nSinyal: {status}"
                loop.run_until_complete(bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='Markdown'))
            
            print("Background Scan Success...")
        except Exception as e:
            print(f"Worker Error: {e}")
            
        time.sleep(60) # Scan tiap 1 menit agar tidak kena banned API

# --- MENJALANKAN WORKER SEKALI SAJA ---
if "worker_started" not in st.runtime.get_instance()._session_mgr.__dict__:
    # Ini trik agar thread hanya dibuat 1x di server Streamlit
    thread = threading.Thread(target=background_worker, daemon=True)
    thread.start()
    st.runtime.get_instance()._session_mgr.__dict__["worker_started"] = True

# --- TAMPILAN UI (HANYA UNTUK MONITORING SAAT ANDA BUKA) ---
st.title("🛰️ Deni Trading Bot 24/7")
st.info("Bot ini berjalan di latar belakang server. Anda bisa menutup tab ini dan notifikasi Telegram tetap akan masuk.")

# Tampilkan tabel data terakhir jika ingin melihat manual
st.write(f"Status Server: ✅ Berjalan (Background Thread)")
