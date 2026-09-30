import os
import sys
import time
import requests

# --- CONFIGURATION ---
STATE_FILE = "alarm_state.txt"
UNTERE_GRENZE = 3
OBERE_GRENZE = 62
NIGHT_PROZENT = 2  # Mindest-Preisanstieg in % für den $NIGHT-Preisalarm

# NIGHT-SNEK Pool auf Minswap
POOL_ID = "f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c3b3318a251bb71f8345c5affcd29645af2f56859eea740bec2a27c91027cb01d"
MINSWAP_API_URL = f"https://api-mainnet-prod.minswap.org/v1/pools/{POOL_ID}/metrics"

NIGHT_PREIS_STATE_FILE = "nightpreis.txt"

# NIGHT-ADA Pool auf Minswap (mit USD-Währungsparameter)
NIGHT_ADA_POOL_ID = "f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4ce74c52975908a612d5ce68327040d449aae99f8b463bb6de046a1b23c5713169"
NIGHT_ADA_API_URL = f"https://api-mainnet-prod.minswap.org/v1/pools/{NIGHT_ADA_POOL_ID}/metrics?currency=usd"

# --- GITHUB SECRETS AUSLESEN ---
PUSHOVER_USER_KEY = os.environ.get("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.environ.get("PUSHOVER_API_TOKEN")

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Cache-Control": "no-cache"
}


def send_push_notification(message):
    print("Sende Push-Nachricht via Pushover...")
    url = "https://api.pushover.net/1/messages.json"
    data = {
        "token": PUSHOVER_API_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "message": message
    }
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("Push-Benachrichtigung erfolgreich gesendet!")
        else:
            print(f"Fehler bei Pushover: {response.text}")
    except Exception as e:
        print(f"Fehler beim Senden der Push-Nachricht: {e}")


def load_last_alert_threshold():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                content = f.read().strip()
                if content:
                    return int(content)
        except Exception as e:
            print(f"Fehler beim Lesen der Statusdatei: {e}")
    return None


def save_alert_threshold(value):
    try:
        with open(STATE_FILE, "w") as f:
            f.write(str(int(value)))
        print(f"Neuen Schwellenwert gespeichert: {int(value)}")
    except Exception as e:
        print(f"Fehler beim Schreiben der Statusdatei: {e}")


def clear_alert_state():
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
            print("Kurs wieder im Normalbereich. Alarm-Gedächtnis zurückgesetzt.")
        except Exception as e:
            print(f"Fehler beim Löschen der Statusdatei: {e}")


def get_night_snek_ratio():
    """Fragt den NIGHT-SNEK-Pool bei Minswap ab und berechnet das Verhältnis 1 NIGHT = X SNEK."""
    print("Rufe NIGHT/SNEK Pool-Daten von der Minswap API ab...")
    response = requests.get(MINSWAP_API_URL, headers=REQUEST_HEADERS, timeout=10)

    if response.status_code != 200:
        raise RuntimeError(f"API-Fehler {response.status_code}: {response.text}")

    data = response.json()
    asset_a_ticker = data["asset_a"]["metadata"]["ticker"]
    asset_b_ticker = data["asset_b"]["metadata"]["ticker"]
    liquidity_a = data["liquidity_a"]
    liquidity_b = data["liquidity_b"]

    print(f"Pool-Zusammensetzung: {asset_a_ticker} ({liquidity_a}) / {asset_b_ticker} ({liquidity_b})")

    if asset_a_ticker == "NIGHT" and asset_b_ticker == "SNEK":
        return liquidity_b / liquidity_a
    elif asset_a_ticker == "SNEK" and asset_b_ticker == "NIGHT":
        return liquidity_a / liquidity_b
    else:
        raise RuntimeError(f"Unerwartete Zusammensetzung: {asset_a_ticker}/{asset_b_ticker}")


def check_crypto_prices():
    print("Starte Preisabfrage via Minswap API...")
    try:
        ratio = get_night_snek_ratio()
        print(f"Aktuelles Verhältnis: 1 NIGHT = {ratio:.2f} SNEK")

        int_ratio = int(ratio)
        last_alerted = load_last_alert_threshold()
        print(f"Zuletzt alarmierter Wert im Speicher: {last_alerted}")

        if int_ratio > OBERE_GRENZE:
            if last_alerted is None or int_ratio > last_alerted:
                msg = f"📈 Krypto-Alarm (Steigt)! Verhältnis bei 1 NIGHT = {ratio:.2f} SNEK!"
                send_push_notification(msg)
                save_alert_threshold(int_ratio)
            else:
                print(f"Verhältnis ({int_ratio}) ist nicht höher als der letzte Alarm ({last_alerted}). Kein Spam.")

        elif int_ratio < UNTERE_GRENZE:
            if last_alerted is None or int_ratio < last_alerted:
                msg = f"📉 Krypto-Alarm (Fällt)! Verhältnis bei 1 NIGHT = {ratio:.2f} SNEK!"
                send_push_notification(msg)
                save_alert_threshold(int_ratio)
            else:
                print(f"Verhältnis ({int_ratio}) ist nicht tiefer als der letzte Alarm ({last_alerted}). Kein Spam.")

        else:
            print("Verhältnis im Normalbereich. Kein Alarm gesendet.")
            if last_alerted is not None:
                clear_alert_state()

    except Exception as e:
        print(f"Fehler bei der API-Abfrage: {e}")


# =====================================================================
# LIVE $NIGHT USD-PREISABFRAGE
# =====================================================================

def get_night_usd_price():
    """
    Holt den offiziellen Live-Preis für NIGHT direkt von Minswap.
    Weg 1: Minswap Asset-Index (wie auf minswap.org angezeigt)
    Weg 2 (Fallback): NIGHT/ADA Pool mit Währungsumrechnung in USD
    """
    # Weg 1: Offizieller Minswap Asset-Katalog
    try:
        url = "https://api-mainnet-prod.minswap.org/v1/assets?term=NIGHT&limit=10"
        res = requests.get(url, headers=REQUEST_HEADERS, timeout=8)
        if res.status_code == 200:
            assets = res.json().get("assets", [])
            for item in assets:
                meta = item.get("metadata") or {}
                if meta.get("ticker") == "NIGHT" and item.get("price"):
                    price_usd = float(item["price"])
                    print(f"Live $NIGHT-Preis direkt von Minswap Asset-Index: ${price_usd:.6f}")
                    return price_usd
    except Exception as e:
        print(f"Asset-Index Abfrage übersprungen: {e}")

    # Weg 2: NIGHT/ADA Pool mit expliziter USD-Bewertung
    print("Rufe NIGHT/ADA Pool-Daten mit Währung USD ab...")
    res = requests.get(NIGHT_ADA_API_URL, headers=REQUEST_HEADERS, timeout=8)
    if res.status_code == 200:
        data = res.json()
        # Bei currency=usd liefert Minswap die Tokenwerte direkt in USD
        asset_a = data.get("asset_a", {})
        ticker_a = (asset_a.get("metadata") or {}).get("ticker")
        
        # Minswap liefert den Tokenpreis direkt im Pool-Metrics-Objekt
        if "price" in data and data["price"]:
            price = float(data["price"])
            print(f"Pool-Spotpreis (USD): ${price:.6f}")
            return price

        # Fallback: USD-Liquidität geteilt durch Token-Menge
        liq_total = data.get("liquidity_raw", 0)
        liq_night = data.get("liquidity_a" if ticker_a == "NIGHT" else "liquidity_b", 0)
        if liq_total > 0 and liq_night > 0:
            # Im Pool entspricht die Hälfte des TVL dem NIGHT-Wert
            price_usd = (liq_total / 2.0) / liq_night
            print(f"Berechneter Pool-USD-Preis: ${price_usd:.6f}")
            return price_usd

    raise RuntimeError("Konnte den NIGHT USD-Preis über keinen Minswap-Endpunkt ermitteln.")


def load_last_night_price():
    if os.path.exists(NIGHT_PREIS_STATE_FILE):
        try:
            with open(NIGHT_PREIS_STATE_FILE, "r") as f:
                content = f.read().strip()
                if content:
                    return float(content)
        except Exception as e:
            print(f"Fehler beim Lesen der NIGHT-Preisdatei: {e}")
    return None


def save_night_price(value):
    try:
        with open(NIGHT_PREIS_STATE_FILE, "w") as f:
            f.write(str(value))
        print(f"Neuer NIGHT-Referenzpreis gespeichert: {value}")
    except Exception as e:
        print(f"Fehler beim Schreiben der NIGHT-Preisdatei: {e}")


def check_night_price():
    print("Starte $NIGHT-Preisabfrage via Minswap...")
    try:
        aktueller_preis = get_night_usd_price()
        print(f"Aktueller $NIGHT-Preis: ${aktueller_preis:.6f}")

        letzter_preis = load_last_night_price()
        if letzter_preis is None:
            print("Noch kein Referenzwert vorhanden. Lege nightpreis.txt neu an.")
            save_night_price(aktueller_preis)
            return

        print(f"Gespeicherter Referenzpreis: ${letzter_preis:.6f}")
        veraenderung_prozent = ((aktueller_preis - letzter_preis) / letzter_preis) * 100

        if veraenderung_prozent >= NIGHT_PROZENT:
            msg = (
                f"$Night um {veraenderung_prozent:.2f}% gestiegen von "
                f"${letzter_preis:.6f} auf ${aktueller_preis:.6f}"
            )
            send_push_notification(msg)
            save_night_price(aktueller_preis)
        elif veraenderung_prozent > 0:
            print(
                f"Preis ist um {veraenderung_prozent:.2f}% gestiegen, "
                f"das liegt unter der Schwelle von {NIGHT_PROZENT}%. Kein Alarm, kein Update."
            )
        else:
            print(
                f"Preis ist gefallen oder gleich geblieben ({veraenderung_prozent:.2f}%). "
                f"Kein Alarm, Referenzwert bleibt unverändert."
            )

    except Exception as e:
        print(f"Fehler bei der $NIGHT-Preisabfrage: {e}")


if __name__ == "__main__":
    print("=== SKRIPT-DURCHLAUF START ===")
    check_crypto_prices()
    check_night_price()
    print("=== SKRIPT-DURCHLAUF BEENDET ===")
    sys.exit(0)
