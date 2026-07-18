import os
import sys
import requests

# --- CONFIGURATION ---
STATE_FILE = "alarm_state.txt"
UNTERE_GRENZE = 95
OBERE_GRENZE = 100

# NIGHT-SNEK Pool auf Minswap (LP Policy-ID + LP Token-Name zusammengesetzt)
POOL_ID = "f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c3b3318a251bb71f8345c5affcd29645af2f56859eea740bec2a27c91027cb01d"
MINSWAP_API_URL = f"https://api-mainnet-prod.minswap.org/v1/pools/{POOL_ID}/metrics"

# --- GITHUB SECRETS AUSLESEN ---
PUSHOVER_USER_KEY = os.environ.get("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.environ.get("PUSHOVER_API_TOKEN")


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


def get_night_snek_ratio():
    """Fragt den NIGHT-SNEK-Pool bei Minswap ab und berechnet das Verhältnis 1 NIGHT = X SNEK."""
    print("Rufe Pool-Daten von der Minswap API ab...")
    response = requests.get(MINSWAP_API_URL, timeout=10)

    if response.status_code != 200:
        raise RuntimeError(f"API-Fehler {response.status_code}: {response.text}")

    data = response.json()

    asset_a_ticker = data["asset_a"]["metadata"]["ticker"]
    asset_b_ticker = data["asset_b"]["metadata"]["ticker"]
    liquidity_a = data["liquidity_a_raw"]
    liquidity_b = data["liquidity_b_raw"]

    print(f"Pool-Zusammensetzung: {asset_a_ticker} ({liquidity_a}) / {asset_b_ticker} ({liquidity_b})")

    if asset_a_ticker == "NIGHT" and asset_b_ticker == "SNEK":
        return liquidity_b / liquidity_a
    elif asset_a_ticker == "SNEK" and asset_b_ticker == "NIGHT":
        return liquidity_a / liquidity_b
    else:
        raise RuntimeError(
            f"Unerwartete Pool-Zusammensetzung: {asset_a_ticker}/{asset_b_ticker} "
            f"(erwartet: NIGHT/SNEK). Pool-ID prüfen!"
        )


def check_crypto_prices():
    print("Starte Preisabfrage via Minswap API...")

    try:
        ratio = get_night_snek_ratio()
        print(f"Aktuelles Verhältnis: 1 NIGHT = {ratio:.2f} SNEK")

        # Für das Gedächtnis nutzen wir die Ganzzahl des Verhältnisses
        int_ratio = int(ratio)
        last_alerted = load_last_alert_threshold()
        print(f"Zuletzt alarmierter Wert im Speicher: {last_alerted}")

        # Logik für OBERHALB der Grenze
        if int_ratio > OBERE_GRENZE:
            if last_alerted is None or int_ratio > last_alerted:
                msg = f"📈 Krypto-Alarm (Steigt)! Verhältnis bei 1 NIGHT = {ratio:.2f} SNEK!"
                send_push_notification(msg)
                save_alert_threshold(int_ratio)
            else:
                print(f"Verhältnis ({int_ratio}) ist nicht höher als der letzte Alarm ({last_alerted}). Kein Spam.")

        # Logik für UNTERHALB der Grenze
        elif int_ratio < UNTERE_GRENZE:
            if last_alerted is None or int_ratio < last_alerted:
                msg = f"📉 Krypto-Alarm (Fällt)! Verhältnis bei 1 NIGHT = {ratio:.2f} SNEK!"
                send_push_notification(msg)
                save_alert_threshold(int_ratio)
            else:
                print(f"Verhältnis ({int_ratio}) ist nicht tiefer als der letzte Alarm ({last_alerted}). Kein Spam.")

        # Normalbereich (zwischen den Grenzen)
        else:
            print("Verhältnis im Normalbereich. Kein Alarm gesendet.")
            if last_alerted is not None:
                clear_alert_state()

    except Exception as e:
        print(f"Fehler bei der API-Abfrage: {e}")


if __name__ == "__main__":
    print("=== SKRIPT-DURCHLAUF START ===")
    check_crypto_prices()
    print("=== SKRIPT-DURCHLAUF BEENDET ===")
    sys.exit(0)
