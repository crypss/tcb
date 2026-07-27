import os
import logging
import requests
import subprocess
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Setup Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
FILE_PATH = "id.txt"

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

# --- FUNGSI BACA & TULIS ID.TXT ---
def load_chat_ids() -> set:
    """Membaca daftar Chat ID dari file id.txt"""
    if not os.path.exists(FILE_PATH):
        return set()
    with open(FILE_PATH, "r") as f:
        lines = f.readlines()
        return {int(line.strip()) for line in lines if line.strip().isdigit()}

def save_and_commit_id(chat_id: int) -> bool:
    """Menyimpan ID ke id.txt dan melakukan Commit + Push ke GitHub"""
    chat_ids = load_chat_ids()
    if chat_id in chat_ids:
        return False  # Sudah terdaftar
    
    chat_ids.add(chat_id)
    
    # 1. Tulis ke file id.txt
    with open(FILE_PATH, "w") as f:
        for cid in chat_ids:
            f.write(f"{cid}\n")
            
    # 2. Push perubahan ke GitHub secara otomatis
    try:
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
        subprocess.run(["git", "add", FILE_PATH], check=True)
        subprocess.run(["git", "commit", "-m", f"auto-update: add chat_id {chat_id} to id.txt"], check=True)
        subprocess.run(["git", "push"], check=True)
        logging.info("Berhasil melakukan commit id.txt ke GitHub!")
    except Exception as e:
        logging.error(f"Gagal push id.txt ke GitHub: {e}")
        
    return True

def remove_and_commit_id(chat_id: int):
    """Menghapus ID dari id.txt dan Commit + Push ke GitHub"""
    chat_ids = load_chat_ids()
    if chat_id not in chat_ids:
        return
    
    chat_ids.remove(chat_id)
    with open(FILE_PATH, "w") as f:
        for cid in chat_ids:
            f.write(f"{cid}\n")
            
    try:
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
        subprocess.run(["git", "add", FILE_PATH], check=True)
        subprocess.run(["git", "commit", "-m", f"auto-update: remove chat_id {chat_id} from id.txt"], check=True)
        subprocess.run(["git", "push"], check=True)
    except Exception as e:
        logging.error(f"Gagal push id.txt ke GitHub: {e}")

# --- FUNGSI HARGA & BOT ---
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
        BotCommand("subscribe", "Aktifkan update harga BTC, SOL, XRP tiap 5 menit"),
        BotCommand("unsubscribe", "Matikan update harga otomatis"),
    ]
    await application.bot.set_my_commands(commands)

# --- JOB MONITORING HARGA (TIAP 5 MENIT) ---
async def send_price_update(context: ContextTypes.DEFAULT_TYPE):
    chat_ids = load_chat_ids()
    if not chat_ids:
        return

    btc_usd = get_crypto_price("btc", "usd")
    btc_idr = get_crypto_price("btc", "idr")
    sol_usd = get_crypto_price("sol", "usd")
    sol_idr = get_crypto_price("sol", "idr")
    xrp_usd = get_crypto_price("xrp", "usd")
    xrp_idr = get_crypto_price("xrp", "idr")

    if btc_usd and sol_usd and xrp_usd:
        msg = (
            "📊 **UPDATE HARGA CRYPTO (Tiap 5 Menit)**\n\n"
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
        
        for chat_id in chat_ids:
            try:
                await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Gagal mengirim pesan ke {chat_id}: {e}")

# --- HANDLER UTAMA ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Bot Konversi & Tracker Crypto**\n\n"
        "• Ketik /subscribe untuk menyimpan ID kamu ke `id.txt` dan menerima update tiap 5 menit.\n"
        "• Ketik /unsubscribe untuk berhenti."
    )

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    is_new = save_and_commit_id(chat_id)
    
    if is_new:
        await update.message.reply_text(f"✅ **Berhasil!** Chat ID `{chat_id}` telah tersimpan ke dalam file `id.txt` di repository GitHub kamu.")
    else:
        await update.message.reply_text("ℹ️ Chat ID kamu sudah ada di dalam daftar `id.txt`.")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    remove_and_commit_id(chat_id)
    await update.message.reply_text("🔕 Chat ID kamu telah dihapus dari file `id.txt`.")

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
        job_queue.run_repeating(send_price_update, interval=300, first=10)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot berjalan...")
    app.run_polling()
