import os
import sys
import requests

# --- CONFIGURATION ---
STATE_FILE = "alarm_state.txt"
UNTERE_GRENZE = 80
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

def get_minswap_pool_prices():
    """
    Fragt die offizielle, öffentliche Minswap API ab.
    Gibt den ADA-Preis für NIGHT und SNEK direkt aus dem Liquiditätspool zurück.
    """
    url = "https://api-mainnet.minswap.org/v1/pools"
    try:
        # Wir holen uns die aktuellen Top-Pools von Minswap
        res = requests.get(url, timeout=15)
        if res.status_code != 200:
            print(f"❌ Minswap API Fehler: Status {res.status_code}")
            return None, None
            
        pools = res.json()
        
        ada_per_night = None
        ada_per_snek = None
        
        # Wir durchlaufen die Pools und suchen anhand der exakten Token-Policy-IDs
        for pool in pools:
            asset_a = pool.get("assetA", {}).get("currencySymbol", "")
            asset_b = pool.get("assetB", {}).get("currencySymbol", "")
            
            # 1. NIGHT-ADA Pool suchen
            # Policy ID von NIGHT: e16561...
            if (asset_a == "e16561023d06eb1af278508ee0e18c09adcb69e9e99ebfe9826e6967" and asset_b == "lovelace") or \
               (asset_b == "e16561023d06eb1af278508ee0e18c09adcb69e9e99ebfe9826e6967" and asset_a == "lovelace"):
                
                # Preisberechnung unter Berücksichtigung der Decimals (NIGHT = 6, ADA = 6)
                reserve_a = int(pool.get("reserveA", 0))
                reserve_b = int(pool.get("reserveB", 0))
                
                if asset_a == "lovelace":
                    ada_per_night = (reserve_a / 1_000_000) / (reserve_b / 1_000_000)
                else:
                    ada_per_night = (reserve_b / 1_000_000) / (reserve_a / 1_000_000)

            # 2. SNEK-ADA Pool suchen
            # Policy ID von SNEK: 279c90...
            if (asset_a == "279c909f343cd051c11a3da366b2a6eb29971aeaf0e7be02cd19e115" and asset_b == "lovelace") or \
               (asset_b == "279c909f343cd051c11a3da366b2a6eb29971aeaf0e7be02cd19e115" and asset_a == "lovelace"):
                
                reserve_a = int(pool.get("reserveA", 0))
                reserve_b = int(pool.get("reserveB", 0))
                
                # SNEK hat 0 Decimals, ADA hat 6 Decimals
                if asset_a == "lovelace":
                    ada_per_snek = (reserve_a / 1_000_000) / reserve_b
                else:
                    ada_per_snek = (reserve_b / 1_000_000) / reserve_a

        return ada_per_night, ada_per_snek

    except Exception as e:
        print(f"Verbindungsfehler zur Minswap API: {e}")
        return None, None

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

def check_crypto_prices():
    print("Starte Pool-Abfrage direkt über die Minswap-API...")
    
    ada_per_night, ada_per_snek = get_minswap_pool_prices()
    
    if ada_per_night is None or ada_per_snek is None:
        print("❌ FEHLER: Daten konnten von Minswap nicht geladen werden.")
        return

    print(f"Minswap-Preise: 1 NIGHT = {ada_per_night:.6f} ADA | 1 SNEK = {ada_per_snek:.6f} ADA")

    raw_ratio = ada_per_night / ada_per_snek if ada_per_snek > 0 else 0
    if raw_ratio == 0:
        print("Fehler: SNEK Pool-Wert berechnet sich als 0.")
        return

    ratio = int(raw_ratio)
    print(f"Aktuelles Verhältnis: 1 NIGHT = {ratio} SNEK (Exakt: {raw_ratio:.4f})")
    
    last_alerted = load_last_alert_threshold()
    print(f"Zuletzt alarmierter Höchstwert im Speicher: {last_alerted}")

    if ratio > OBERE_GRENZE:
        if last_alerted is None or ratio > last_alerted:
            msg = f"📈 Krypto-Alarm (Steigt)! Verhältnis bei 1 NIGHT = {ratio} SNEK!"
            send_push_notification(msg)
            save_alert_threshold(ratio)
        else:
            print(f"Verhältnis ({ratio}) ist nicht höher als der letzte Alarm ({last_alerted}). Kein Spam.")

    elif ratio < UNTERE_GRENZE:
        if last_alerted is None or ratio < last_alerted:
            msg = f"📉 Krypto-Alarm (Fällt)! Verhältnis bei 1 NIGHT = {ratio} SNEK!"
            send_push_notification(msg)
            save_alert_threshold(ratio)
        else:
            print(f"Verhältnis ({ratio}) ist nicht tiefer als der letzte Alarm ({last_alerted}). Kein Spam.")

    else:
        print("Verhältnis im Normalbereich.")
        if last_alerted is not None:
            clear_alert_state()

if __name__ == "__main__":
    print("=== SKRIPT-DURCHLAUF START ===")
    check_crypto_prices()
    print("=== SKRIPT-DURCHLAUF BEENDET ===")
    sys.exit(0)
