import os
import sys
import requests

# --- CONFIGURATION ---
STATE_FILE = "alarm_state.txt"
UNTERE_GRENZE = 95
OBERE_GRENZE = 100

# --- GITHUB SECRETS AUSLESEN ---
PUSHOVER_USER_KEY = os.environ.get("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.environ.get("PUSHOVER_API_TOKEN")

def send_push_notification(message):
    """Sendet die Benachrichtigung an dein Smartphone via Pushover"""
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

def get_price_from_geckoterminal(policy_id):
    """Holt den aktuellen USD-Preis eines Cardano-Tokens"""
    url = f"https://api.geckoterminal.com/api/v2/networks/cardano/tokens/{policy_id}"
    headers = {"Accept": "application/json;version=20230302"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            price_usd = data.get("data", {}).get("attributes", {}).get("price_usd")
            if price_usd:
                return float(price_usd)
        return None
    except Exception as e:
        print(f"Fehler bei API-Abfrage: {e}")
        return None

def load_last_alert_threshold():
    """Lädt den letzten alarmierten Schwellenwert als Ganzzahl"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                content = f.read().strip()
                if content:
                    return int(content) # Als ganze Zahl laden
        except Exception as e:
            print(f"Fehler beim Lesen der Statusdatei: {e}")
    return None

def save_alert_threshold(value):
    """Speichert den aktuellen Schwellenwert als Ganzzahl"""
    try:
        with open(STATE_FILE, "w") as f:
            f.write(str(int(value))) # Als ganze Zahl speichern
        print(f"Neuen Schwellenwert gespeichert: {int(value)}")
    except Exception as e:
        print(f"Fehler beim Schreiben der Statusdatei: {e}")

def clear_alert_state():
    """Löscht den gespeicherten Zustand, wenn der Kurs wieder normal ist"""
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
            print("Kurs wieder im Normalbereich. Alarm-Gedächtnis zurückgesetzt.")
        except Exception as e:
            print(f"Fehler beim Löschen der Statusdatei: {e}")

def check_crypto_prices():
    print("Starte Preisabfrage...")
    night_policy = "64f7b6cf0ab04901cc565a0445d447d2fbf00554c935b809d3b45281"
    snek_policy  = "279c909f361266bc4009369bc9d128d0022cfedddcee54a56c41fe36"
    
    price_night = get_price_from_geckoterminal(night_policy)
    price_snek = get_price_from_geckoterminal(snek_policy)
    
    if price_night is None or price_snek is None:
        print("❌ FEHLER: Preise konnten nicht geladen werden.")
        return

    raw_ratio = price_night / price_snek if price_snek > 0 else 0
    if raw_ratio == 0:
        print("Fehler: SNEK Preis ist 0.")
        return

    # Umwandlung in eine reine Ganzzahl (Kommastellen werden abgeschnitten)
    ratio = int(raw_ratio)
    print(f"Aktuelles Verhältnis (gerundet): 1 NIGHT = {ratio} SNEK (Exakt: {raw_ratio:.4f})")
    
    # Letzten alarmierten Wert laden
    last_alerted = load_last_alert_threshold()
    print(f"Zuletzt alarmierter Höchstwert im Speicher: {last_alerted}")

    # Logik für OBERHALB der Grenze
    if ratio > OBERE_GRENZE:
        # Nur benachrichtigen, wenn es noch kein Signal gab ODER der neue Wert ECHTE 1 höher ist
        if last_alerted is None or ratio > last_alerted:
            msg = f"📈 Krypto-Alarm (Steigt)! Verhältnis bei 1 NIGHT = {ratio} SNEK!"
            send_push_notification(msg)
            save_alert_threshold(ratio)
        else:
            print(f"Verhältnis ({ratio}) ist nicht höher als der letzte Alarm ({last_alerted}). Kein Spam.")

    # Logik für UNTERHALB der Grenze
    elif ratio < UNTERE_GRENZE:
        # Nur benachrichtigen, wenn es noch kein Signal gab ODER der neue Wert ECHTE 1 tiefer ist
        if last_alerted is None or ratio < last_alerted:
            msg = f"📉 Krypto-Alarm (Fällt)! Verhältnis bei 1 NIGHT = {ratio} SNEK!"
            send_push_notification(msg)
            save_alert_threshold(ratio)
        else:
            print(f"Verhältnis ({ratio}) ist nicht tiefer als der letzte Alarm ({last_alerted}). Kein Spam.")

    # Normalbereich (liegt zwischen den beiden Grenzen)
    else:
        print("Verhältnis im Normalbereich.")
        if last_alerted is not None:
            clear_alert_state()

if __name__ == "__main__":
    print("=== SKRIPT-DURCHLAUF START ===")
    check_crypto_prices()
    print("=== SKRIPT-DURCHLAUF BEENDET ===")
    sys.exit(0)
