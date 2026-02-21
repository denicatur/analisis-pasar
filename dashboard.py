import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import requests
import feedparser
import plotly.graph_objects as go
import google.generativeai as genai
from telegram import Bot
import asyncio
import time
from datetime import datetime
import pytz

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Deni Smart Dashboard Pro", layout="wide", page_icon="🛰️")

# Inisialisasi API dari Secrets
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    TOKO_KEY = st.secrets["TOKOCRYPTO_API_KEY"]
    TOKO_SECRET = st.secrets["TOKOCRYPTO_SECRET_KEY"]
    
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-pro')
except Exception as e:
    st.error(f"⚠️ Konfigurasi Secrets tidak lengkap: {e}")
    st.stop()

# --- 2. FUNGSI DATA ---

def fetch_crypto_signals():
    ex = ccxt.tokocrypto()
    pairs = ['BTC/BIDR', 'ETH/BIDR', 'SOL/BIDR', 'BNB/BIDR']
    results, msg = [], ""
    for k in pairs:
        try:
            bars = ex.fetch_ohlcv(k, timeframe='1h', limit=100)
            df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
            rsi = ta.rsi(df['close'], length=14).iloc[-1]
            ema20 = ta.ema(df['close'], length=20).iloc[-1]
            atr = ta.atr(df['high'], df['low'], df['close'], length=14).iloc[-1]
            price = df['close'].iloc[-1]
            status = "TUNGGU"
            sl_price = 0
            if rsi < 35 and price > ema20:
                status = "🚀 BELI"
                sl_price = price - (atr * 2)
            elif rsi > 70:
                status = "⚠️ JUAL"
                sl_price = price + (atr * 2)
            results.append({"Aset": k, "Harga": price, "RSI": rsi, "Sinyal": status, "SL": sl_price})
            if status != "TUNGGU":
                msg += f"🏢 *TOKOCRYPTO:* {status} {k}\n💰 Harga: {price:,.0f}\n\n"
        except: continue
    return results, msg

def fetch_tokocrypto_new_coins():
    try:
        url = "https://api.tokocrypto.com/open/v1/common/symbols"
        response = requests.get(url).json()
        if response['code'] == 0:
            return [{"Koin": c['baseAsset'], "Pasangan": c['symbol'], "Status": "Active"} for c in response['data']['list'][:5]]
    except: return []

def fetch_forex_signals():
    pairs = {'GC=F': 'GOLD (XAU/USD)', 'EURUSD=X': 'EUR/USD', 'GBPUSD=X': 'GBP/USD'}
    results, msg = [], ""
    for sym, name in pairs.items():
        try:
            data = yf.download(sym, period="5d", interval="1h", progress=False)
            df = data['Close']
            rsi = ta.rsi(df, length=14).iloc[-1]
            price = df.iloc[-1]
            status = "🚀 BUY" if rsi < 30 else "⚠️ SELL" if rsi > 70 else "TUNGGU"
            results.append({"Pair": name, "Harga": f"{price:,.2f}", "RSI": f"{rsi:.1f}", "Sinyal": status})
            if status != "TUNGGU":
                msg += f"🌍 *FOREX:* {status} {name}\n💰 Harga: {price:,.2f}\n\n"
        except: continue
    return results, msg

def get_ai_news():
    feed = feedparser.parse("https://cryptopanic.com/news/rss/")
    news_data = []
    for entry in feed.entries[:3]:
        try:
            prompt = f"Analisis sentimen berita ini (Bullish/Bearish/Neutral) dalam 1 kata: {entry.title}"
            sentimen = ai_model.generate_content(prompt).text
            news_data.append({"Judul": entry.title, "Sentimen": sentimen})
        except: news_data.append({"Judul": entry.title, "Sentimen": "Neutral"})
    return news_data

# --- 3. UI DASHBOARD ---

# Header & Jam Real-Time
col_title, col_time = st.columns([2, 1])
with col_title:
    st.title("🛰️ Deni Smart Dashboard Pro")

with col_time:
    tz_jkt = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz_jkt)
    st.metric("🕒 Jam Real-Time (WIB)", now.strftime("%H:%M:%S"))
    st.caption(now.strftime("%A, %d %B %Y"))

# Sidebar: Money Management dengan Tombol Konfirmasi
with st.sidebar:
    st.header("🛡️ MM Assistant")
    total_modal = st.number_input("Modal Trading (BIDR)", value=10000000, step=500000)
    e_price = st.number_input("Harga Entry", min_value=0.0)
    s_price = st.number_input("Harga Stop Loss", min_value=0.0)
    risk_percent = st.slider("Toleransi Resiko (%)", 0.5, 5.0, 1.0)
    
    # Tombol Konfirmasi MM
    if st.button("📊 Hitung Posisi & Resiko"):
        if e_price > s_price > 0:
            risk_rp = total_modal * (risk_percent / 100)
            pos_size = risk_rp / (e_price - s_price)
            st.success(f"**Rekomendasi Beli:** {pos_size:.6f} koin")
            st.warning(f"**Resiko Kehilangan:** Rp{risk_rp:,.0f} ({risk_percent}%)")
        else:
            st.error("Harga Entry harus lebih besar dari Stop Loss!")

# Layout Utama
tab1, tab2, tab3 = st.tabs(["🚀 Sinyal Trading", "📊 Candlestick", "🎁 Info Koin & AI"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Sinyal Crypto")
        c_res, c_msg = fetch_crypto_signals()
        st.table(pd.DataFrame(c_res))
    with c2:
        st.subheader("Sinyal Forex & Gold")
        f_res, f_msg = fetch_forex_signals()
        st.table(pd.DataFrame(f_res))
    
    if st.button("📲 Kirim Laporan ke Telegram"):
        full_msg = f"🛰️ *DENI UPDATE*\n\n{c_msg}{f_msg}"
        asyncio.run(Bot(token=TOKEN).send_message(chat_id=CHAT_ID, text=full_msg, parse_mode='Markdown'))
        st.toast("Laporan Terkirim!", icon="✅")

with tab2:
    selected = st.selectbox("Pilih Market", ['BTC/BIDR', 'ETH/BIDR', 'SOL/BIDR'])
    try:
        bars = ccxt.tokocrypto().fetch_ohlcv(selected, timeframe='1h', limit=50)
        df_chart = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        df_chart['ts'] = pd.to_datetime(df_chart['ts'], unit='ms')
        fig = go.Figure(data=[go.Candlestick(x=df_chart['ts'], open=df_chart['open'], high=df_chart['high'], low=df_chart['low'], close=df_chart['close'])])
        fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=450)
        st.plotly_chart(fig, use_container_width=True)
    except: st.error("Grafik gagal dimuat.")

with tab3:
    cl, cr = st.columns(2)
    with cl:
        st.subheader("🆕 Listing Baru Tokocrypto")
        st.table(pd.DataFrame(fetch_tokocrypto_new_coins()))
    with cr:
        st.subheader("🤖 Analisis AI News")
        for n in get_ai_news():
            st.write(f"📌 {n['Judul']}")
            st.caption(f"Sentimen: {n['Sentimen']}")
            st.write("---")

# Auto-Refresh
st.divider()
st.caption(f"🔄 Terakhir Update: {datetime.now(tz_jkt).strftime('%H:%M:%S')}")
time.sleep(60)
st.rerun()
