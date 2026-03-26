import requests
import os
from datetime import datetime

# 從環境變數讀取，本機測試可在終端機先 export 設定
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

OKX_URL = "https://www.okx.com/api/v5/market/ticker"
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

SYMBOLS = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]

def fetch_prices():
    prices = {}
    for inst_id in SYMBOLS:
        r = requests.get(OKX_URL, params={"instId": inst_id}, timeout=10)
        data = r.json()
        if not data.get("data"):
            print(f"[ERROR] {inst_id} unexpected response: {data}")
            raise KeyError(f"'data' not found in response for {inst_id}")
        prices[inst_id] = float(data["data"][0]["last"])
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
        f"\U0001f4ca OKX 即時報價\n"
        f"BTC：${prices['BTC-USDT']:,.0f} USDT\n"
        f"ETH：${prices['ETH-USDT']:,.2f} USDT\n"
        f"SOL：${prices['SOL-USDT']:,.2f} USDT\n"
        f"\u23f0 {now}"
    )

    result = send_telegram(message)
    if result.get("ok"):
        print("Telegram message sent successfully.")
    else:
        print(f"Failed: {result}")

if __name__ == "__main__":
    main()
