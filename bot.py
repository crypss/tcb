import os
import re
import threading
import requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- WEB SERVER UNTUK RENDER FREE TIER ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot Online!", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)
# ----------------------------------------

# 1. Token Bot Telegram dari @BotFather (Gunakan token baru setelah di-reset)
TOKEN = "6686083484:AAH3bNJKZcgFML3jzSE0GwS8VolqMInXd9Y"

# 2. Web App URL dari Google Apps Script milikmu
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxDA8f6N46XqmonJgIN-w-Zz-ZekarLjW1MI6F-UwbyNQ9npPInLQGYcOHaC8PyssSY/exec"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! Saya Bot Konversi Mata Uang via Google Finance.\n\n"
        "Kirim format konversi seperti:\n"
        "• `20 usd to idr`\n"
        "• `100 eur to idr`\n"
        "• `50 sgd to myr`",
        parse_mode="Markdown"
    )

async def convert_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    
    # Deteksi pola: <angka> <dari_mata_uang> to <ke_mata_uang>
    pattern = r"^([\d\.]+)\s*([a-z]{3})\s+to\s+([a-z]{3})$"
    match = re.match(pattern, text)
    
    if not match:
        return
    
    amount = float(match.group(1))
    from_curr = match.group(2).upper()
    to_curr = match.group(3).upper()
    
    pair = f"{from_curr}{to_curr}"
    
    try:
        # Panggil Google Apps Script
        response = requests.get(f"{APPS_SCRIPT_URL}?pair={pair}", timeout=10)
        
        if response.status_code == 200:
            raw_text = response.text.strip()
            
            # Coba ubah respon langsung menjadi angka (float)
            try:
                # Menghapus koma pemisah ribuan jika ada
                clean_rate_str = raw_text.replace(',', '')
                rate = float(clean_rate_str)
                
                result = amount * rate
                
                pesan = (
                    f"💵 **Konversi Mata Uang (Google Finance)**\n\n"
                    f"`{amount:,.2f} {from_curr}` = `{result:,.2f} {to_curr}`\n\n"
                    f"*(Kurs 1 {from_curr} = {rate:,.2f} {to_curr})*"
                )
                await update.message.reply_text(pesan, parse_mode="Markdown")
                
            except ValueError:
                # Jika Google Finance merespons error/#N/A/teks non-angka
                await update.message.reply_text(
                    f"❌ Pasangan mata uang `{from_curr}` ke `{to_curr}` tidak ditemukan atau tidak valid di Google Finance.",
                    parse_mode="Markdown"
                )
        else:
            await update.message.reply_text("❌ Gagal terhubung ke layanan Google Finance.")
            
    except Exception as e:
        await update.message.reply_text("⚠️ Terjadi kesalahan koneksi saat mengambil data.")

if __name__ == '__main__':
    # 1. Jalankan Flask server di background thread (PENTING untuk Render Free Tier)
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 2. Jalankan Bot Telegram
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, convert_currency))
    
    print("Bot Google Finance All-Currency siap dijalankan!")
    app.run_polling()
