import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
import feedparser
from telegram import Bot
import asyncio
import threading
import time
from datetime import datetime

# --- 1. LOGIKA LOGIN DENGAN TOMBOL ---
def login_ui():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.markdown("<h2 style='text-align: center;'>🔒 Deni Private Terminal</h2>", unsafe_allow_value=True)
        
        # Kolom di tengah untuk tampilan login yang rapi
        _, col_mid, _ = st.columns([1, 2, 1])
        with col_mid:
            user = st.text_input("Username", placeholder="Masukkan username...")
            pw = st.text_input("Password", type="password", placeholder="Masukkan password...")
            
            if st.button("Masuk Ke Sistem"):
                if user == st.secrets["MY_USER"] and pw == st.secrets["MY_PASS"]:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("❌ Username atau Password salah!")
        return False
    return True

# --- JALANKAN CEK LOGIN ---
if login_ui():
    st.set_page_config(page_title="Deni Global Trading Terminal", layout="wide")

    # --- 2. DAFTAR INSTRUMEN ---
    ASSETS = {
        "FOREX": ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X'],
        "METALS": ['GC=F', 'SI=F'],
        "INDEXES": ['^IXIC', '^DJI', '^GSPC']
    }
    ALL_SYMBOLS = ASSETS["FOREX"] + ASSETS["METALS"] + ASSETS["INDEXES"]

    # --- 3. FUNGSI DATA & ANALISIS ---
    @st.cache_data(ttl=300)
    def get_economic_calendar():
        try:
            feed = feedparser.parse("https://www.dailyfx.com/free-ads/economic-calendar/rss")
            events = []
            for entry in feed.entries[:10]:
                events.append({"Waktu": entry.published, "Event": entry.title})
            return pd.DataFrame(events)
        except:
            return pd.DataFrame([{"Info": "Gagal memuat kalender ekonomi"}])

    def fetch_data(symbol):
        try:
            df = yf.download(symbol, period="5d", interval="1h", progress=False, auto_adjust=True)
            if df.empty: return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['EMA20'] = ta.ema(df['Close'], length=20)
            return df
        except: return None

    # --- 4. TAMPILAN DASHBOARD ---
    st.sidebar.title("🚀 Control Panel")
    st.sidebar.write(f"User: **{st.secrets['MY_USER']}**")
    if st.sidebar.button("Logout / Keluar"):
        st.session_state["authenticated"] = False
        st.rerun()

    st.title("🛰️ Deni Global Trading Terminal")
    st.write(f"Update Terakhir: {datetime.now().strftime('%H:%M:%S')} WIB")

    tab_monitor, tab_charts, tab_calendar = st.tabs(["📊 Monitoring", "📈 Candlestick Charts", "📅 Calendar"])

    with tab_monitor:
        st.subheader("Market Signals")
        results = []
        for sym in ALL_SYMBOLS:
            df = fetch_data(sym)
            if df is not None:
                last = df.iloc[-1]
                price, rsi, ema = last['Close'], last['RSI'], last['EMA20']
                status = "⚖️ WAIT"
                if rsi < 35 and price > ema: status = "🚀 BUY"
                elif rsi > 70: status = "⚠️ SELL"
                
                results.append({
                    "Symbol": sym.replace('=X', '').replace('^', ''),
                    "Price": f"{price:,.2f}" if price > 10 else f"{price:.4f}",
                    "RSI": f"{rsi:.2f}",
                    "Signal": status
                })
        st.table(pd.DataFrame(results))

    with tab_charts:
        st.subheader("Interactive Candlestick")
        selected_asset = st.selectbox("Pilih Aset:", ALL_SYMBOLS)
        df_chart = fetch_data(selected_asset)
        if df_chart is not None:
            fig = go.Figure(data=[go.Candlestick(
                x=df_chart.index, open=df_chart['Open'], high=df_chart['High'],
                low=df_chart['Low'], close=df_chart['Close'], name=selected_asset
            )])
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA20'], line=dict(color='orange', width=1.5), name='EMA20'))
            fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            [Image of a professional candlestick chart with EMA and RSI indicators]

    with tab_calendar:
        st.subheader("Upcoming Economic Events")
        st.dataframe(get_economic_calendar(), use_container_width=True)

    # --- 5. WORKER TELEGRAM 24/7 ---
    def telegram_worker():
        bot = Bot(token=st.secrets["TELEGRAM_TOKEN"])
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while True:
            notif_text = ""
            for sym in ALL_SYMBOLS:
                df = fetch_data(sym)
                if df is not None:
                    last = df.iloc[-1]
                    if last['RSI'] < 35 and last['Close'] > last['EMA20']:
                        notif_text += f"🚀 *BUY ALERT*: {sym} @ {last['Close']:.4f}\n"
                    elif last['RSI'] > 70:
                        notif_text += f"⚠️ *SELL ALERT*: {sym} @ {last['Close']:.4f}\n"
            
            if notif_text:
                try:
                    loop.run_until_complete(bot.send_message(
                        chat_id=st.secrets["TELEGRAM_CHAT_ID"],
                        text=f"🌍 *MARKET ALERT*\n\n{notif_text}",
                        parse_mode='Markdown'
                    ))
                except: pass
            time.sleep(300) # Scan tiap 5 menit

    if "bg_active" not in st.runtime.get_instance()._session_mgr.__dict__:
        threading.Thread(target=telegram_worker, daemon=True).start()
        st.runtime.get_instance()._session_mgr.__dict__["bg_active"] = True

    time.sleep(60)
    st.rerun()
