import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from telegram import Bot
import asyncio
import threading
import time

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Deni Real-Time Monitor", layout="wide")

# Keamanan API (Wajib diisi di Secrets Streamlit)
try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
except:
    st.error("Konfigurasi Secrets (Token/ID) Belum Lengkap!")
    st.stop()

bot = Bot(token=TELEGRAM_TOKEN)

# Daftar Koin & Forex Lengkap
LIST_CRYPTO = ['BTC/IDR', 'ETH/IDR', 'SOL/IDR', 'BNB/IDR', 'XRP/IDR', 'DOGE/IDR', 'ADA/IDR']
LIST_FOREX = ['GC=F', 'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDCAD=X']

# State Global untuk memantau perubahan sinyal
if 'signals' not in st.session_state:
    st.session_state['signals'] = {}

# --- FUNGSI DATA ---
def get_logic(price, rsi, ema):
    if pd.isna(rsi) or pd.isna(ema): return "WAIT"
    if rsi < 35 and price > ema: return "🚀 BUY"
    if rsi < 30: return "🛒 ACCUMULATE"
    if rsi > 70: return "⚠️ SELL"
    if price < ema: return "❌ DOWN TREND"
    return "⚖️ HOLD"

def fetch_data_all():
    """Mengambil data valid dari Indodax & Yahoo Finance"""
    results = []
    notif_msg = ""
    
    # 1. Crypto (Indodax API - Valid & Realtime)
    exchange = ccxt.indodax({'enableRateLimit': True})
    for k in LIST_CRYPTO:
        try:
            bars = exchange.fetch_ohlcv(k, timeframe='1h', limit=50)
            df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
            rsi = ta.rsi(df['close'], length=14).iloc[-1]
            ema = ta.ema(df['close'], length=20).iloc[-1]
            price = df['close'].iloc[-1]
            status = get_logic(price, rsi, ema)
            
            results.append({"Aset": k, "Harga": f"Rp{price:,.0f}", "Sinyal": status, "Tipe": "CRYPTO"})
            
            # Cek Sinyal Penting untuk Telegram
            if status in ["🚀 BUY", "⚠️ SELL"]:
                notif_msg += f"🟢 *{status}*: `{k}` @ Rp{price:,.0f}\n"
        except: continue

    # 2. Forex & Gold (Yahoo Finance - Valid & Realtime)
    for f in LIST_FOREX:
        try:
            data = yf.download(f, period="2d", interval="1h", progress=False, auto_adjust=True)
            close_col = data['Close'].iloc[:, 0] if isinstance(data['Close'], pd.DataFrame) else data['Close']
            price = close_col.iloc[-1]
            rsi = ta.rsi(close_col, length=14).iloc[-1]
            ema = ta.ema(close_col, length=20).iloc[-1]
            status = get_logic(price, rsi, ema)
            
            label = "GOLD" if "GC=F" in f else f.replace('=X','')
            p_fmt = f"${price:,.2f}" if "GC" in f else f"{price:.4f}"
            results.append({"Aset": label, "Harga": p_fmt, "Sinyal": status, "Tipe": "FOREX/GOLD"})
            
            if status in ["🚀 BUY", "⚠️ SELL"]:
                notif_msg += f"🔵 *{status}*: `{label}` @ {p_fmt}\n"
        except: continue
        
    return results, notif_msg

# --- BACKGROUND THREAD (Running 24/7) ---
def worker():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while True:
        try:
            _, notif = fetch_data_all()
            if notif:
                full_notif = f"🛰️ *DENI SIGNAL DETECTOR*\n_Waktu: {time.strftime('%H:%M:%S')}_\n\n{notif}"
                loop.run_until_complete(bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=full_notif, parse_mode='Markdown'))
        except Exception as e:
            print(f"Worker Error: {e}")
        time.sleep(300) # Scan tiap 5 menit agar tidak kena limit rate API

# Jalankan worker hanya sekali
if not hasattr(st, "worker_started"):
    threading.Thread(target=worker, daemon=True).start()
    st.worker_started = True

# --- TAMPILAN DASHBOARD ---
st.title("🛰️ Deni Smart Monitoring Dashboard")
st.subheader(f"Status Pasar - {time.strftime('%d %b %Y %H:%M:%S')}")

data_list, _ = fetch_data_all()
df_display = pd.DataFrame(data_list)

if not df_display.empty:
    # Pisahkan tabel Crypto dan Forex
    c1, c2 = st.columns(2)
    with c1:
        st.info("🪙 Crypto Markets")
        st.dataframe(df_display[df_display['Tipe'] == 'CRYPTO'], use_container_width=True)
    with c2:
        st.warning("📈 Forex & Gold Markets")
        st.dataframe(df_display[df_display['Tipe'] == 'FOREX/GOLD'], use_container_width=True)

# Auto Refresh UI setiap 30 detik
time.sleep(30)
st.rerun()
