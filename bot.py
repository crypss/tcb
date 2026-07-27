import os
import re
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Membaca token dari GitHub Secrets
TOKEN = os.environ.get("6686083484:AAH3bNJKZcgFML3jzSE0GwS8VolqMInXd9Y")
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxDA8f6N46XqmonJgIN-w-Zz-ZekarLjW1MI6F-UwbyNQ9npPInLQGYcOHaC8PyssSY/exec"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! Saya Bot Konversi Mata Uang via Google Finance.\n\n"
        "Kirim format konversi seperti:\n"
        "• `20 usd to idr`\n"
        "• `100 eur to idr`",
        parse_mode="Markdown"
    )

async def convert_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    pattern = r"^([\d\.]+)\s*([a-z]{3})\s+to\s+([a-z]{3})$"
    match = re.match(pattern, text)
    
    if not match:
        return
    
    amount = float(match.group(1))
    from_curr = match.group(2).upper()
    to_curr = match.group(3).upper()
    pair = f"{from_curr}{to_curr}"
    
    try:
        response = requests.get(f"{APPS_SCRIPT_URL}?pair={pair}", timeout=10)
        if response.status_code == 200:
            raw_text = response.text.strip().replace(',', '')
            rate = float(raw_text)
            result = amount * rate
            
            pesan = (
                f"💵 **Konversi Mata Uang (Google Finance)**\n\n"
                f"`{amount:,.2f} {from_curr}` = `{result:,.2f} {to_curr}`\n\n"
                f"*(Kurs 1 {from_curr} = {rate:,.2f} {to_curr})*"
            )
            await update.message.reply_text(pesan, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("⚠️ Terjadi kesalahan saat mengambil data.")

if __name__ == '__main__':
    if not TOKEN:
        print("Error: TELEGRAM_TOKEN tidak ditemukan!")
        exit(1)
        
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, convert_currency))
    
    print("Bot berjalan via GitHub Actions...")
    app.run_polling()
