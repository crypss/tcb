import asyncio
import json
import logging
import os
import requests
from telegram import Bot

# Setup Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("TELEGRAM_TOKEN")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")
PRICE_FILE = "last_prices.json"


# --- MANAJEMEN PENYIMPANAN HARGA DENGAN FILE ---
def load_previous_prices():
  """Membaca harga terakhir dari file JSON lokal"""
  if os.path.exists(PRICE_FILE):
    try:
      with open(PRICE_FILE, "r") as f:
        return json.load(f)
    except Exception as e:
      logging.error(f"Gagal membaca {PRICE_FILE}: {e}")
  return {"btc_usd": None, "eth_usd": None, "sol_usd": None, "xrp_usd": None}


def save_current_prices(prices):
  """Menyimpan harga saat ini ke file JSON lokal"""
  try:
    with open(PRICE_FILE, "w") as f:
      json.dump(prices, f)
  except Exception as e:
    logging.error(f"Gagal menyimpan ke {PRICE_FILE}: {e}")


def get_trend_emoji(current, previous):
  """Menentukan tren naik (🟢), turun (🔴), atau tetap/awal (⚪)"""
  if previous is None or current == previous:
    return "⚪"
  elif current > previous:
    return "🟢"
  else:
    return "🔴"


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
  metrics = {"realized_price": None, "delta_price": None}

  try:
    res = requests.get(f"{base_url}realized_price.json", timeout=10)
    if res.status_code == 200:
      data = res.json()
      if data and len(data) > 0:
        for entry in reversed(data):
          if len(entry) > 1 and entry[1] is not None:
            metrics["realized_price"] = float(entry[1])
            break
  except Exception as e:
    logging.error(f"Error Request Realized Price: {e}")

  try:
    res = requests.get(f"{base_url}delta_cap.json", timeout=10)
    if res.status_code == 200:
      data = res.json()
      if data and len(data) > 0:
        for entry in reversed(data):
          if len(entry) > 1 and entry[1] is not None:
            metrics["delta_price"] = float(entry[1])
            break
  except Exception as e:
    logging.error(f"Error Request Delta Price: {e}")

  return metrics


# --- EKSEKUSI PENGIRIMAN PESAN ---
async def send_update():
  prev_prices = load_previous_prices()
  data = get_multiple_prices()
  onchain_data = get_bgeometrics_metrics()
  usd_idr = get_fiat_rate("usd", "idr")
  eur_idr = get_fiat_rate("eur", "idr")

  if not data:
    logging.warning(
        "Gagal mengambil data harga dari CoinGecko, membatalkan pengiriman."
    )
    return

  btc_usd = data.get("bitcoin", {}).get("usd", 0)
  eth_usd = data.get("ethereum", {}).get("usd", 0)
  sol_usd = data.get("solana", {}).get("usd", 0)
  xrp_usd = data.get("ripple", {}).get("usd", 0)

  # Deteksi Tren Naik / Turun
  btc_trend = get_trend_emoji(btc_usd, prev_prices.get("btc_usd"))
  eth_trend = get_trend_emoji(eth_usd, prev_prices.get("eth_usd"))
  sol_trend = get_trend_emoji(sol_usd, prev_prices.get("sol_usd"))
  xrp_trend = get_trend_emoji(xrp_usd, prev_prices.get("xrp_usd"))

  # Cek apakah ini pertama kali sistem jalan (semua prev_prices masih None)
  is_first_run = prev_prices.get("btc_usd") is None

  # Simpan harga terbaru ke file lokal untuk eksekusi berikutnya
  save_current_prices({
      "btc_usd": btc_usd,
      "eth_usd": eth_usd,
      "sol_usd": sol_usd,
      "xrp_usd": xrp_usd,
  })

  lines = []
  # Tampilkan baris jika: First run ATAU harganya bergerak (naik/turun)
  if is_first_run or btc_trend != "⚪":
    lines.append(f"{btc_trend} $BTC = ${btc_usd:,.2f}")
  if is_first_run or eth_trend != "⚪":
    lines.append(f"{eth_trend} $ETH = ${eth_usd:,.2f}")
  if is_first_run or sol_trend != "⚪":
    lines.append(f"{sol_trend} $SOL = ${sol_usd:,.2f}")
  if is_first_run or xrp_trend != "⚪":
    lines.append(f"{xrp_trend} $XRP = ${xrp_usd:,.4f}")

  # Jika bukan eksekusi pertama DAN tidak ada pergerakan harga sama sekali, lewati pesan
  if not lines:
    logging.info(
        "Tidak ada perubahan harga pada BTC, ETH, SOL, maupun XRP. Pesan"
        " dilewati."
    )
    return

  price_text = "\n".join(lines)

  onchain_info = ""
  if onchain_data["realized_price"]:
    onchain_info += (
        f"\n\n<b>BTC Realized Price:</b> ${onchain_data['realized_price']:,.2f}"
    )
  if onchain_data["delta_price"]:
    onchain_info += (
        f"\n<b>BTC Delta Price:</b> ${onchain_data['delta_price']:,.2f}"
    )

  fiat_info = ""
  if usd_idr:
    fiat_info += f"\n<b>USD Price:</b> IDR {usd_idr:,.2f}"
  if eur_idr:
    fiat_info += f"\n<b>EUR Price:</b> IDR {eur_idr:,.2f}"

  msg = (
      f"{price_text}{onchain_info}{fiat_info}\n\n<i>Real time prices update by"
      " CoinGecko & BGeometrics.</i>"
  )

  bot = Bot(token=TOKEN)
  await bot.send_message(chat_id=TARGET_CHAT_ID, text=msg, parse_mode="HTML")
  logging.info("Pesan update berhasil dikirim ke Telegram!")


if __name__ == "__main__":
  if not TOKEN:
    raise ValueError("Error: TELEGRAM_TOKEN belum diatur!")
  if not TARGET_CHAT_ID:
    raise ValueError("Error: TARGET_CHAT_ID belum diatur!")

  asyncio.run(send_update())
