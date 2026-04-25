import requests
import time
import numpy as np
import pandas as pd
import mplfinance as mpf
import json
import os

# ==============================
# CONFIG
# ==============================

TOKEN = "8428200035:AAGj0kOGsbwC_MNtN1Hd1b_mbUpoAXx-MgM"
CHAT_IDS = ["1068636754", 526074717]

BASE = "https://www.okx.com"

SCAN_INTERVAL = 60
dynamic_threshold = 20

# ==============================
# TELEGRAM
# ==============================

def send(msg):
    try:
        for chat_id in CHAT_IDS:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": chat_id, "text": msg[:4000]},
                timeout=10
            )
    except:
        pass


def send_photo(path, caption=""):
    try:
        for chat_id in CHAT_IDS:
            with open(path, "rb") as f:
                requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                    data={"chat_id": chat_id, "caption": caption[:1000]},
                    files={"photo": f},
                    timeout=20
                )
    except:
        pass

# ==============================
# SAFE REQUEST
# ==============================

def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)

        if r.status_code != 200:
            print("HTTP ERROR:", r.status_code)
            return None

        data = r.json()

        if isinstance(data, dict) and data.get("code"):
            print("API ERROR:", data)
            return None

        return data

    except Exception as e:
        print("REQUEST ERROR:", e)
        return None

# ==============================
# OKX TICKERS
# ==============================

def get_24h():
    url = BASE + "/api/v5/market/tickers?instType=SWAP"
    data = safe_get(url)

    if not data or "data" not in data:
        print("❌ OKX no ticker data")
        return []

    result = []

    for item in data["data"]:
        try:
            symbol = item["instId"].replace("-SWAP", "").replace("-", "")

            # proxy изменения цены (упрощённо)
            result.append({
                "symbol": symbol,
                "priceChangePercent": float(item.get("open24h", 0))
            })
        except:
            continue

    print(f"OKX tickers loaded: {len(result)}")
    return result

# ==============================
# OKX KLINES
# ==============================

def get_klines(symbol):
    inst = symbol.replace("USDT", "-USDT-SWAP")

    url = BASE + "/api/v5/market/candles"
    params = {
        "instId": inst,
        "bar": "15m",
        "limit": 120
    }

    data = safe_get(url, params)

    if not data or "data" not in data:
        return []

    kl = []

    for c in data["data"]:
        try:
            kl.append([
                int(c[0]),  # time
                c[1],       # open
                c[2],       # high
                c[3],       # low
                c[4],       # close
                c[5],       # volume
            ])
        except:
            continue

    return kl[::-1]

# ==============================
# ATR
# ==============================

def atr(kl):
    highs = np.array([float(x[2]) for x in kl])
    lows = np.array([float(x[3]) for x in kl])
    closes = np.array([float(x[4]) for x in kl])

    trs = []
    for i in range(1, len(kl)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        trs.append(tr)

    return np.mean(trs[-14:]) if len(trs) > 14 else 0

# ==============================
# FEATURES
# ==============================

def features(row, kl):
    p = float(row["priceChangePercent"])

    closes = np.array([float(x[4]) for x in kl])
    volumes = np.array([float(x[5]) for x in kl])

    vol_fade = volumes[-3:].mean() < volumes[-6:-3].mean() if len(volumes) > 6 else 0
    breakout = closes[-1] < np.min(closes[-6:-1]) if len(closes) > 6 else 0
    momentum = (closes[-1] - closes[-10]) / closes[-10] if len(closes) > 10 else 0

    a = atr(kl)
    regime = 1 if p > 20 and vol_fade else 0

    return p, vol_fade, breakout, momentum, a, regime

# ==============================
# ANALYZE
# ==============================

def analyze(row):
    symbol = row["symbol"]

    if not symbol.endswith("USDT"):
        return None

    kl = get_klines(symbol)
    if len(kl) < 80:
        return None

    p, vol_fade, breakout, momentum, a, regime = features(row, kl)

    score = 0
    if p > 20: score += 20
    if vol_fade: score += 15
    if breakout: score += 25
    if momentum < 0: score += 10
    if regime: score += 10

    score = max(0, min(100, score))

    if score < dynamic_threshold:
        return None

    price = float(kl[-1][4])

    return {
        "symbol": symbol,
        "score": score,
        "price": round(price, 6),
        "kl": kl
    }

# ==============================
# MESSAGE
# ==============================

def build_message(s):
    if s["score"] >= 85:
        status = "🟢 ЭЛИТНЫЙ"
    elif s["score"] >= 75:
        status = "🔥 СИЛЬНЫЙ"
    else:
        status = "👀 WATCH"

    return f"""
━━━━━━━━━━━━━━
📉 SHORT SIGNAL (OKX)
{status}
━━━━━━━━━━━━━━
🪙 {s['symbol']}
🎯 SCORE: {s['score']}
💰 PRICE: {s['price']}
━━━━━━━━━━━━━━
"""

# ==============================
# MAIN LOOP
# ==============================

def main():
    send("🚀 OKX BOT STARTED SUCCESSFULLY")

    while True:
        try:
            print("Scanning OKX...")

            data = get_24h()

            if not data:
                time.sleep(10)
                continue

            for row in data:
                s = analyze(row)

                if s:
                    msg = build_message(s)
                    send(msg)

            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            print("ERROR:", e)
            send(f"ERROR: {str(e)}")
            time.sleep(10)

if __name__ == "__main__":
    main()
