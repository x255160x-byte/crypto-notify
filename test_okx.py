import os, hmac, hashlib, base64, time, requests
from datetime import datetime, timezone

API_KEY    = os.environ['OKX_API_KEY']
SECRET_KEY = os.environ['OKX_SECRET_KEY']
PASSPHRASE = os.environ['OKX_PASSPHRASE']

# OKX 模擬盤 base URL
BASE = "https://www.okx.com"
SIM_HEADER = {"x-simulated-trading": "1"}  # 關鍵：這個 header 讓請求走模擬盤

def sign(timestamp, method, path, body=""):
    msg = f"{timestamp}{method}{path}{body}"
    mac = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

def headers(method, path, body=""):
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    return {
        "OK-ACCESS-KEY":        API_KEY,
        "OK-ACCESS-SIGN":       sign(ts, method, path, body),
        "OK-ACCESS-TIMESTAMP":  ts,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type":         "application/json",
        "x-simulated-trading":  "1",   # 模擬盤
    }

print("=" * 50)
print("  OKX 模擬盤連線測試")
print("=" * 50)

# 測試1：帳戶餘額
print("\n[1] 查詢模擬盤帳戶餘額...")
path = "/api/v5/account/balance"
r = requests.get(BASE + path, headers=headers("GET", path))
data = r.json()
if data.get('code') == '0':
    for d in data['data'][0]['details']:
        if float(d.get('cashBal', 0)) > 0:
            print(f"    {d['ccy']}: {float(d['cashBal']):,.2f}")
    print("    ✅ 帳戶餘額查詢成功")
else:
    print(f"    ❌ 失敗: {data}")

# 測試2：查詢 ETH-USDT-SWAP 最新價格（公開API，不需要簽名）
print("\n[2] 查詢 ETH-USDT-SWAP 市場價格...")
r2 = requests.get(f"{BASE}/api/v5/market/ticker?instId=ETH-USDT-SWAP")
data2 = r2.json()
if data2.get('code') == '0':
    price = float(data2['data'][0]['last'])
    print(f"    ETH-USDT-SWAP 當前價格: ${price:,.2f}")
    print("    ✅ 市場數據查詢成功")
else:
    print(f"    ❌ 失敗: {data2}")

# 測試3：查詢持倉
print("\n[3] 查詢模擬盤持倉...")
path3 = "/api/v5/account/positions?instType=SWAP"
r3 = requests.get(BASE + path3, headers=headers("GET", path3))
data3 = r3.json()
if data3.get('code') == '0':
    positions = [p for p in data3['data'] if float(p.get('pos', 0)) != 0]
    if positions:
        for p in positions:
            print(f"    {p['instId']} | 方向:{p['posSide']} | 數量:{p['pos']}")
    else:
        print("    目前無持倉（正常）")
    print("    ✅ 持倉查詢成功")
else:
    print(f"    ❌ 失敗: {data3}")

# 測試4：查詢K線（EMA99策略需要）
print("\n[4] 查詢 ETH-USDT-SWAP 15分鐘K線（最近5根）...")
r4 = requests.get(f"{BASE}/api/v5/market/candles?instId=ETH-USDT-SWAP&bar=15m&limit=5")
data4 = r4.json()
if data4.get('code') == '0':
    print(f"    取得 {len(data4['data'])} 根K棒")
    latest = data4['data'][0]
    print(f"    最新K棒 - 開:{float(latest[1]):.2f} 高:{float(latest[2]):.2f} 低:{float(latest[3]):.2f} 收:{float(latest[4]):.2f}")
    print("    ✅ K線數據查詢成功")
else:
    print(f"    ❌ 失敗: {data4}")

print("\n" + "=" * 50)
print("  測試完成！如果全部 ✅ 就可以部署機器人")
print("=" * 50)
