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

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Deni Smart Dashboard Pro", layout="wide", page_icon="🛰️")

# Inisialisasi API dari Secrets
try:
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
    CMC_API_KEY = st.secrets["CMC_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    TOKO_KEY = st.secrets["TOKOCRYPTO_API_KEY"]
    TOKO_SECRET = st.secrets["TOKOCRYPTO_SECRET_KEY"]
    
    # Inisialisasi AI Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-pro')
except Exception as e:
    st.error(f"⚠️ Konfigurasi Secrets tidak lengkap: {e}")
    st.stop()

# --- 2. FUNGSI PENGAMBILAN DATA ---

def fetch_crypto_signals():
    """Analisis Sinyal Tokocrypto"""
    ex = ccxt.tokocrypto({'apiKey': TOKO_KEY, 'secret': TOKO_SECRET})
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
                msg += f"🏢 *TOKOCRYPTO:* {status} {k}\n💰 Harga: {price:,.0f}\n🛡️ SL: {sl_price:,.0f}\n\n"
        except: continue
    return results, msg

def fetch_forex_signals():
    """Analisis Sinyal Forex & Gold"""
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
    """Berita dengan Sentimen AI"""
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

st.title("🛰️ Deni Smart Dashboard Pro")

# Sidebar: Saldo & Money Management
with st.sidebar:
    st.header("💰 Saldo Tokocrypto")
    try:
        ex_toko = ccxt.tokocrypto({'apiKey': TOKO_KEY, 'secret': TOKO_SECRET})
        bal = ex_toko.fetch_balance()['free']
        st.metric("Saldo BIDR", f"Rp{bal.get('BIDR', 0):,.0f}")
    except: st.warning("Cek API Key Anda")

    st.divider()
    st.header("🛡️ MM Assistant")
    total_modal = st.number_input("Modal (BIDR)", value=10000000)
    e_price = st.number_input("Harga Entry", min_value=0.0)
    s_price = st.number_input("Harga Stop Loss", min_value=0.0)
    if e_price > s_price > 0:
        risk_rp = total_modal * 0.01
        pos_size = risk_rp / (e_price - s_price)
        st.success(f"Rekomendasi Beli: {pos_size:.6f}")
        st.info(f"Resiko per Trade: Rp{risk_rp:,.0f}")

# Tabs Utama
tab1, tab2, tab3 = st.tabs(["🚀 Live Sinyal", "📊 Grafik", "🎁 Airdrop & Berita"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Crypto Signals")
        c_res, c_msg = fetch_crypto_signals()
        st.table(pd.DataFrame(c_res))
    with col2:
        st.subheader("Forex & Gold")
        f_res, f_msg = fetch_forex_signals()
        st.table(pd.DataFrame(f_res))
    
    if st.button("📲 Kirim Laporan ke Telegram"):
        full_msg = f"🛰️ *DENI UPDATE REPORT*\n\n{c_msg}{f_msg}"
        asyncio.run(Bot(token=TOKEN).send_message(chat_id=CHAT_ID, text=full_msg, parse_mode='Markdown'))
        st.toast("Terkirim ke Telegram!", icon="✅")

with tab2:
    selected = st.selectbox("Pilih Aset", ['BTC/BIDR', 'ETH/BIDR', 'SOL/BIDR'])
    try:
        bars = ccxt.tokocrypto().fetch_ohlcv(selected, timeframe='1h', limit=50)
        df_chart = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        df_chart['ts'] = pd.to_datetime(df_chart['ts'], unit='ms')
        fig = go.Figure(data=[go.Candlestick(x=df_chart['ts'], open=df_chart['open'], high=df_chart['high'], low=df_chart['low'], close=df_chart['close'])])
        fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=500)
        st.plotly_chart(fig, use_container_width=True)
    except: st.error("Gagal memuat grafik")

with tab3:
    c_a, c_b = st.columns(2)
    with c_a:
        st.subheader("🤖 AI News Sentiment")
        for n in get_ai_news():
            st.write(f"📌 {n['Judul']}")
            st.caption(f"AI Sentimen: {n['Sentimen']}")
            st.write("---")
    with c_b:
        st.subheader("🪂 Airdrop Alert")
        airdrop_feed = feedparser.parse("https://cryptopanic.com/news/rss/?filter=airdrop")
        for e in airdrop_feed.entries[:5]:
            st.write(f"💎 [{e.title}]({e.link})")

# Footer & Auto-Refresh
st.divider()
st.caption(f"Terakhir Update: {datetime.now().strftime('%H:%M:%S')}")
time.sleep(60)
st.rerun()
