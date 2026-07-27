import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Setup Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")

# Mapping simbol Crypto ke ID CoinGecko
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

def get_crypto_price(crypto_symbol: str, target_currency: str) -> float:
    """Mengambil harga Crypto dari CoinGecko API (Bisa target Fiat atau Crypto lain)"""
    crypto_id = CRYPTO_MAP.get(crypto_symbol.lower())
    target_id = CRYPTO_MAP.get(target_currency.lower())
    
    if not crypto_id:
        return None
    
    # Jika targetnya juga Crypto (misal: USDT to SOL)
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
    
    # Jika targetnya Mata Uang Biasa / Fiat (misal: BTC to IDR)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto_id}&vs_currencies={target_currency.lower()}"
    try:
        res = requests.get(url, timeout=10).json()
        return res.get(crypto_id, {}).get(target_currency.lower())
    except Exception as e:
        logging.error(f"Error Crypto-to-Fiat: {e}")
        return None

def get_fiat_rate(from_curr: str, to_curr: str) -> float:
    """Mengambil kurs mata uang biasa (Fiat)"""
    url = f"https://open.er-api.com/v6/latest/{from_curr.upper()}"
    try:
        res = requests.get(url, timeout=10).json()
        if res.get("result") == "success":
            return res["rates"].get(to_curr.upper())
        return None
    except Exception as e:
        logging.error(f"Error Fiat rate: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Bot Konversi Mata Uang & Crypto**\n\n"
        "Bisa digunakan untuk berbagai variasi format:\n\n"
        "💵 **Mata Uang Biasa (Fiat):**\n"
        "• `10 usd to idr`\n"
        "• `euro to idr` (otomatis dihitung 1)\n\n"
        "🪙 **Crypto:**\n"
        "• `1 usdt to sol` (Crypto ke Crypto)\n"
        "• `1 btc to idr` (Crypto ke Fiat)"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    parts = text.split()
    
    amount = 1.0
    from_symbol = ""
    to_symbol = ""

    # Parse input berdasarkan jumlah kata
    # Kasus 1: "10 usd to idr" atau "1 usdt to sol" (4 kata)
    if len(parts) == 4 and parts[2] == "to":
        try:
            amount = float(parts[0])
            from_symbol = parts[1]
            to_symbol = parts[3]
        except ValueError:
            await update.message.reply_text("⚠️ Angka tidak valid.")
            return
            
    # Kasus 2: "euro to idr" atau "btc to usd" (3 kata, tanpa menyebut angka)
    elif len(parts) == 3 and parts[1] == "to":
        amount = 1.0
        from_symbol = parts[0]
        to_symbol = parts[2]
    else:
        await update.message.reply_text(
            "💡 Contoh penggunaan:\n"
            "• `10 usd to idr`\n"
            "• `euro to idr`\n"
            "• `1 usdt to sol`"
        )
        return

    # 1. Cek apakah ini konversi yang melibatkan Crypto
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

    # 2. Cek konversi Fiat (Mata Uang Negara biasa)
    # Kode pendukung jika user mengetik "euro" menggantikan "eur"
    if from_symbol == "euro": from_symbol = "eur"
    if to_symbol == "euro": to_symbol = "eur"

    fiat_rate = get_fiat_rate(from_symbol, to_symbol)
    if fiat_rate:
        total = amount * fiat_rate
        await update.message.reply_text(
            f"💱 **Konversi Mata Uang**\n\n"
            f"{amount:g} {from_symbol.upper()} = **{total:,.2f} {to_symbol.upper()}**"
        )
        return

    await update.message.reply_text("❌ Simbol mata uang atau crypto tidak ditemukan.")

if __name__ == '__main__':
    if not TOKEN:
        raise ValueError("Error: TELEGRAM_TOKEN tidak ditemukan!")
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot berjalan...")
    app.run_polling()
