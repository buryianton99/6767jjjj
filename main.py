import requests
import time
import numpy as np
import pandas as pd
import mplfinance as mpf

# ==============================
# CONFIG
# ==============================

TOKEN = "YOUR_TOKEN"
CHAT_IDS = ["1068636754", "526074717"]

BASE = "https://api.okx.com"  # OKX public API (spot market)

SCAN_INTERVAL = 60
dynamic_threshold = 20

DEBUG = True
HEARTBEAT_INTERVAL = 300  # 5 min

last_heartbeat = 0

# ==============================
# TELEGRAM
# ==============================

def send(msg):
    for chat_id in CHAT_IDS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": chat_id, "text": msg[:4000]},
                timeout=10
            )
        except Exception as e:
            print("Telegram error:", e)

# ==============================
# SAFE REQUEST (VERY IMPORTANT)
# ==============================

def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)

        if DEBUG:
            print("API URL:", r.url)
            print("STATUS:", r.status_code)

        try:
            data = r.json()
        except:
            print("NON-JSON RESPONSE:", r.text[:300])
            return None

        return data

    except Exception as e:
        print("REQUEST ERROR:", e)
        return None

# ==============================
# OKX MARKET DATA
# ==============================

def get_tickers():
    # OKX spot tickers
    data = safe_get(BASE + "/api/v5/market/tickers?instType=SPOT")

    if not data:
        return []

    # OKX returns: {"data":[...]}
    if isinstance(data, dict) and "data" in data:
        return data["data"]

    return []

# ==============================
# FEATURES (simplified but stable)
# ==============================

def features(t):
    try:
        change = float(t.get("24hChange", 0))
        vol = float(t.get("volCcy24h", 0))

        score = 0
        if change > 5:
            score += 30
        if change > 10:
            score += 50
        if vol > 1_000_000:
            score += 10

        return change, vol, score

    except:
        return 0, 0, 0

# ==============================
# ANALYZE
# ==============================

def analyze(t):
    symbol = t.get("instId")

    if not symbol:
        return None

    change, vol, score = features(t)

    if DEBUG:
        print(f"{symbol} change={change} vol={vol} score={score}")

    if score < dynamic_threshold:
        return None

    return {
        "symbol": symbol,
        "score": score,
        "change": change,
        "vol": vol
    }

# ==============================
# MESSAGE
# ==============================

def msg(s):
    return f"""
📡 SIGNAL
{ s['symbol'] }
Score: {s['score']}
Change: {s['change']}
Volume: {s['vol']}
"""

# ==============================
# MAIN
# ==============================

def main():
    global last_heartbeat

    send("🚀 DIAGNOSTIC BOT STARTED")

    while True:
        try:
            tickers = get_tickers()

            if not tickers:
                send("⚠️ NO DATA FROM OKX API")
                time.sleep(10)
                continue

            checked = 0
            signals = 0

            for t in tickers:
                checked += 1
                s = analyze(t)

                if s:
                    signals += 1
                    send(msg(s))

            if DEBUG:
                print(f"Checked: {checked}, Signals: {signals}")

            # heartbeat
            if time.time() - last_heartbeat > HEARTBEAT_INTERVAL:
                send(f"🟢 BOT ALIVE | checked={checked} signals={signals}")
                last_heartbeat = time.time()

            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            send(f"❌ ERROR: {str(e)}")
            print("CRASH:", e)
            time.sleep(10)

if __name__ == "__main__":
    main()
