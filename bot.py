import os
import requests
import asyncio
from telegram import Bot
from telegram.constants import ParseMode

# Ambil kredensial dari Environment Variables (GitHub Secrets)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TARGET_CHAT_ID")

def get_crypto_prices():
    """Mengambil harga live dan perubahan 24 jam dari CoinGecko"""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin,ethereum,solana,ripple",
        "vs_currencies": "usd",
        "include_24hr_change": "true"
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching CoinGecko data: {e}")
        return None

def get_bgeometrics_metrics():
    """Mengambil metrik on-chain Realized Price & Delta Price dari BGeometrics"""
    headers = {"User-Agent": "Mozilla/5.0"}
    metrics = {"realized_price": None, "delta_price": None}
    
    # Endpoint Realized Price
    try:
        res_realized = requests.get(
            "https://api.bgeometrics.com/v1/bitcoin-realized-price",
            headers=headers,
            timeout=15
        )
        if res_realized.status_code == 200:
            data = res_realized.json()
            # Ambil entri data terbaru
            metrics["realized_price"] = float(data[-1]["value"]) if isinstance(data, list) else float(data.get("value", 0))
    except Exception as e:
        print(f"Error fetching Realized Price: {e}")

    # Endpoint Delta Price
    try:
        res_delta = requests.get(
            "https://api.bgeometrics.com/v1/bitcoin-delta-price",
            headers=headers,
            timeout=15
        )
        if res_delta.status_code == 200:
            data = res_delta.json()
            metrics["delta_price"] = float(data[-1]["value"]) if isinstance(data, list) else float(data.get("value", 0))
    except Exception as e:
        print(f"Error fetching Delta Price: {e}")

    return metrics

def format_message(prices, metrics):
    """Menyusun teks pesan dengan format HTML"""
    btc_price = prices.get("bitcoin", {}).get("usd", 0)
    btc_change = prices.get("bitcoin", {}).get("usd_24h_change", 0)
    eth_price = prices.get("ethereum", {}).get("usd", 0)
    eth_change = prices.get("ethereum", {}).get("usd_24h_change", 0)
    sol_price = prices.get("solana", {}).get("usd", 0)
    sol_change = prices.get("solana", {}).get("usd_24h_change", 0)
    xrp_price = prices.get("ripple", {}).get("usd", 0)
    xrp_change = prices.get("ripple", {}).get("usd_24h_change", 0)

    arrow = lambda c: "🟢 +" if c >= 0 else "🔴 "

    msg = "📊 <b>UPDATE PASAR KRIPTO</b>\n\n"
    msg += f"• <b>BTC:</b> ${btc_price:,.2f} ({arrow(btc_change)}{btc_change:.2f}%)\n"
    msg += f"• <b>ETH:</b> ${eth_price:,.2f} ({arrow(eth_change)}{eth_change:.2f}%)\n"
    msg += f"• <b>SOL:</b> ${sol_price:,.2f} ({arrow(sol_change)}{sol_change:.2f}%)\n"
    msg += f"• <b>XRP:</b> ${xrp_price:,.4f} ({arrow(xrp_change)}{xrp_change:.2f}%)\n\n"

    msg += "⛓ <b>On-Chain Metrics (BTC)</b>\n"
    if metrics.get("realized_price"):
        msg += f"• <b>Realized Price:</b> ${metrics['realized_price']:,.2f}\n"
    if metrics.get("delta_price"):
        msg += f"• <b>Delta Price:</b> ${metrics['delta_price']:,.2f}\n"

    # Evaluasi status peringatan jika harga di bawah Realized Price
    realized = metrics.get("realized_price")
    if realized and btc_price < realized:
        msg += "\n⚠️ <b>Peringatan:</b> Harga BTC berada di bawah Realized Price (Undervalued Zone)!"

    return msg

async def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID belum disetel di Secrets.")
        return

    prices = get_crypto_prices()
    metrics = get_bgeometrics_metrics()

    if not prices:
        print("Gagal mengambil data harga. Pengiriman pesan dibatalkan.")
        return

    message = format_message(prices, metrics)

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=message,
        parse_mode=ParseMode.HTML
    )
    print("Pesan pemantauan berhasil dikirim.")

if __name__ == "__main__":
    asyncio.run(main())
