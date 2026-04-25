import requests
import time

# ==============================
# CONFIG
# ==============================

TOKEN = "8428200035:AAGj0kOGsbwC_MNtN1Hd1b_mbUpoAXx-MgM"
CHAT_IDS = ["1068636754", 526074717]

BASE = "https://api.mexc.com"

SCAN_INTERVAL = 60
dynamic_threshold = 65

# ==============================
# TELEGRAM SAFE
# ==============================

def send(msg):
    try:
        for chat_id in CHAT_IDS:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": chat_id, "text": msg[:4000]},
                timeout=10
            )
    except Exception as e:
        print("TELEGRAM ERROR:", e)

# ==============================
# SAFE REQUEST
# ==============================

def safe_get(url, params=None):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        r = requests.get(url, params=params, headers=headers, timeout=10)

        if r.status_code != 200:
            print("HTTP ERROR:", r.status_code, r.text[:200])
            return None

        try:
            return r.json()
        except:
            print("JSON PARSE ERROR:", r.text[:200])
            return None

    except Exception as e:
        print("REQUEST ERROR:", e)
        return None

# ==============================
# MARKET DATA
# ==============================

def get_24h():
    data = safe_get(BASE + "/api/v3/ticker/24hr")
    if not isinstance(data, list):
        return []
    return data


def get_klines(symbol):
    data = safe_get(BASE + "/api/v3/klines", {
        "symbol": symbol,
        "interval": "15m",
        "limit": 100
    })

    if not isinstance(data, list):
        return []

    return data

# ==============================
# FEATURE ENGINE (NO CRASH VERSION)
# ==============================

def analyze(row):
    try:
        symbol = row.get("symbol")
        if not symbol or not symbol.endswith("USDT"):
            return None

        price_change = float(row.get("priceChangePercent", 0))

        kl = get_klines(symbol)
        if len(kl) < 50:
            return None

        closes = []
        volumes = []

        for k in kl:
            try:
                closes.append(float(k[4]))
                volumes.append(float(k[5]))
            except:
                continue

        if len(closes) < 20:
            return None

        # ======================
        # FEATURES
        # ======================

        vol_fade = False
        if len(volumes) > 10:
            vol_fade = sum(volumes[-3:]) < sum(volumes[-6:-3])

        breakout = closes[-1] < min(closes[-6:-1])

        momentum = 0
        if len(closes) > 10:
            momentum = (closes[-1] - closes[-10]) / closes[-10]

        regime = price_change > 2 and vol_fade

        # ======================
        # SCORE
        # ======================

        score = 0
        if price_change > 2:
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

        return {
            "symbol": symbol,
            "score": score,
            "price": closes[-1]
        }

    except Exception as e:
        print("ANALYZE ERROR:", e)
        return None

# ==============================
# MESSAGE
# ==============================

def build_message(s):
    if s["score"] >= 85:
        status = "🟢 ELITE"
    elif s["score"] >= 75:
        status = "🔥 STRONG"
    else:
        status = "👀 WATCH"

    return (
        "━━━━━━━━━━━━━━\n"
        "📉 SIGNAL\n"
        f"{status}\n"
        "━━━━━━━━━━━━━━\n"
        f"🪙 {s['symbol']}\n"
        f"🎯 SCORE: {s['score']}\n"
        f"💰 PRICE: {s['price']}\n"
        "━━━━━━━━━━━━━━"
    )

# ==============================
# MAIN LOOP (RAILWAY SAFE)
# ==============================

def main():
    print("BOT STARTED")
    send("🚀 BOT STARTED (SAFE MODE)")

    while True:
        try:
            data = get_24h()

            if not data:
                print("NO MARKET DATA")
                time.sleep(10)
                continue

            for row in data:
                signal = analyze(row)

                if signal:
                    msg = build_message(signal)
                    print("SIGNAL:", signal["symbol"], signal["score"])
                    send(msg)

            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            print("MAIN LOOP ERROR:", e)
            send(f"ERROR: {str(e)}")
            time.sleep(10)

if __name__ == "__main__":
    main()
