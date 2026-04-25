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

BASE = "https://fapi.binance.com"

SCAN_INTERVAL = 60
dynamic_threshold = 20

# сколько максимум сигналов за один цикл
MAX_SIGNALS_PER_CYCLE = 3

# раз в сколько циклов слать статус
STATUS_EVERY = 10

# ==============================
# TELEGRAM
# ==============================

def send(msg):
    for chat_id in CHAT_IDS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={
                    "chat_id": chat_id,
                    "text": str(msg)[:4000]
                },
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
                    data={
                        "chat_id": chat_id,
                        "caption": caption[:1000]
                    },
                    files={"photo": f},
                    timeout=20
                )
        except:
            pass


# ==============================
# BINANCE
# ==============================

def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
        return r.json()
    except:
        return None


def get_24h():
    data = safe_get(BASE + "/fapi/v1/ticker/24hr")
    return data if isinstance(data, list) else []


def get_klines(symbol):
    data = safe_get(
        BASE + "/fapi/v1/klines",
        {
            "symbol": symbol,
            "interval": "15m",
            "limit": 120
        }
    )
    return data if isinstance(data, list) else []


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

        if len(trs) > 14:
            return np.mean(trs[-14:])

        return 0
    except:
        return 0


# ==============================
# FEATURES
# ==============================

def features(row, kl):
    p = float(row["priceChangePercent"])

    closes = np.array([float(x[4]) for x in kl])
    volumes = np.array([float(x[5]) for x in kl])

    vol_fade = (
        volumes[-3:].mean() < volumes[-6:-3].mean()
        if len(volumes) > 6 else False
    )

    breakout = (
        closes[-1] < np.min(closes[-6:-1])
        if len(closes) > 6 else False
    )

    momentum = (
        (closes[-1] - closes[-10]) / closes[-10]
        if len(closes) > 10 else 0
    )

    a = atr(kl)

    regime = 1 if p > 20 and vol_fade else 0

    return p, vol_fade, breakout, momentum, a, regime


# ==============================
# ANALYZE
# ==============================

def analyze(row):
    try:
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

    except:
        return None


# ==============================
# CHART
# ==============================

def chart(symbol, kl):
    try:
        df = pd.DataFrame(kl, columns=[
            "time", "open", "high", "low", "close", "volume",
            "x1", "x2", "x3", "x4", "x5", "x6"
        ])

        df = df[["time", "open", "high", "low", "close", "volume"]]

        df.columns = [
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]

        df["Date"] = pd.to_datetime(df["Date"], unit="ms")
        df.set_index("Date", inplace=True)

        for c in df.columns:
            df[c] = df[c].astype(float)

        file_path = f"chart_{symbol}.png"

        mpf.plot(
            df,
            type="candle",
            volume=True,
            style="charles",
            figsize=(12, 8),
            tight_layout=True,
            savefig=dict(
                fname=file_path,
                dpi=150,
                bbox_inches="tight"
            )
        )

        return file_path

    except:
        return None


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
📉 SHORT SIGNAL
{status}
━━━━━━━━━━━━━━
🪙 {s['symbol']}
🎯 SCORE: {s['score']}
💰 PRICE: {s['price']}
━━━━━━━━━━━━━━
"""


# ==============================
# MAIN
# ==============================

def main():
    send("🚀 BOT STARTED SUCCESSFULLY")

    cycle = 0

    while True:
        try:
            cycle += 1

            data = get_24h()

            if not data:
                send("⚠️ Binance не вернул данные")
                time.sleep(10)
                continue

            # статус раз в N циклов
            if cycle % STATUS_EVERY == 0:
                send(f"✅ BOT ONLINE | Coins: {len(data)}")

            found = 0

            for row in data:
                if found >= MAX_SIGNALS_PER_CYCLE:
                    break

                s = analyze(row)

                if s:
                    found += 1

                    msg = build_message(s)
                    file = chart(s["symbol"], s["kl"])

                    if file:
                        send_photo(file, msg)
                    else:
                        send(msg)

                    time.sleep(1)

            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            send(f"❌ ERROR: {str(e)}")
            time.sleep(10)


if __name__ == "__main__":
    main()
