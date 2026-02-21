import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import requests
import plotly.graph_objects as go
import pytz
from datetime import datetime
import time
from telegram import Bot
import asyncio

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Deni Market Monitor", layout="wide", page_icon="📈")

# Ambil Secret Telegram saja
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
except:
    st.error("⚠️ Masukkan TELEGRAM_TOKEN dan TELEGRAM_CHAT_ID di menu Secrets!")
    st.stop()

# --- 2. FUNGSI DATA & SINYAL ---

def fetch_market_data():
    """Ambil data Crypto & Forex dari sumber publik"""
    # List Aset
    crypto_pairs = {'btc_idr': 'BTC/IDR', 'eth_idr': 'ETH/IDR', 'sol_idr': 'SOL/IDR'}
    forex_pairs = {'GC=F': 'GOLD', 'EURUSD=X': 'EUR/USD'}
    
    results, msg = [], "🛰️ *LAPORAN PASAR DENI*\n\n"
    
    # Ambil Harga Crypto (Indodax API Publik)
    for p, name in crypto_pairs.items():
        try:
            url = f"https://indodax.com/api/ticker/{p}"
            price = float(requests.get(url).json()['ticker']['last'])
            # Sinyal Sederhana (Contoh: Harga di atas 10jt = TUNGGU)
            results.append({"Aset": name, "Harga": f"{price:,.0f}", "Sinyal": "MONITORING"})
            msg += f"🔸 {name}: Rp {price:,.0f}\n"
        except: continue
    
    # Ambil Harga Forex (Yahoo Finance)
    msg += "\n🌍 *FOREX & GOLD*\n"
    for p, name in forex_pairs.items():
        try:
            df = yf.download(p, period="1d", interval="1m", progress=False)
            price = df['Close'].iloc[-1]
            results.append({"Aset": name, "Harga": f"{price:,.2f}", "Sinyal": "MONITORING"})
            msg += f"🔹 {name}: {price:,.2f}\n"
        except: continue
        
    return results, msg

# --- 3. TAMPILAN DASHBOARD ---

col_t, col_j = st.columns([2, 1])
with col_t:
    st.title("📈 Deni Market Monitor")
    st.caption("Mode: Publik + Telegram Notif")

with col_j:
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    st.metric("🕒 Waktu WIB", now.strftime("%H:%M:%S"))

# Main Table
data_pasar, laporan_teks = fetch_market_data()
st.subheader("📊 Harga Real-Time")
st.table(pd.DataFrame(data_pasar))

# Tombol Kirim Telegram
st.divider()
if st.button("📲 Kirim Laporan ke Telegram Sekarang"):
    try:
        bot = Bot(token=TOKEN)
        asyncio.run(bot.send_message(chat_id=CHAT_ID, text=laporan_teks, parse_mode='Markdown'))
        st.success("✅ Terkirim ke Telegram!")
    except Exception as e:
        st.error(f"Gagal kirim: {e}")

# Auto Refresh
time.sleep(60)
st.rerun()
