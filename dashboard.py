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

# --- 1. KEAMANAN AKSES ---
def check_password():
    def password_entered():
        if st.session_state["username"] == st.secrets["MY_USER"] and \
           st.session_state["password"] == st.secrets["MY_PASS"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔒 Private Trading System")
        st.text_input("Username", on_change=password_entered, key="username")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        return False
    return st.session_state["password_correct"]

if check_password():
    st.set_page_config(page_title="Deni Global Trading Terminal", layout="wide")

    # --- 2. DAFTAR INSTRUMEN TERSTRUKTUR ---
    ASSETS = {
        "FOREX": ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X'],
        "METALS": ['GC=F', 'SI=F'],
        "INDEXES": ['^IXIC', '^DJI', '^GSPC']
    }
    ALL_SYMBOLS = ASSETS["FOREX"] + ASSETS["METALS"] + ASSETS["INDEXES"]

    # --- 3. FUNGSI DATA & ANALISIS ---
    @st.cache_data(ttl=60)
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
            # Handle Multi-Index if necessary
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['EMA20'] = ta.ema(df['Close'], length=20)
            return df
        except: return None

    # --- 4. TAMPILAN DASHBOARD ---
    st.title("🛰️ Deni Global Trading Terminal")
    st.write(f"Server Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # TABS UNTUK STRUKTUR YANG RAPI
    tab_monitor, tab_charts, tab_calendar = st.tabs(["📊 Monitoring & Signal", "📈 Candlestick Charts", "📅 Economic Calendar"])

    with tab_monitor:
        st.subheader("Real-Time Market Signals")
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
        selected_asset = st.selectbox("Pilih Aset untuk Dilihat:", ALL_SYMBOLS)
        df_chart = fetch_data(selected_asset)
        if df_chart is not None:
            fig = go.Figure(data=[go.Candlestick(
                x=df_chart.index,
                open=df_chart['Open'],
                high=df_chart['High'],
                low=df_chart['Low'],
                close=df_chart['Close'],
                name=selected_asset
            )])
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA20'], line=dict(color='orange', width=1), name='EMA20'))
            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            

    with tab_calendar:
        st.subheader("Upcoming Economic Events")
        st.dataframe(get_economic_calendar(), use_container_width=True)
        

    # --- 5. BACKGROUND WORKER (TELEGRAM) ---
    def telegram_worker():
        bot = Bot(token=st.secrets["TELEGRAM_TOKEN"])
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        last_notif_time = 0
        
        while True:
            current_time = time.time()
            # Scan setiap 5 menit
            if current_time - last_notif_time > 300:
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
                last_notif_time = current_time
            time.sleep(60)

    if "bg_active" not in st.runtime.get_instance()._session_mgr.__dict__:
        threading.Thread(target=telegram_worker, daemon=True).start()
        st.runtime.get_instance()._session_mgr.__dict__["bg_active"] = True

    # Auto Refresh UI
    time.sleep(60)
    st.rerun()
