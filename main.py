import requests
import time
import numpy as np
import pandas as pd
import mplfinance as mpf
import os

# ==============================
# CONFIG
# ==============================

TOKEN = "8428200035:AAGj0kOGsbwC_MNtN1Hd1b_mbUpoAXx-MgM"
CHAT_IDS = ["1068636754", "526074717"]

BASE = "https://fstream.binance.com"

SCAN_INTERVAL = 60
dynamic_threshold = 20

# ==============================
# TELEGRAM
# ==============================

def send(msg):
    for chat_id in CHAT_IDS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": chat_id, "text": str(msg)[:4000]},
                timeout=10
            )
        except:
            pass


def send_photo(path, caption=""):
    for chat_id in CHAT_IDS:
        try:
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
# SAFE REQUEST (С ДИАГНОСТИКОЙ)
# ==============================

def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)

        # 🔥 ДИАГНОСТИКА
        print("REQUEST:", r.url)
        print("STATUS:", r.status_code)
        print("TEXT (first 200):", r.text[:200])

        # если не 200 — сразу видно проблему
        if r.status_code != 200:
            return None

        return r.json()

    except Exception as e:
        print("REQUEST ERROR:", str(e))
        return None


# ==============================
# BINANCE
# ==============================

def get_24h():
    data = safe_get(BASE + "/fapi/v1/ticker/24hr")

    if not isinstance(data, list):
        print("❌ Binance 24h data is invalid:", type(data))
        return []

    return data


def get_klines(symbol):
    data = safe_get(
        BASE + "/fapi/v1/klines",
        {"symbol": symbol, "interval": "15m", "limit": 120}
    )

    if not isinstance(data, list):
        return []

    return data


# ==============================
# ATR
# ==============================

def atr(kl):
    try:
        highs = np.array([float(x[2]) for x in kl])
        lows = np.array([float(x[3]) for x in kl])
        closes = np.array([float(x[4]) for x in kl])

        trs = []

        for i in range(1, len(kl)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )
            trs.append(tr)

        return np.mean(trs[-14:]) if len(trs) > 14 else 0

    except:
        return 0


# ==============================
# FEATURES
# ==============================

def features(row, kl):
    p = float(row["priceChangePercent"])

    closes = np.array([float(x[4]) for x in kl])
    volumes = np.array([float(x[5]) for x in kl])

    vol_fade = volumes[-3:].mean() < volumes[-6:-3].mean() if len(volumes) > 6 else False
    breakout = closes[-1] < np.min(closes[-6:-1]) if len(closes) > 6 else False
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

    if p > 20:
        score += 20
    if vol_fade:
        score += 15
    if breakout:
        score += 25
    if momentum < 0:
        score += 10
    if regime:
        score += 10

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
# MAIN LOOP
# ==============================

def main():
    send("🚀 BOT STARTED + DIAGNOSTIC MODE")

    while True:
        try:
            data = get_24h()

            # 🔥 ДИАГНОСТИКА
            send(f"📊 Coins received: {len(data)}")

            if not data:
                send("❌ No data from Binance (API blocked or down)")
                time.sleep(10)
                continue

            found = 0

            for row in data:
                if found >= 3:
                    break

                s = analyze(row)

                if s:
                    found += 1

                    msg = f"""
━━━━━━━━━━━━━━
📉 SIGNAL FOUND
🪙 {s['symbol']}
🎯 SCORE: {s['score']}
💰 PRICE: {s['price']}
━━━━━━━━━━━━━━
"""

                    send(msg)

            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            send(f"❌ ERROR: {str(e)}")
            time.sleep(10)


if __name__ == "__main__":
    main()
