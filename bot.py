import os
import logging
import requests
from telegram import Update
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

# --- INGATAN HARGA SEBELUMNYA ---
previous_prices = {
    "btc_usd": None,
    "eth_usd": None,
    "sol_usd": None,
    "xrp_usd": None
}

def get_trend_emoji(current, previous):
    EMOJI_BULLISH = '🟢'
    EMOJI_BEARISH = '🔴'

    if previous is None or current == previous:
        return None
    elif current > previous:
        return EMOJI_BULLISH
    else:
        return EMOJI_BEARISH

# --- API HARGA CRYPTO & FIAT ---
def get_multiple_prices():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,ripple&vs_currencies=usd,idr"
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

# --- API BGEOMETRICS ON-CHAIN METRICS ---
def get_bgeometrics_metrics():
    base_url = "https://charts.bgeometrics.com/files/"
    metrics = {
        "realized_price": None,
        "delta_price": None
    }
    
    try:
        res = requests.get(f"{base_url}realized_price.json", timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data and len(data) > 0 and data[-1][1] is not None:
                metrics["realized_price"] = float(data[-1][1])
    except Exception as e:
        logging.error(f"Error Request Realized Price: {e}")

    try:
        res = requests.get(f"{base_url}delta_cap.json", timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data and len(data) > 0 and data[-1][1] is not None:
                metrics["delta_price"] = float(data[-1][1])
    except Exception as e:
        logging.error(f"Error Request Delta Price: {e}")

    return metrics

# --- API PUBLIK GRATIS: BINANCE LONG/SHORT RATIO ---
def get_binance_market_sentiment():
    """Mengambil data Long/Short Ratio global BTC dari Binance Futures secara publik & gratis"""
    url = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
    params = {
        "symbol": "BTCUSDT",
        "period": "1h",
        "limit": 1
    }
    
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data and len(data) > 0:
                latest = data[0]
                long_account = float(latest.get("longAccount", 0)) * 100
                short_account = float(latest.get("shortAccount", 0)) * 100
                ratio = float(latest.get("longShortRatio", 1))
                
                # Analisis sentimen sederhana
                if long_account > 55:
                    status = "⚠️ <i>Longs terlalu padat! Rawan kena long squeeze (turun dulu)</i>"
                elif short_account > 55:
                    status = "⚠️ <i>Shorts terlalu padat! Rawan kena short squeeze (naik dulu)</i>"
                else:
                    status = "⚖️ <i>Market seimbang / netral</i>"
                    
                return f"📊 <b>Binance BTC L/S Ratio:</b> Long {long_account:.1f}% | Short {short_account:.1f}%\n{status}"
    except Exception as e:
        logging.error(f"Error Request Binance Sentiment: {e}")
        
    return None

# --- JOB PERIODIK ---
async def send_price_update(context: ContextTypes.DEFAULT_TYPE):
    global previous_prices
    
    data = get_multiple_prices()
    onchain_data = get_bgeometrics_metrics()
    sentiment_data = get_binance_market_sentiment()
    
    usd_idr = get_fiat_rate("usd", "idr")
    eur_idr = get_fiat_rate("eur", "idr")

    if not data:
        logging.warning("Gagal mengambil data harga, melewati siklus ini.")
        return

    btc_usd = data.get("bitcoin", {}).get("usd", 0)
    eth_usd = data.get("ethereum", {}).get("usd", 0)
    sol_usd = data.get("solana", {}).get("usd", 0)
    xrp_usd = data.get("ripple", {}).get("usd", 0)

    btc_trend = get_trend_emoji(btc_usd, previous_prices["btc_usd"])
    eth_trend = get_trend_emoji(eth_usd, previous_prices["eth_usd"])
    sol_trend = get_trend_emoji(sol_usd, previous_prices["sol_usd"])
    xrp_trend = get_trend_emoji(xrp_usd, previous_prices["xrp_usd"])

    previous_prices["btc_usd"] = btc_usd
    previous_prices["eth_usd"] = eth_usd
    previous_prices["sol_usd"] = sol_usd
    previous_prices["xrp_usd"] = xrp_usd

    lines = []
    if btc_trend:
        lines.append(f"{btc_trend} $BTC = ${btc_usd:,.2f}")
    if eth_trend:
        lines.append(f"{eth_trend} $ETH = ${eth_usd:,.2f}")
    if sol_trend:
        lines.append(f"{sol_trend} $SOL = ${sol_usd:,.2f}")
    if xrp_trend:
        lines.append(f"{xrp_trend} $XRP = ${xrp_usd:,.4f}")

    if lines:
        price_text = "\n".join(lines)
        
        onchain_info = ""
        if onchain_data["realized_price"]:
            onchain_info += f"\n\n📊 <b>BTC Realized Price:</b> ${onchain_data['realized_price']:,.2f}"
        if onchain_data["delta_price"]:
            onchain_info += f"\n🔻 <b>BTC Delta Price:</b> ${onchain_data['delta_price']:,.2f}"
            
        sentiment_info = ""
        if sentiment_data:
            sentiment_info += f"\n\n{sentiment_data}"

        fiat_info = ""
        if usd_idr:
            fiat_info += f"\n\n💵 <b>USD:</b> IDR {usd_idr:,.2f}"
        if eur_idr:
            fiat_info += f"\n💶 <b>EUR:</b> IDR {eur_idr:,.2f}"
            
        msg = f"{price_text}{onchain_info}{sentiment_info}{fiat_info}\n\n<i>Real time prices update by CoinGecko, BGeometrics & Binance API.</i>"
        
        try:
            await context.bot.send_message(chat_id=TARGET_CHAT_ID, text=msg, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Gagal mengirim pesan: {e}")
        
# --- HANDLER CONVERSION & COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 <b>Bot Konversi & Tracker Crypto Active</b>\n\n"
        "• Update BTC, SOL, XRP dikirim otomatis jika ada pergerakan harga.\n\n"
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
    if not TARGET_CHAT_ID:
        raise ValueError("Error: TARGET_CHAT_ID belum diatur!")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    if app.job_queue:
        app.job_queue.run_repeating(send_price_update, interval=900, first=5)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot berjalan dengan Binance Market Sentiment Public API...")
    app.run_polling()
