import os
import logging
import requests
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Setup Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")

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

# --- ID STIKER YANG DIMINTA ---
STICKER_BULL = "CAACAgEAAxkBAAEhBYhqaguThFURvTD5DMUvz92PtYbUTgACRgADcVG-MUXQrHf2FeEDPQQ"
STICKER_BEAR = "CAACAgEAAxkBAAEhBYxqagvc4ymf40pytKfY0-Jt4yfcuAACRQADcVG-MavBKOyGVYvcPQQ"
STICKER_BULLBEAR = "CAACAgEAAxkBAAEhBZBqagvz6UMiUkMbn4m0lHlyMUpomAACYgADcVG-MWtBqfq5ZZUKPQQ"

# --- INGATAN HARGA SEBELUMNYA ---
previous_prices = {
    "btc_usd": None,
    "sol_usd": None,
    "xrp_usd": None
}

def get_trend_indicator(current, previous):
    # Mengembalikan string tren: 'bull', 'bear', atau None jika stabil
    if previous is None or current == previous:
        return None
    elif current > previous:
        return 'bull'
    else:
        return 'bear'

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

# --- JOB PERIODIK ---
async def send_price_update(context: ContextTypes.DEFAULT_TYPE):
    global previous_prices
    
    data = get_multiple_prices()
    if data:
        btc_usd = data.get("bitcoin", {}).get("usd", 0)
        sol_usd = data.get("solana", {}).get("usd", 0)
        xrp_usd = data.get("ripple", {}).get("usd", 0)

        # Menentukan tren masing-masing koin
        btc_trend = get_trend_indicator(btc_usd, previous_prices["btc_usd"])
        sol_trend = get_trend_indicator(sol_usd, previous_prices["sol_usd"])
        xrp_trend = get_trend_indicator(xrp_usd, previous_prices["xrp_usd"])

        # Update ingatan harga untuk pengecekan berikutnya
        previous_prices["btc_usd"] = btc_usd
        previous_prices["sol_usd"] = sol_usd
        previous_prices["xrp_usd"] = xrp_usd

        # Menyusun baris teks hanya untuk koin yang berubah
        lines = []
        trends_found = []

        if btc_trend:
            icon = '🟢' if btc_trend == 'bull' else '🔴'
            lines.append(f"{icon} $btc = ${btc_usd:,.2f}")
            trends_found.append(btc_trend)
            
        if sol_trend:
            icon = '🟢' if sol_trend == 'bull' else '🔴'
            lines.append(f"{icon} $sol = ${sol_usd:,.2f}")
            trends_found.append(sol_trend)
            
        if xrp_trend:
            icon = '🟢' if xrp_trend == 'bull' else '🔴'
            lines.append(f"{icon} $xrp = ${xrp_usd:,.4f}")
            trends_found.append(xrp_trend)

        # Jika ada pergerakan harga pada koin manapun
        if lines:
            msg = "\n".join(lines)
            
            # Menentukan stiker yang akan dikirim di atas pesan harga
            # Jika semua tren yang aktif adalah 'bull'
            if all(t == 'bull' for t in trends_found):
                chosen_sticker = STICKER_BULL
            # Jika semua tren yang aktif adalah 'bear'
            elif all(t == 'bear' for t in trends_found):
                chosen_sticker = STICKER_BEAR
            # Jika ada campuran (misal ada bull dan bear sekaligus)
            else:
                chosen_sticker = STICKER_BULLBEAR

            try:
                # 1. Kirim stiker terlebih dahulu di bagian atas
                await context.bot.send_sticker(chat_id=TARGET_CHAT_ID, sticker=chosen_sticker)
                # 2. Kirim pesan teks daftar harga di bawahnya
                await context.bot.send_message(chat_id=TARGET_CHAT_ID, text=msg)
            except Exception as e:
                logging.error(f"Gagal mengirim pesan atau stiker: {e}")
        else:
            logging.info("Harga stabil (tidak ada perubahan), pengiriman pesan dilewati.")

# --- HANDLER CONVERSION & COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 <b>Bot Konversi & Tracker Crypto Active</b>\n\n"
        "• Update BTC, SOL, XRP dikirim otomatis dengan stiker animasi market.\n\n"
        "💡 <b>Cara Konversi Manual:</b>\n"
        "• Fiat: <code>10 usd to idr</code>, <code>50000 idr to myr</code>\n"
        "• Crypto: <code>1 btc to usd</code>, <code>2 sol to idr</code>",
        parse_mode="HTML"
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
        app.job_queue.run_repeating(send_price_update, interval=900, first=5)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot berjalan dengan fitur pengiriman stiker Bull/Bear/BullBear otomatis...")
    app.run_polling()
