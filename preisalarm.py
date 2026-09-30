import os
import sys
import time
import requests

# --- CONFIGURATION ---
STATE_FILE = "alarm_state.txt"
UNTERE_GRENZE = 3
OBERE_GRENZE = 62
NIGHT_PROZENT = 2  # Mindest-Preisanstieg in % für den $NIGHT-Preisalarm

# NIGHT-SNEK Pool auf Minswap (LP Policy-ID + LP Token-Name)
POOL_ID = "f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c3b3318a251bb71f8345c5affcd29645af2f56859eea740bec2a27c91027cb01d"
# WICHTIG: Kein "/metrics" am Ende, damit die Live-Reserven geliefert werden!
MINSWAP_API_URL = f"https://api-mainnet-prod.minswap.org/v1/pools/{POOL_ID}"

# $NIGHT-Preis-Ermittlung über zwei liquidere Pools statt des dünnen NIGHT/USDM-Pools:
# 1 NIGHT in USD = (NIGHT/ADA-Kurs) * (ADA/USDM-Kurs)
NIGHT_PREIS_STATE_FILE = "nightpreis.txt"

# NIGHT-ADA Pool auf Minswap
NIGHT_ADA_POOL_ID = "f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4ce74c52975908a612d5ce68327040d449aae99f8b463bb6de046a1b23c5713169"
NIGHT_ADA_API_URL = f"https://api-mainnet-prod.minswap.org/v1/pools/{NIGHT_ADA_POOL_ID}"

# ADA-USDM Pool auf Minswap
ADA_USDM_POOL_ID = "f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c7dd6988c5a86693c76aeec1ea94afa41770be0de21a775ca7a2a1eabdb6a0171"
ADA_USDM_API_URL = f"https://api-mainnet-prod.minswap.org/v1/pools/{ADA_USDM_POOL_ID}"

# --- GITHUB SECRETS AUSLESEN ---
PUSHOVER_USER_KEY = os.environ.get("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.environ.get("PUSHOVER_API_TOKEN")

# HTTP-Header zur Vermeidung von CDN-/Proxy-Caching
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache"
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
    """Lädt den letzten alarmierten Schwellenwert aus der Datei"""
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
    """Speichert den aktuellen Schwellenwert"""
    try:
        with open(STATE_FILE, "w") as f:
            f.write(str(int(value)))
        print(f"Neuen Schwellenwert gespeichert: {int(value)}")
    except Exception as e:
        print(f"Fehler beim Schreiben der Statusdatei: {e}")


def clear_alert_state():
    """Löscht den Zustand, wenn der Kurs wieder im Normalbereich ist"""
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
            print("Kurs wieder im Normalbereich. Alarm-Gedächtnis zurückgesetzt.")
        except Exception as e:
            print(f"Fehler beim Löschen der Statusdatei: {e}")


def extract_pool_data(data):
    """
    Parst flexibel sowohl das direkte Pool-Objekt als auch ein geschachteltes Metrics-Objekt
    und berücksichtigt die korrekten Dezimalstellen.
    """
    asset_a = data.get("asset_a", {})
    asset_b = data.get("asset_b", {})

    meta_a = asset_a.get("metadata") or {}
    meta_b = asset_b.get("metadata") or {}

    ticker_a = meta_a.get("ticker") or ("ADA" if asset_a.get("currency_symbol") == "" else "TOKEN_A")
    ticker_b = meta_b.get("ticker") or ("ADA" if asset_b.get("currency_symbol") == "" else "TOKEN_B")

    decimals_a = int(meta_a.get("decimals", 6 if ticker_a == "ADA" else 0))
    decimals_b = int(meta_b.get("decimals", 6 if ticker_b == "ADA" else 0))

    # Unterstützt sowohl die Felder des direkten Pool-Endpunkts (quantity) als auch von metrics (liquidity)
    qty_a = float(data.get("quantity_a") or data.get("reserve_a") or data.get("liquidity_a") or 0)
    qty_b = float(data.get("quantity_b") or data.get("reserve_b") or data.get("liquidity_b") or 0)

    # Falls Rohmengen (Integer) vorliegen, auf Dezimalstellen skalieren
    if "liquidity_a" not in data and decimals_a > 0:
        qty_a = qty_a / (10 ** decimals_a)
    if "liquidity_b" not in data and decimals_b > 0:
        qty_b = qty_b / (10 ** decimals_b)

    return ticker_a, ticker_b, qty_a, qty_b


def get_night_snek_ratio():
    """Fragt den NIGHT-SNEK-Pool bei Minswap ab und berechnet das Verhältnis 1 NIGHT = X SNEK."""
    print("Rufe Pool-Daten von der Minswap API ab...")
    params = {"_t": int(time.time())}
    response = requests.get(MINSWAP_API_URL, headers=REQUEST_HEADERS, params=params, timeout=10)

    if response.status_code != 200:
        raise RuntimeError(f"API-Fehler {response.status_code}: {response.text}")

    data = response.json()
    ticker_a, ticker_b, qty_a, qty_b = extract_pool_data(data)

    print(f"Pool-Zusammensetzung: {ticker_a} ({qty_a:.4f}) / {ticker_b} ({qty_b:.4f})")

    if ticker_a == "NIGHT" and ticker_b == "SNEK":
        return qty_b / qty_a
    elif ticker_a == "SNEK" and ticker_b == "NIGHT":
        return qty_a / qty_b
    else:
        # Fallback falls Ticker anders formatiert ist: Positionen anhand der Reserven prüfen
        raise RuntimeError(
            f"Unerwartete Pool-Zusammensetzung: {ticker_a}/{ticker_b} "
            f"(erwartet: NIGHT/SNEK). Pool-ID prüfen!"
        )


def check_crypto_prices():
    print("Starte Preisabfrage via Minswap API...")

    try:
        ratio = get_night_snek_ratio()
        print(f"Aktuelles Verhältnis: 1 NIGHT = {ratio:.2f} SNEK")

        int_ratio = int(ratio)
        last_alerted = load_last_alert_threshold()
        print(f"Zuletzt alarmierter Wert im Speicher: {last_alerted}")

        # OBERHALB der Grenze
        if int_ratio > OBERE_GRENZE:
            if last_alerted is None or int_ratio > last_alerted:
                msg = f"📈 Krypto-Alarm (Steigt)! Verhältnis bei 1 NIGHT = {ratio:.2f} SNEK!"
                send_push_notification(msg)
                save_alert_threshold(int_ratio)
            else:
                print(f"Verhältnis ({int_ratio}) ist nicht höher als der letzte Alarm ({last_alerted}). Kein Spam.")

        # UNTERHALB der Grenze
        elif int_ratio < UNTERE_GRENZE:
            if last_alerted is None or int_ratio < last_alerted:
                msg = f"📉 Krypto-Alarm (Fällt)! Verhältnis bei 1 NIGHT = {ratio:.2f} SNEK!"
                send_push_notification(msg)
                save_alert_threshold(int_ratio)
            else:
                print(f"Verhältnis ({int_ratio}) ist nicht tiefer als der letzte Alarm ({last_alerted}). Kein Spam.")

        # Normalbereich
        else:
            print("Verhältnis im Normalbereich. Kein Alarm gesendet.")
            if last_alerted is not None:
                clear_alert_state()

    except Exception as e:
        print(f"Fehler bei der API-Abfrage: {e}")


def get_night_ada_ratio():
    """Fragt den NIGHT/ADA-Pool bei Minswap ab und liefert: 1 NIGHT = X ADA."""
    print("Rufe NIGHT/ADA-Pool-Daten von der Minswap API ab...")
    params = {"_t": int(time.time())}
    response = requests.get(NIGHT_ADA_API_URL, headers=REQUEST_HEADERS, params=params, timeout=10)

    if response.status_code != 200:
        raise RuntimeError(f"API-Fehler {response.status_code}: {response.text}")

    data = response.json()
    ticker_a, ticker_b, qty_a, qty_b = extract_pool_data(data)

    print(f"Pool-Zusammensetzung: {ticker_a} ({qty_a:.4f}) / {ticker_b} ({qty_b:.4f})")

    if ticker_a == "NIGHT" and ticker_b == "ADA":
        return qty_b / qty_a
    elif ticker_a == "ADA" and ticker_b == "NIGHT":
        return qty_a / qty_b
    else:
        raise RuntimeError(
            f"Unerwartete Pool-Zusammensetzung: {ticker_a}/{ticker_b} "
            f"(erwartet: NIGHT/ADA). Pool-ID prüfen!"
        )


def get_ada_usdm_ratio():
    """Fragt den ADA/USDM-Pool bei Minswap ab und liefert: 1 ADA = X USDM (≈ USD)."""
    print("Rufe ADA/USDM-Pool-Daten von der Minswap API ab...")
    params = {"_t": int(time.time())}
    response = requests.get(ADA_USDM_API_URL, headers=REQUEST_HEADERS, params=params, timeout=10)

    if response.status_code != 200:
        raise RuntimeError(f"API-Fehler {response.status_code}: {response.text}")

    data = response.json()
    ticker_a, ticker_b, qty_a, qty_b = extract_pool_data(data)

    print(f"Pool-Zusammensetzung: {ticker_a} ({qty_a:.4f}) / {ticker_b} ({qty_b:.4f})")

    if ticker_a == "ADA" and ticker_b == "USDM":
        return qty_b / qty_a
    elif ticker_a == "USDM" and ticker_b == "ADA":
        return qty_a / qty_b
    else:
        raise RuntimeError(
            f"Unerwartete Pool-Zusammensetzung: {ticker_a}/{ticker_b} "
            f"(erwartet: ADA/USDM). Pool-ID prüfen!"
        )


def get_night_usd_price():
    """
    Berechnet den USD-Preis von 1 $NIGHT:
    1 NIGHT in USD = (NIGHT/ADA-Kurs) * (ADA/USDM-Kurs)
    """
    night_in_ada = get_night_ada_ratio()
    ada_in_usd = get_ada_usdm_ratio()
    night_in_usd = night_in_ada * ada_in_usd

    print(f"1 NIGHT = {night_in_ada:.6f} ADA, 1 ADA = {ada_in_usd:.4f} USD "
          f"=> 1 NIGHT = ${night_in_usd:.6f}")

    return night_in_usd


def load_last_night_price():
    """Lädt den zuletzt gespeicherten $NIGHT-Preis aus der Datei. None, wenn nicht vorhanden."""
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
    """Speichert den aktuellen $NIGHT-Preis als neuen Referenzwert."""
    try:
        with open(NIGHT_PREIS_STATE_FILE, "w") as f:
            f.write(str(value))
        print(f"Neuer NIGHT-Referenzpreis gespeichert: {value}")
    except Exception as e:
        print(f"Fehler beim Schreiben der NIGHT-Preisdatei: {e}")


def check_night_price():
    """Prüft den $NIGHT-Preis und alarmiert bei Anstieg >= NIGHT_PROZENT."""
    print("Starte $NIGHT-Preisabfrage via Minswap API (NIGHT/ADA * ADA/USDM)...")

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
