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
st.set_page_config(page_title="Deni 24/7 Monitoring", layout="wide")

# Keamanan API (Wajib diisi di Secrets Streamlit Cloud)
try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
except:
    st.error("Masukkan TELEGRAM_TOKEN dan TELEGRAM_CHAT_ID di Secrets!")
    st.stop()

bot = Bot(token=TELEGRAM_TOKEN)

# Daftar Aset
LIST_CRYPTO = ['BTC/IDR', 'ETH/IDR', 'SOL/IDR', 'BNB/IDR']
LIST_FOREX = ['GC=F', 'EURUSD=X', 'GBPUSD=X', 'USDJPY=X']

# Simpan status sinyal terakhir agar tidak spam Telegram
last_signals = {}

# --- FUNGSI ANALISIS ---
def get_logic(price, rsi, ema):
    if pd.isna(rsi) or pd.isna(ema): return "TUNGGU"
    if rsi < 35 and price > ema: return "BELI"
    if rsi < 30: return "CICIL"
    if rsi > 70: return "JUAL"
    if price < ema: return "JANGAN BELI"
    return "TUNGGU"

# --- WORKER BACKGROUND ---
def monitoring_worker():
    """Layanan latar belakang yang berjalan 24 jam di server"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        try:
            report_msg = ""
            
            # 1. Scan Crypto
            exchange = ccxt.indodax({'enableRateLimit': True, 'timeout': 10000})
            for k in LIST_CRYPTO:
                bars = exchange.fetch_ohlcv(k, timeframe='1h', limit=50)
                df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
                rsi = ta.rsi(df['close'], length=14).iloc[-1]
                ema = ta.ema(df['close'], length=20).iloc[-1]
                price = df['close'].iloc[-1]
                
                status = get_logic(price, rsi, ema)
                
                # Cek jika sinyal berubah atau sinyal penting (BELI/JUAL)
                if status in ["BELI", "JUAL", "CICIL"]:
                    key = f"crypto_{k}"
                    if last_signals.get(key) != status:
                        report_msg += f"🟢 *SIGNAL {status}* pada `{k}`\n💰 Harga: Rp{price:,.0f}\n\n"
                        last_signals[key] = status
                else:
                    last_signals[f"crypto_{k}"] = status

            # 2. Scan Forex & Gold
            for f in LIST_FOREX:
                data = yf.download(f, period="2d", interval="1h", progress=False, auto_adjust=True)
                if not data.empty:
                    close_col = data['Close'].iloc[:, 0] if isinstance(data['Close'], pd.DataFrame) else data['Close']
                    rsi = ta.rsi(close_col, length=14).iloc[-1]
                    ema = ta.ema(close_col, length=20).iloc[-1]
                    price = close_col.iloc[-1]
                    
                    status = get_logic(price, rsi, ema)
                    label = "GOLD" if "GC=F" in f else f.replace('=X','')
                    
                    if status in ["BELI", "JUAL", "CICIL"]:
                        key = f"forex_{f}"
                        if last_signals.get(key) != status:
                            p_fmt = f"{price:,.2f}" if "GC" in f else f"{price:.4f}"
                            report_msg += f"🔵 *SIGNAL {status}* pada `{label}`\n💰 Harga: {p_fmt}\n\n"
                            last_signals[key] = status
                    else:
                        last_signals[f"forex_{f}"] = status

            # Kirim jika ada akumulasi sinyal baru
            if report_msg:
                full_notif = f"🛰️ *Deni 24/7 Monitoring*\n\n{report_msg}"
                loop.run_until_complete(bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=full_notif, parse_mode='Markdown'))
            
            print(f"Background Scan {time.strftime('%H:%M:%S')} - Success")
            
        except Exception as e:
            print(f"Worker Error: {e}")
            
        time.sleep(120) # Scan setiap 2 menit agar server awet & tidak kena limit API

# --- TRIGGER WORKER ---
# Menggunakan st.runtime agar thread tetap hidup di server walaupun tab ditutup
if not hasattr(st, "already_started"):
    thread = threading.Thread(target=monitoring_worker, daemon=True)
    thread.start()
    st.already_started = True

# --- UI SEDERHANA (Hanya untuk Cek Status) ---
st.title("🛰️ Deni Smart Bot 24/7")
st.success("Bot Aktif di Background Server!")
st.write("Anda bisa menutup tab ini. Notifikasi Telegram akan otomatis masuk jika ada sinyal BELI atau JUAL.")

# Tampilan Tabel Monitoring Singkat
st.divider()
st.subheader("Status Sinyal Terakhir")
st.write(last_signals if last_signals else "Menunggu pemindaian pertama...")
