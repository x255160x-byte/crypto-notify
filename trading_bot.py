"""
EMA99 穿越策略機器人
- 多空都做 + EMA99斜率過濾
- 止盈：MA45  止損：前25根高低點
- OKX 模擬盤
"""
import os, hmac, hashlib, base64, json, requests
from datetime import datetime, timezone

# ── 設定 ────────────────────────────────────────────
API_KEY    = os.environ['OKX_API_KEY']
SECRET_KEY = os.environ['OKX_SECRET_KEY']
PASSPHRASE = os.environ['OKX_PASSPHRASE']
TG_TOKEN   = os.environ['TELEGRAM_BOT_TOKEN']
TG_CHAT    = os.environ['TELEGRAM_CHAT_ID']

INST_ID  = "ETH-USDT-SWAP"
BAR      = "15m"
RISK_PCT = 0.01
BASE     = "https://www.okx.com"

# ── OKX API ──────────────────────────────────────────
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

def okx_get(path, params=""):
    full = path + (f"?{params}" if params else "")
    r = requests.get(BASE + full, headers=_headers("GET", full), timeout=15)
    return r.json()

def okx_post(path, body: dict):
    body_str = json.dumps(body)
    r = requests.post(BASE + path, headers=_headers("POST", path, body_str),
                      data=body_str, timeout=15)
    return r.json()

# ── Telegram ─────────────────────────────────────────
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
        print(f"  📨 Telegram 已發送")
    except Exception as e:
        print(f"  ⚠️ Telegram 失敗: {e}")

# ── K線與指標 ─────────────────────────────────────────
def get_klines(limit=150):
    r = requests.get(f"{BASE}/api/v5/market/candles",
                     params={"instId": INST_ID, "bar": BAR, "limit": limit},
                     timeout=15)
    data = r.json()
    if data.get('code') != '0':
        raise Exception(f"K線失敗: {data}")
    rows = list(reversed(data['data']))
    return [{'ts': int(x[0]), 'o': float(x[1]), 'h': float(x[2]),
             'l': float(x[3]), 'c': float(x[4])} for x in rows]

def calc(klines):
    closes = [k['c'] for k in klines]
    highs  = [k['h'] for k in klines]
    lows   = [k['l'] for k in klines]
    n = len(closes)

    # MA45
    ma45 = sum(closes[-45:]) / 45 if n >= 45 else None

    # EMA99（完整序列）
    k = 2 / 100
    ema_vals = [closes[0]]
    for c in closes[1:]:
        ema_vals.append(c * k + ema_vals[-1] * (1 - k))

    ema99      = ema_vals[-1]
    ema99_prev = ema_vals[-2]
    ema99_8ago = ema_vals[-9] if len(ema_vals) >= 9 else ema_vals[0]
    slope      = ema99 - ema99_8ago

    # 前25根高低點（不含當根）
    low25  = min(lows[-26:-1])
    high25 = max(highs[-26:-1])

    # 穿越信號
    cross_up   = (closes[-2] < ema99_prev) and (closes[-1] > ema99)
    cross_down = (closes[-2] > ema99_prev) and (closes[-1] < ema99)

    return {
        'close': closes[-1], 'ma45': ma45,
        'ema99': ema99, 'slope': slope,
        'low25': low25, 'high25': high25,
        'cross_up': cross_up, 'cross_down': cross_down,
    }

# ── 帳戶 & 持倉 ───────────────────────────────────────
def get_balance():
    data = okx_get("/api/v5/account/balance")
    if data.get('code') != '0':
        raise Exception(f"餘額失敗: {data}")
    for d in data['data'][0]['details']:
        if d['ccy'] == 'USDT':
            # availEq 有時為空，改用 cashBal 或 eq 作為備援
            val = d.get('availEq') or d.get('cashBal') or d.get('eq') or '0'
            return float(val)
    return 0.0

def get_position():
    data = okx_get("/api/v5/account/positions", f"instId={INST_ID}")
    if data.get('code') != '0':
        return None
    for p in data['data']:
        if p['instId'] == INST_ID and float(p.get('pos', 0)) != 0:
            return {
                'side':   p['posSide'],
                'size':   abs(float(p['pos'])),
                'avg_px': float(p['avgPx']),
            }
    return None

def get_ct_val():
    r = requests.get(f"{BASE}/api/v5/public/instruments",
                     params={"instType": "SWAP", "instId": INST_ID}, timeout=15)
    data = r.json()
    if data.get('code') != '0':
        return 0.01
    return float(data['data'][0]['ctVal'])

# ── 下單 ─────────────────────────────────────────────
def place_order(side, pos_side, sz):
    body = {
        "instId":  INST_ID,
        "tdMode":  "cross",
        "side":    side,
        "posSide": pos_side,
        "ordType": "market",
        "sz":      str(int(sz)),
    }
    data = okx_post("/api/v5/trade/order", body)
    if data.get('code') == '0':
        return data['data'][0]['ordId']
    raise Exception(f"下單失敗: {data}")

def close_pos(pos):
    if pos['side'] == 'long':
        return place_order('sell', 'long', pos['size'])
    return place_order('buy', 'short', pos['size'])

# ── 主邏輯 ───────────────────────────────────────────
def main():
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    print(f"\n{'='*52}")
    print(f"  EMA99 策略機器人 | {now}")
    print(f"{'='*52}")

    klines  = get_klines(150)
    ind     = calc(klines)
    bal     = get_balance()
    pos     = get_position()
    ct_val  = get_ct_val()

    print(f"  ETH:   ${ind['close']:,.2f}")
    print(f"  EMA99: {ind['ema99']:.2f}  斜率: {ind['slope']:+.3f}")
    print(f"  MA45:  {ind['ma45']:.2f if ind['ma45'] else 'N/A'}")
    print(f"  SL多:  {ind['low25']:.2f}  SL空: {ind['high25']:.2f}")
    print(f"  上穿:  {ind['cross_up']}  下穿: {ind['cross_down']}")
    print(f"  USDT:  {bal:,.2f}  持倉: {pos}")

    # ── 出場 ──
    if pos:
        exit_reason = None

        if pos['side'] == 'long':
            if ind['close'] <= ind['low25']:
                exit_reason = ('止損', f"收盤 {ind['close']:.2f} ≤ 前25低 {ind['low25']:.2f}")
            elif ind['ma45'] and ind['close'] <= ind['ma45']:
                exit_reason = ('止盈', f"收盤 {ind['close']:.2f} ≤ MA45 {ind['ma45']:.2f}")

        elif pos['side'] == 'short':
            if ind['close'] >= ind['high25']:
                exit_reason = ('止損', f"收盤 {ind['close']:.2f} ≥ 前25高 {ind['high25']:.2f}")
            elif ind['ma45'] and ind['close'] >= ind['ma45']:
                exit_reason = ('止盈', f"收盤 {ind['close']:.2f} ≥ MA45 {ind['ma45']:.2f}")

        if exit_reason:
            tag, detail = exit_reason
            icon = '✅' if tag == '止盈' else '🛑'
            pnl = (ind['close'] - pos['avg_px']) * pos['size'] * ct_val
            if pos['side'] == 'short': pnl = -pnl
            print(f"\n  {icon} {tag}：{detail}")
            ord_id = close_pos(pos)
            tg(
                f"<b>{icon} {tag}出場</b>\n"
                f"幣對：{INST_ID}\n"
                f"方向：{'多單' if pos['side']=='long' else '空單'}\n"
                f"出場價：{ind['close']:,.2f}\n"
                f"均價：{pos['avg_px']:,.2f}\n"
                f"預估損益：{pnl:+.2f} USDT\n"
                f"原因：{detail}\n"
                f"訂單：{ord_id}\n"
                f"時間：{now}"
            )
            return

    # ── 入場 ──
    if pos is None:
        signal = None
        if ind['cross_up'] and ind['slope'] > 0:
            signal = 'long'
        elif ind['cross_down'] and ind['slope'] < 0:
            signal = 'short'

        if signal:
            sl_price = ind['low25'] if signal == 'long' else ind['high25']
            sl_dist  = abs(ind['close'] - sl_price)
            if sl_dist <= 0:
                print("  ⚠️ 止損距離異常，跳過")
                return

            risk_amt     = bal * RISK_PCT
            sz_contracts = max(1, int((risk_amt / sl_dist) / ct_val))

            side     = 'buy' if signal == 'long' else 'sell'
            pos_side = signal
            icon     = '🟢' if signal == 'long' else '🔴'

            print(f"\n  📡 {icon} {'多單' if signal=='long' else '空單'}信號")
            print(f"  入場: {ind['close']:.2f} | 止損: {sl_price:.2f} | 張數: {sz_contracts}")
            ord_id = place_order(side, pos_side, sz_contracts)
            tg(
                f"<b>📡 {'多單入場 🟢' if signal=='long' else '空單入場 🔴'}</b>\n"
                f"幣對：{INST_ID}\n"
                f"入場價：{ind['close']:,.2f}\n"
                f"止損：{sl_price:,.2f}\n"
                f"止盈目標：MA45 {ind['ma45']:.2f if ind['ma45'] else 'N/A'}\n"
                f"下單：{sz_contracts} 張｜風險：{risk_amt:.1f} USDT\n"
                f"EMA99 斜率：{ind['slope']:+.3f}\n"
                f"訂單：{ord_id}\n"
                f"時間：{now}"
            )
        else:
            print("\n  ⏳ 無信號，等待下次")
    else:
        print(f"\n  📊 持倉中（{pos['side']}），等待出場條件")

if __name__ == "__main__":
    main()
