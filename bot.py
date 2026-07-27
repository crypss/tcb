import os
import logging
import requests
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Setup Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")

# Chat ID Telegram kamu langsung dikunci di sini
TARGET_CHAT_IDS = {978089424}

CRYPTO_MAP = {
    'btc': 'bitcoin',
    'eth': 'ethereum',
    'sol': 'solana',
    'doge': 'dogecoin',
    'bnb': 'binancecoin',
    'xrp': 'ripple',
    'ada': 'cardano',
    'usdt': 'tether',
    'dot': 'polkadot',
    'ltc': 'litecoin',
    'link': 'chainlink'
}

# --- FUNGSI AMBIL HARGA ---
def get_crypto_price(crypto_symbol: str, target_currency: str) -> float:
    crypto_id = CRYPTO_MAP.get(crypto_symbol.lower())
    target_id = CRYPTO_MAP.get(target_currency.lower())
    
    if not crypto_id:
        return None
    
    if target_id:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto_id},{target_id}&vs_currencies=usd"
        try:
            res = requests.get(url, timeout=10).json()
            price_from_usd = res.get(crypto_id, {}).get("usd")
            price_to_usd = res.get(target_id, {}).get("usd")
            if price_from_usd and price_to_usd:
                return price_from_usd / price_to_usd
        except Exception as e:
            logging.error(f"Error Crypto-to-Crypto: {e}")
            return None
    
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto_id}&vs_currencies={target_currency.lower()}"
    try:
        res = requests.get(url, timeout=10).json()
        return res.get(crypto_id, {}).get(target_currency.lower())
    except Exception as e:
        logging.error(f"Error Crypto-to-Fiat: {e}")
        return None

def get_fiat_rate(from_curr: str, to_curr: str) -> float:
    url = f"https://open.er-api.com/v6/latest/{from_curr.upper()}"
    try:
        res = requests.get(url, timeout=10).json()
        if res.get("result") == "success":
            return res["rates"].get(to_curr.upper())
        return None
    except Exception as e:
        logging.error(f"Error Fiat rate: {e}")
        return None

async def post_init(application):
    commands = [
        BotCommand("start", "Mulai bot & petunjuk penggunaan"),
    ]
    await application.bot.set_my_commands(commands)

# --- JOB MONITORING HARGA (TIAP 1 MENIT) ---
async def send_price_update(context: ContextTypes.DEFAULT_TYPE):
    btc_usd = get_crypto_price("btc", "usd")
    btc_idr = get_crypto_price("btc", "idr")
    sol_usd = get_crypto_price("sol", "usd")
    sol_idr = get_crypto_price("sol", "idr")
    xrp_usd = get_crypto_price("xrp", "usd")
    xrp_idr = get_crypto_price("xrp", "idr")

    if btc_usd and sol_usd and xrp_usd:
        msg = (
            "📊 **UPDATE HARGA CRYPTO (Tiap 1 Menit)**\n\n"
            f"🪙 **Bitcoin (BTC):**\n"
            f"• ${btc_usd:,.2f} USD\n"
            f"• Rp {btc_idr:,.0f} IDR\n\n"
            f"🪙 **Solana (SOL):**\n"
            f"• ${sol_usd:,.2f} USD\n"
            f"• Rp {sol_idr:,.0f} IDR\n\n"
            f"🪙 **Ripple (XRP):**\n"
            f"• ${xrp_usd:,.4f} USD\n"
            f"• Rp {xrp_idr:,.0f} IDR"
        )
        
        for chat_id in TARGET_CHAT_IDS:
            try:
                await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
                logging.info(f"Berhasil mengirim update ke {chat_id}")
            except Exception as e:
                logging.error(f"Gagal mengirim pesan ke {chat_id}: {e}")
    else:
        logging.error("Gagal mengambil harga crypto dari API.")

# --- HANDLER ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Bot Konversi & Tracker Crypto**\n\n"
        "• Update harga BTC, SOL, dan XRP akan dikirim otomatis **setiap 1 menit**.\n\n"
        "💡 **Cara Konversi Manual:**\n"
        "• `10 usd to idr`\n"
        "• `1 xrp to usdt`\n"
        "• `sol to idr`"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    parts = text.split()
    
    amount = 1.0
    from_symbol = ""
    to_symbol = ""

    if len(parts) == 4 and parts[2] == "to":
        try:
            amount = float(parts[0])
            from_symbol = parts[1]
            to_symbol = parts[3]
        except ValueError:
            await update.message.reply_text("⚠️ Angka tidak valid.")
            return
    elif len(parts) == 3 and parts[1] == "to":
        amount = 1.0
        from_symbol = parts[0]
        to_symbol = parts[2]
    else:
        return

    if from_symbol == "euro": from_symbol = "eur"
    if to_symbol == "euro": to_symbol = "eur"

    if from_symbol in CRYPTO_MAP or to_symbol in CRYPTO_MAP:
        rate = get_crypto_price(from_symbol, to_symbol)
        if rate:
            total = amount * rate
            formatted_total = f"{total:,.2f}" if total >= 1 else f"{total:.6f}"
            await update.message.reply_text(
                f"🪙 **Konversi Crypto**\n\n"
                f"{amount:g} {from_symbol.upper()} = **{formatted_total} {to_symbol.upper()}**"
            )
            return

    fiat_rate = get_fiat_rate(from_symbol, to_symbol)
    if fiat_rate:
        total = amount * fiat_rate
        await update.message.reply_text(
            f"💱 **Konversi Mata Uang**\n\n"
            f"{amount:g} {from_symbol.upper()} = **{total:,.2f} {to_symbol.upper()}**"
        )
        return

if __name__ == '__main__':
    if not TOKEN:
        raise ValueError("Error: TELEGRAM_TOKEN tidak ditemukan!")
    
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    
    job_queue = app.job_queue
    if job_queue:
        # Jalankan setiap 60 detik (1 menit)
        job_queue.run_repeating(send_price_update, interval=60, first=5)
        logging.info("JobQueue diaktifkan (Interval: 1 Menit).")
    else:
        logging.error("JobQueue TIDAK AKTIF! Pastikan requirements.txt berisi 'python-telegram-bot[job-queue]'")
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot berjalan...")
    app.run_polling()
