import os
import logging
import requests
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Setup Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
TARGET_CHAT_ID = 978089424

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

# --- INGATAN HARGA SEBELUMNYA ---
previous_prices = {
    "btc_usd": None,
    "sol_usd": None,
    "xrp_usd": None
}

def get_trend_emoji(current, previous):
    if previous is None or current == previous:
        return "⚪"
    elif current > previous:
        return "🟢"
    else:
        return "🔴"

# --- API HARGA CRYPTO & FIAT ---
def get_multiple_prices():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,solana,ripple&vs_currencies=usd,idr"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logging.error(f"Error Request API CoinGecko: {e}")
    return None

def get_crypto_price(crypto_symbol: str, target_currency: str) -> float:
    crypto_id = CRYPTO_MAP.get(crypto_symbol.lower())
    target_id = CRYPTO_MAP.get(target_currency.lower())
    
    if not crypto_id:
        return None
    
    if target_id:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto_id},{target_id}&vs_currencies=usd"
        try:
            res = requests.get(url, timeout=10).json()
            price_from = res.get(crypto_id, {}).get("usd")
            price_to = res.get(target_id, {}).get("usd")
            if price_from and price_to:
                return price_from / price_to
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
    except Exception as e:
        logging.error(f"Error Fiat rate: {e}")
    return None

# --- JOB PERIODIK (TIAP 1 MENIT) ---
async def send_price_update(context: ContextTypes.DEFAULT_TYPE):
    global previous_prices
    
    data = get_multiple_prices()
    if data:
        btc_usd = data.get("bitcoin", {}).get("usd", 0)
        btc_idr = data.get("bitcoin", {}).get("idr", 0)
        sol_usd = data.get("solana", {}).get("usd", 0)
        sol_idr = data.get("solana", {}).get("idr", 0)
        xrp_usd = data.get("ripple", {}).get("usd", 0)
        xrp_idr = data.get("ripple", {}).get("idr", 0)

        # Menentukan tren naik/turun
        btc_trend = get_trend_emoji(btc_usd, previous_prices["btc_usd"])
        sol_trend = get_trend_emoji(sol_usd, previous_prices["sol_usd"])
        xrp_trend = get_trend_emoji(xrp_usd, previous_prices["xrp_usd"])

        # Update ingatan harga untuk menit berikutnya
        previous_prices["btc_usd"] = btc_usd
        previous_prices["sol_usd"] = sol_usd
        previous_prices["xrp_usd"] = xrp_usd

        msg = (
            f"{btc_trend} $btc = ${btc_usd:,.2f}\n"
            f"{sol_trend} $sol = ${sol_usd:,.2f}\n"
            f"{xrp_trend} $xrp = ${xrp_usd:,.4f}\n"
        )
        
        try:
            await context.bot.send_message(chat_id=TARGET_CHAT_ID, text=msg, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Gagal mengirim pesan: {e}")

# --- HANDLER CONVERSION & COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Bot Konversi & Tracker Crypto Active**\n\n"
        "• Update BTC, SOL, XRP dikirim otomatis setiap **1 menit**.\n\n"
        "💡 **Cara Konversi Manual:**\n"
        "• Fiat: `10 usd to idr`, `50000 idr to myr`\n"
        "• Crypto: `1 btc to usd`, `2 sol to idr`"
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
            await update.message.reply_text("⚠️ Angka nominal tidak valid.")
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
                f"{amount:g} {from_symbol.upper()} = {formatted_total} {to_symbol.upper()}"
            )
            return

    fiat_rate = get_fiat_rate(from_symbol, to_symbol)
    if fiat_rate:
        total = amount * fiat_rate
        await update.message.reply_text(
            f"{amount:g} {from_symbol.upper()} = {total:,.2f} {to_symbol.upper()}"
        )
        return

    await update.message.reply_text("⚠️ Simbol mata uang / crypto tidak dikenali.")

if __name__ == '__main__':
    if not TOKEN:
        raise ValueError("Error: TELEGRAM_TOKEN belum diatur!")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    if app.job_queue:
        app.job_queue.run_repeating(send_price_update, interval=300, first=5)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot berjalan dengan indikator trend...")
    app.run_polling()
