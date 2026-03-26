import requests
import os
from datetime import datetime

# 從環境變數讀取，本機測試可在終端機先 export 設定
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

BINANCE_URL = "https://api.binance.com/api/v3/ticker/price"
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

def fetch_prices():
    prices = {}
    for symbol in SYMBOLS:
        r = requests.get(BINANCE_URL, params={"symbol": symbol}, timeout=10)
        data = r.json()
        if "price" not in data:
            print(f"[ERROR] {symbol} unexpected response: {data}")
            raise KeyError(f"'price' not found in response for {symbol}")
        prices[symbol] = float(data["price"])
    return prices

def send_telegram(message):
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
    }
    r = requests.post(TELEGRAM_URL, json=payload)
    return r.json()

def main():
    prices = fetch_prices()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    message = (
        f"\U0001f4ca 幣安即時報價\n"
        f"BTC：${prices['BTCUSDT']:,.0f} USDT\n"
        f"ETH：${prices['ETHUSDT']:,.2f} USDT\n"
        f"SOL：${prices['SOLUSDT']:,.2f} USDT\n"
        f"\u23f0 {now}"
    )

    result = send_telegram(message)
    if result.get("ok"):
        print("Telegram message sent successfully.")
    else:
        print(f"Failed: {result}")

if __name__ == "__main__":
    main()
