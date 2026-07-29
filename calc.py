import os
import re
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Setup Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")

def calculate_expression(text: str) -> str:
    """
    Fungsi untuk memproses string matematika / persentase.
    """
    text = text.strip().lower()

    # Pattern 1: Parsel format "67% 100000" atau "67% dari 100000"
    match_percent = re.match(r"^(\d+(?:\.\d+)?)\%\s*(?:dari)?\s*(\d+(?:\.\d+)?)$", text)
    if match_percent:
        percent = float(match_percent.group(1))
        amount = float(match_percent.group(2))
        result = (percent / 100) * amount
        return f"💡 **Hasil:** {percent}% dari {amount:,.2f} = **{result:,.2f}**"

    # Pattern 2: Operasi penambahan/pengurangan persen (contoh: "100000 + 10%" atau "100000 - 15%")
    match_add_sub_percent = re.match(r"^(\d+(?:\.\d+)?)\s*([\+\-])\s*(\d+(?:\.\d+)?)\%$", text)
    if match_add_sub_percent:
        amount = float(match_add_sub_percent.group(1))
        op = match_add_sub_percent.group(2)
        percent = float(match_add_sub_percent.group(3))
        
        diff = (percent / 100) * amount
        result = amount + diff if op == '+' else amount - diff
        return f"💡 **Hasil:** {amount:,.2f} {op} {percent}% = **{result:,.2f}**"

    # Pattern 3: Matematika Dasar (contoh: "50000 * 2", "100000 / 4", "500 + 250")
    # Sanitasi input hanya izinkan angka dan operator dasar demi keamanan
    cleaned_text = text.replace("x", "*").replace(":", "/")
    if re.match(r"^[0-9\.\+\-\*\/\(\)\s]+$", cleaned_text):
        try:
            # Evaluasi aman matematika sederhana
            result = eval(cleaned_text, {"__builtins__": None}, {})
            return f"🔢 **Hasil:** `{cleaned_text}` = **{result:,.2f}**"
        except Exception:
            return None

    return None

async def handle_calc_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    result_text = calculate_expression(text)

    if result_text:
        await update.message.reply_text(result_text, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧮 **Bot Kalkulator Simpel Active**\n\n"
        "Ketik perintah perhitungan langsung di chat, contoh:\n"
        "• `67% 100000` (Persentase)\n"
        "• `15% dari 250000`\n"
        "• `100000 + 10%` (Tambah persen)\n"
        "• `50000 * 3` atau `150000 / 2` (Matematika dasar)",
        parse_mode="Markdown"
    )

if __name__ == '__main__':
    if not TOKEN:
        raise ValueError("Error: TELEGRAM_TOKEN belum diatur!")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    # Tangkap semua pesan teks biasa
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_calc_message))

    print("Kalkulator Bot berjalan...")
    app.run_polling()