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

# --- 1. LOGIKA LOGIN MODERN ---
def login_ui():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        # Tampilan Tengah
        _, col_mid, _ = st.columns([1, 1.5, 1])
        with col_mid:
            st.markdown("<h1 style='text-align: center; color: #00FFAA;'>🛰️ DENI TERMINAL</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center;'>Market Analysis & Automated Signals</p>", unsafe_allow_html=True)
            
            with st.container(border=True):
                user = st.text_input("👤 Username", placeholder="Enter username")
                pw = st.text_input("🔑 Password", type="password", placeholder="Enter password")
                
                # Tombol Login
                if st.button("AUTHENTICATE & ACCESS", use_container_width=True):
                    if user == st.secrets["MY_USER"] and pw == st.secrets["MY_PASS"]:
                        st.session_state["authenticated"] = True
                        st.rerun()
                    else:
                        st.error("❌ Invalid Credentials")
            
            st.caption("Secure encrypted access for authorized users only.")
        return False
    return True

# --- CEK LOGIN SEBELUM RENDER ---
if login_ui():
    st.set_page_config(page_title="Deni Global Trading Terminal", layout="wide")

    # --- 2. DATA INSTRUMEN ---
    ASSETS = {
        "FOREX": ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X'],
        "METALS": ['GC=F', 'SI=F'],
        "INDEXES/NASDAQ": ['^IXIC', '^DJI', '^GSPC']
    }
    ALL_SYMBOLS = ASSETS["FOREX"] + ASSETS["METALS"] + ASSETS["INDEXES/NASDAQ"]

    # --- 3. HELPER FUNCTIONS ---
    @st.cache_data(ttl=600)
    def fetch_calendar():
        try:
            feed = feedparser.parse("https://www.dailyfx.com/free-ads/economic-calendar/rss")
            data = [{"Time": e.published, "Event": e.title} for e in feed.entries[:12]]
            return pd.DataFrame(data)
        except:
            return pd.DataFrame([{"Info": "Calendar service unavailable"}])

    def fetch_market_data(symbol):
        try:
            df = yf.download(symbol, period="5d", interval="1h", progress=False, auto_adjust=True)
            if df.empty: return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['EMA20'] = ta.ema(df['Close'], length=20)
            return df
        except: return None

    # --- 4. SIDEBAR CONTROL ---
    st.sidebar.markdown(f"### 🛡️ Authorized User\n**{st.secrets['MY_USER']}**")
    if st.sidebar.button("LOGOUT SYSTEM", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()
    
    st.sidebar.divider()
    st.sidebar.info("Bot Status: 🟢 ACTIVE\nServer: Streamlit Cloud")

    # --- 5. MAIN UI ---
    st.title("🛰️ Deni Smart Trading Terminal")
    
    tab1, tab2, tab3 = st.tabs(["📊 Market Monitor", "📈 Chart Analysis", "📅 Economic Calendar"])

    with tab1:
        st.subheader("Automated Signal Feed")
        results = []
        for sym in ALL_SYMBOLS:
            df = fetch_market_data(sym)
            if df is not None:
                last = df.iloc[-1]
                price, rsi, ema = last['Close'], last['RSI'], last['EMA20']
                status = "⚖️ NEUTRAL"
                if rsi < 35 and price > ema: status = "🚀 BUY SIGNAL"
                elif rsi > 70: status = "⚠️ SELL SIGNAL"
                
                results.append({
                    "Symbol": sym.replace('=X', '').replace('^', ''),
                    "Price": f"{price:,.2f}" if price > 10 else f"{price:.4f}",
                    "RSI": f"{rsi:.2f}",
                    "System Signal": status
                })
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Candlestick & Indicator View")
        target = st.selectbox("Select Asset to Analyze:", ALL_SYMBOLS)
        df_chart = fetch_market_data(target)
        if df_chart is not None:
            fig = go.Figure(data=[go.Candlestick(
                x=df_chart.index, open=df_chart['Open'], high=df_chart['High'],
                low=df_chart['Low'], close=df_chart['Close'], name='Price'
            )])
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA20'], line=dict(color='#FFAA00', width=2), name='EMA 20'))
            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            

    with tab3:
        st.subheader("Global Economic Calendar")
        st.table(fetch_calendar())
        

    # --- 6. BACKGROUND WORKER (TELEGRAM) ---
    def telegram_worker():
        bot = Bot(token=st.secrets["TELEGRAM_TOKEN"])
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while True:
            notif_text = ""
            for sym in ALL_SYMBOLS:
                df = fetch_market_data(sym)
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
            time.sleep(300)

    if "bg_active" not in st.runtime.get_instance()._session_mgr.__dict__:
        threading.Thread(target=telegram_worker, daemon=True).start()
        st.runtime.get_instance()._session_mgr.__dict__["bg_active"] = True

    # Auto Refresh Web UI
    time.sleep(60)
    st.rerun()
