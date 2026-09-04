import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Setup Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")
COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY")

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

# --- API COINGLASS LIQUIDATION MAP V4 ---
def get_coinglass_liquidation_analysis(current_btc_price: float):
    if not COINGLASS_API_KEY:
        return "⚠️ API Key Coinglass belum diatur."
        
    url = "https://open-api-v4.coinglass.com/api/futures/liquidation/map"
    headers = {
        "CG-API-KEY": COINGLASS_API_KEY,
        "accept": "application/json"
    }
    params = {
        "exchange": "Binance",
        "symbol": "BTCUSDT",
        "range": "1d"
    }
    
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code == 200:
            res_data = res.json()
            if str(res_data.get("code")) == "0" or res_data.get("success") == True:
                liq_data = res_data.get("data", [])
                
                total_long_below = 0.0
                total_short_above = 0.0
                
                if isinstance(liq_data, list):
                    for item in liq_data:
                        try:
                            p = float(item.get("price", item.get("h", 0)))
                            vol = float(item.get("vol", item.get("value", item.get("l", 0))))
                            
                            if p > 0:
                                if p < current_btc_price:
                                    total_long_below += vol
                                elif p > current_btc_price:
                                    total_short_above += vol
                        except (ValueError, TypeError, AttributeError):
                            continue
                elif isinstance(liq_data, dict):
                    for price_str, val in liq_data.items():
                        try:
                            p = float(price_str)
                            v = float(val) if not isinstance(val, (list, dict)) else float(val[0])
                            if p < current_btc_price:
                                total_long_below += v
                            elif p > current_btc_price:
                                total_short_above += v
                        except (ValueError, TypeError, IndexError):
                            continue

                if total_long_below > 0 or total_short_above > 0:
                    total_all = total_long_below + total_short_above
                    long_pct = (total_long_below / total_all) * 100
                    short_pct = (total_short_above / total_all) * 100
                    
                    if total_long_below > total_short_above:
                        return f"🔥 <b>BTC Liq Heatmap:</b> Zona Panas di Bawah (Longs Tebal)\n📉 <i>Likuiditas: {long_pct:.1f}% di bawah vs {short_pct:.1f}% di atas. Potensi market turun menjemput bawah!</i>"
                    else:
                        return f"🔥 <b>BTC Liq Heatmap:</b> Zona Panas di Atas (Shorts Tebal)\n📈 <i>Likuiditas: {short_pct:.1f}% di atas vs {long_pct:.1f}% di bawah. Potensi market naik menjemput atas!</i>"
                else:
                    return "🔥 <b>BTC Liq Heatmap:</b> Data API Terbaca (Aktivitas Normal)"
            else:
                msg_err = res_data.get("msg", "Unknown error")
                return f"🔥 <b>BTC Liq Heatmap:</b> API Respon Gagal ({msg_err})"
    except Exception as e:
        logging.error(f"Error Request Coinglass Liquidation Map: {e}")
        
    return "🔥 <b>BTC Liq Heatmap:</b> Gagal memproses data rincian"

# --- JOB PERIODIK ---
async def send_price_update(context: ContextTypes.DEFAULT_TYPE):
    global previous_prices
    
    data = get_multiple_prices()
    onchain_data = get_bgeometrics_metrics()
    
    usd_idr = get_fiat_rate("usd", "idr")
    eur_idr = get_fiat_rate("eur", "idr")

    if not data:
        logging.warning("Gagal mengambil data harga, melewati siklus ini.")
        return

    btc_usd = data.get("bitcoin", {}).get("usd", 0)
    eth_usd = data.get("ethereum", {}).get("usd", 0)
    sol_usd = data.get("solana", {}).get("usd", 0)
    xrp_usd = data.get("ripple", {}).get("usd", 0)

    coinglass_analysis = get_coinglass_liquidation_analysis(btc_usd)

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
            
        liquidation_info = ""
        if coinglass_analysis:
            liquidation_info += f"\n\n{coinglass_analysis}"

        fiat_info = ""
        if usd_idr:
            fiat_info += f"\n\n💵 <b>USD:</b> IDR {usd_idr:,.2f}"
        if eur_idr:
            fiat_info += f"\n💶 <b>EUR:</b> IDR {eur_idr:,.2f}"
            
        msg = f"{price_text}{onchain_info}{liquidation_info}{fiat_info}\n\n<i>Real time prices update by CoinGecko, BGeometrics & Coinglass.</i>"
        
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
        app.job_queue.run_repeating(send_price_update, interval=60, first=5)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot berjalan dengan integrasi lengkap Coinglass v4...")
    app.run_polling()
