"""
測試下單：開1張ETH多單，然後馬上平倉
確認 OKX 模擬盤下單功能正常
"""
import os, hmac, hashlib, base64, json, requests
from datetime import datetime, timezone

API_KEY    = os.environ['OKX_API_KEY']
SECRET_KEY = os.environ['OKX_SECRET_KEY']
PASSPHRASE = os.environ['OKX_PASSPHRASE']
TG_TOKEN   = os.environ['TELEGRAM_BOT_TOKEN']
TG_CHAT    = os.environ['TELEGRAM_CHAT_ID']

BASE    = "https://www.okx.com"
INST_ID = "ETH-USDT-SWAP"

def _sign(ts, method, path, body=""):
    msg = f"{ts}{method}{path}{body}"
    mac = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

def _headers(method, path, body=""):
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    return {
        "OK-ACCESS-KEY":        API_KEY,
        "OK-ACCESS-SIGN":       _sign(ts, method, path, body),
        "OK-ACCESS-TIMESTAMP":  ts,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type":         "application/json",
        "x-simulated-trading":  "1",
    }

def okx_post(path, body):
    body_str = json.dumps(body)
    r = requests.post(BASE + path, headers=_headers("POST", path, body_str),
                      data=body_str, timeout=15)
    return r.json()

def okx_get(path, params=""):
    full = path + (f"?{params}" if params else "")
    r = requests.get(BASE + full, headers=_headers("GET", full), timeout=15)
    return r.json()

def tg(msg):
    requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"},
        timeout=10
    )

def get_price():
    r = requests.get(f"{BASE}/api/v5/market/ticker?instId={INST_ID}", timeout=10)
    return float(r.json()['data'][0]['last'])

now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
price = get_price()
print(f"ETH 當前價格: ${price:,.2f}")
print(f"開始測試下單...\n")

# 開1張多單（最小單位）
print("[1] 開多單 1 張...")
buy_body = {
    "instId":  INST_ID,
    "tdMode":  "cross",
    "side":    "buy",
    "posSide": "long",
    "ordType": "market",
    "sz":      "1",
}
buy_res = okx_post("/api/v5/trade/order", buy_body)
print(f"    回應: {buy_res}")

if buy_res.get('code') == '0':
    ord_id = buy_res['data'][0]['ordId']
    print(f"    ✅ 開單成功！訂單ID: {ord_id}")

    # 等1秒確認成交
    import time; time.sleep(1)

    # 馬上平倉
    print("[2] 平倉...")
    sell_body = {
        "instId":  INST_ID,
        "tdMode":  "cross",
        "side":    "sell",
        "posSide": "long",
        "ordType": "market",
        "sz":      "1",
    }
    sell_res = okx_post("/api/v5/trade/order", sell_body)
    print(f"    回應: {sell_res}")

    if sell_res.get('code') == '0':
        close_id = sell_res['data'][0]['ordId']
        print(f"    ✅ 平倉成功！訂單ID: {close_id}")

        tg(
            f"<b>✅ 下單測試成功！</b>\n"
            f"幣對：{INST_ID}\n"
            f"操作：開多1張 → 馬上平倉\n"
            f"ETH價格：${price:,.2f}\n"
            f"開單ID：{ord_id}\n"
            f"平倉ID：{close_id}\n"
            f"時間：{now}\n\n"
            f"🎉 OKX模擬盤下單功能正常！"
        )
        print("\n✅ 測試完成！Telegram 已發送通知")
    else:
        print(f"    ❌ 平倉失敗: {sell_res}")
        tg(f"❌ 測試平倉失敗：{sell_res}")
else:
    print(f"    ❌ 開單失敗: {buy_res}")
    tg(f"❌ 測試開單失敗：{buy_res}")
