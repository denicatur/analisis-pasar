import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from telegram import Bot
import asyncio
import time

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Deni Trading Dashboard", layout="wide")

# Mengambil API Key dari Streamlit Secrets (Aman untuk Hosting)
try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
except:
    st.error("API Key belum diset di Streamlit Secrets!")
    st.stop()

LIST_CRYPTO = ['BTC/IDR', 'ETH/IDR', 'SOL/IDR', 'BNB/IDR']
LIST_FOREX = ['GC=F', 'EURUSD=X', 'GBPUSD=X', 'USDJPY=X']

# Inisialisasi Bot
bot = Bot(token=TELEGRAM_TOKEN)

async def send_telegram(msg):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='Markdown')
    except Exception as e:
        print(f"Error Telegram: {e}")

# Fungsi Ambil Data
def fetch_crypto(symbol):
    try:
        exchange = ccxt.indodax({'enableRateLimit': True, 'timeout': 10000})
        bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
        df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        df['RSI'] = ta.rsi(df['close'], length=14)
        df['EMA20'] = ta.ema(df['close'], length=20)
        return df
    except: return None

def fetch_forex(symbol):
    try:
        df = yf.download(symbol, period="5d", interval="1h", progress=False, auto_adjust=True)
        if df.empty: return None
        close_data = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        new_df = pd.DataFrame({'Close': close_data})
        new_df['RSI'] = ta.rsi(new_df['Close'], length=14)
        new_df['EMA20'] = ta.ema(new_df['Close'], length=20)
        return new_df
    except: return None

def get_logic(price, rsi, ema):
    if pd.isna(rsi) or pd.isna(ema): return "⚖️ LOADING", "gray"
    if rsi < 35 and price > ema: return "🚀 BELI", "green"
    if rsi < 30: return "🛒 CICIL", "blue"
    if rsi > 70: return "⚠️ JUAL", "red"
    if price < ema: return "❌ JANGAN BELI", "orange"
    return "⚖️ TUNGGU", "white"

# --- TAMPILAN DASHBOARD ---
st.title("🛰️ Deni Smart Trading Dashboard")
st.write(f"Update Terakhir: {time.strftime('%H:%M:%S')} WIB")

# Placeholder untuk Notifikasi di UI
notif_area = st.empty()
telegram_msg = ""

col1, col2 = st.columns(2)

with col1:
    st.subheader("🪙 Crypto")
    crypto_res = []
    for k in LIST_CRYPTO:
        df = fetch_crypto(k)
        if df is not None:
            last = df.iloc[-1]
            status, _ = get_logic(last['close'], last['RSI'], last['EMA20'])
            crypto_res.append({"Aset": k, "Harga": f"{last['close']:,.0f}", "Sinyal": status})
            if "BELI" in status or "JUAL" in status:
                telegram_msg += f"🟢 *SIGNAL {status}* pada `{k}` (Rp{last['close']:,.0f})\n"
    st.table(pd.DataFrame(crypto_res))

with col2:
    st.subheader("📈 Forex & Gold")
    forex_res = []
    for f in LIST_FOREX:
        df = fetch_forex(f)
        if df is not None:
            last = df.iloc[-1]
            status, _ = get_logic(last['Close'], last['RSI'], last['EMA20'])
            label = "GOLD" if "GC=F" in f else f.replace('=X','')
            forex_res.append({"Aset": label, "Harga": f"{last['Close']:,.2f}", "Sinyal": status})
            if "BELI" in status or "JUAL" in status:
                telegram_msg += f"🔵 *SIGNAL {status}* pada `{label}` ({last['Close']:,.2f})\n"
    st.table(pd.DataFrame(forex_res))

# Kirim Telegram jika ada Sinyal Ekstrim
if telegram_msg:
    st.warning("⚠️ Sinyal Beli/Jual Terdeteksi! Mengirim ke Telegram...")
    asyncio.run(send_telegram(f"🔔 *NOTIFIKASI TRADING*\n\n{telegram_msg}"))

# Auto Refresh setiap 30 detik
time.sleep(30)
st.rerun()