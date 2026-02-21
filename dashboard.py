import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import threading
import time

# --- CONFIG ---
st.set_page_config(page_title="Deni Smart Bot", layout="wide")

try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
except:
    st.error("Konfigurasi Secrets Belum Lengkap!")
    st.stop()

# State untuk kontrol Bot
if 'bot_active' not in st.session_state:
    st.session_state['bot_active'] = True

# --- FUNGSI COMMAND TELEGRAM ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st.session_state['bot_active'] = True
    await update.message.reply_text("✅ Monitoring Diaktifkan! Bot mulai memantau pasar...")

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st.session_state['bot_active'] = False
    await update.message.reply_text("🛑 Monitoring Dimatikan. Ketik /start untuk menyalakan kembali.")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "🟢 AKTIF" if st.session_state['bot_active'] else "🔴 NONAKTIF"
    await update.message.reply_text(f"Status Bot saat ini: {status}")

# --- WORKER: MENDENGARKAN PERINTAH TELEGRAM ---
def telegram_listener():
    """Fungsi ini berjalan 24 jam untuk menunggu perintah /start atau /stop"""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("stop", stop_cmd))
    application.add_handler(CommandHandler("status", status_cmd))
    
    print("Remote Control Telegram Aktif...")
    application.run_polling(close_loop=False)

# --- WORKER: SCANNER PASAR ---
def monitoring_worker():
    bot_obj = Bot(token=TELEGRAM_TOKEN)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        if st.session_state.get('bot_active', True):
            # ... (Kode fetch_data_all Anda di sini) ...
            # Jika ada sinyal, kirim notif:
            # loop.run_until_complete(bot_obj.send_message(...))
            print("Scanning pasar...")
        
        time.sleep(300) # Scan tiap 5 menit

# --- MENJALANKAN KEDUA WORKER ---
if "listener_started" not in st.runtime.get_instance()._session_mgr.__dict__:
    # Thread 1: Dengerin Chat Telegram
    threading.Thread(target=telegram_listener, daemon=True).start()
    # Thread 2: Scan Pasar
    threading.Thread(target=monitoring_worker, daemon=True).start()
    st.runtime.get_instance()._session_mgr.__dict__["listener_started"] = True

# --- UI STREAMLIT ---
st.title("🛰️ Deni Smart Bot Control")
status_label = "🟢 AKTIF" if st.session_state['bot_active'] else "🔴 NONAKTIF"
st.metric("Status Bot", status_label)

if st.button("Nyalakan Manual"):
    st.session_state['bot_active'] = True
if st.button("Matikan Manual"):
    st.session_state['bot_active'] = False
