import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from telegram import Bot
import asyncio
import threading
import time

# --- 1. KONFIGURASI KEAMANAN ---
def check_password():
    """Mengembalikan True jika pengguna memasukkan password yang benar."""
    def password_entered():
        if st.session_state["username"] == st.secrets["MY_USER"] and \
           st.session_state["password"] == st.secrets["MY_PASS"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # hapus password dari session state
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔒 Akses Terbatas")
        st.text_input("Username", on_change=password_entered, key="username")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.info("Hanya Deni yang bisa mengakses dashboard ini.")
        return False
    elif not st.session_state["password_correct"]:
        st.error("❌ Username atau Password Salah!")
        st.text_input("Username", on_change=password_entered, key="username")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        return False
    else:
        return True

# --- 2. JALANKAN CEK LOGIN ---
if check_password():
    # --- JIKA LOGIN BERHASIL, JALANKAN PROGRAM UTAMA ---

    st.set_page_config(page_title="Deni Private Dashboard", layout="wide")

    # API Keys dari Secrets
    TOKEN = st.secrets["TELEGRAM_TOKEN"]
    CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
    
    LIST_CRYPTO = ['BTC/IDR', 'ETH/IDR', 'SOL/IDR', 'BNB/IDR']
    LIST_FOREX = ['GC=F', 'EURUSD=X', 'GBPUSD=X']

    def fetch_and_logic():
        results = []
        notif = ""
        ex = ccxt.indodax()
        # Scan Crypto
        for k in LIST_CRYPTO:
            try:
                bars = ex.fetch_ohlcv(k, timeframe='1h', limit=50)
                df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
                rsi = ta.rsi(df['close'], length=14).iloc[-1]
                ema = ta.ema(df['close'], length=20).iloc[-1]
                price = df['close'].iloc[-1]
                status = "TUNGGU"
                if rsi < 35 and price > ema: status = "🚀 BELI"
                elif rsi > 70: status = "⚠️ JUAL"
                results.append({"Aset": k, "Harga": f"Rp{price:,.0f}", "Sinyal": status})
                if status != "TUNGGU": notif += f"🟢 {status}: {k} @ Rp{price:,.0f}\n"
            except: continue
        return results, notif

    # --- WORKER BACKGROUND (24/7) ---
    def auto_scanner():
        bot = Bot(token=TOKEN)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while True:
            _, notif = fetch_and_logic()
            if notif:
                try:
                    loop.run_until_complete(bot.send_message(chat_id=CHAT_ID, text=f"🛰️ *SIGNAL DETECTOR*\n\n{notif}", parse_mode='Markdown'))
                except: pass
            time.sleep(300) # Cek tiap 5 menit

    if "bg_active" not in st.runtime.get_instance()._session_mgr.__dict__:
        threading.Thread(target=auto_scanner, daemon=True).start()
        st.runtime.get_instance()._session_mgr.__dict__["bg_active"] = True

    # --- TAMPILAN DASHBOARD ---
    st.title("🛰️ Deni Smart Private Dashboard")
    st.sidebar.success(f"Selamat Datang, {st.secrets['MY_USER']}!")
    if st.sidebar.button("Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

    res, _ = fetch_and_logic()
    st.table(pd.DataFrame(res))
    
    st.write("_Update otomatis setiap 60 detik (Halaman ini)_")
    time.sleep(60)
    st.rerun()
