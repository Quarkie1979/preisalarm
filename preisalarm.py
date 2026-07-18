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
BLOCKFROST_PROJECT_ID = os.environ.get("BLOCKFROST_PROJECT_ID")

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

def get_minswap_prices_via_blockfrost():
    """
    Nutzt den spezialisierten Minswap-DEX-Endpunkt von Blockfrost.
    Das umgeht DNS-Fehler von externen APIs und das Adressformat-Problem.
    """
    # Blockfrost hat einen direkten Endpunkt, um Minswap V1 Pools abzufragen
    url = "https://cardano-mainnet.blockfrost.io/api/v0/backend/minswap/pools"
    headers = {"project_id": BLOCKFROST_PROJECT_ID}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code != 200:
            print(f"❌ Blockfrost Minswap-Endpunkt fehlgeschlagen (Status {res.status_code})")
            return None, None
            
        pools = res.json()
        
        ada_per_night = None
        ada_per_snek = None
        
        # Die Policy IDs unserer beiden Token
        NIGHT_POLICY = "e16561023d06eb1af278508ee0e18c09adcb69e9e99ebfe9826e6967"
        SNEK_POLICY  = "279c909f343cd051c11a3da366b2a6eb29971aeaf0e7be02cd19e115"
        
        for pool in pools:
            # Blockfrost strukturiert die Assets meistens als 'asset_a' und 'asset_b'
            asset_a = pool.get("asset_a", "")
            asset_b = pool.get("asset_b", "")
            
            # --- 1. NIGHT Pool suchen ---
            if asset_a == NIGHT_POLICY or asset_b == NIGHT_POLICY:
                reserve_a = int(pool.get("reserve_a", 0))
                reserve_b = int(pool.get("reserve_b", 0))
                
                # Lovelace (ADA) ist bei Blockfrost immer das leere Asset ""
                if asset_a == "":  # Asset A ist ADA, Asset B ist NIGHT
                    ada_per_night = (reserve_a / 1_000_000) / (reserve_b / 1_000_000)
                elif asset_b == "": # Asset B ist ADA, Asset A ist NIGHT
                    ada_per_night = (reserve_b / 1_000_000) / (reserve_a / 1_000_000)

            # --- 2. SNEK Pool suchen ---
            if asset_a == SNEK_POLICY or asset_b == SNEK_POLICY:
                reserve_a = int(pool.get("reserve_a", 0))
                reserve_b = int(pool.get("reserve_b", 0))
                
                # SNEK hat 0 Decimals, ADA ("") hat 6 Decimals
                if asset_a == "":  # Asset A ist ADA, Asset B ist SNEK
                    ada_per_snek = (reserve_a / 1_000_000) / reserve_b
                elif asset_b == "": # Asset B ist ADA, Asset A ist SNEK
                    ada_per_snek = (reserve_b / 1_000_000) / reserve_a

        return ada_per_night, ada_per_snek

    except Exception as e:
        print(f"Verbindungsfehler bei Blockfrost-Minswap-Abfrage: {e}")
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
    print("Starte Minswap-Pool-Abfrage via Blockfrost DEX-Brücke...")
    
    if not BLOCKFROST_PROJECT_ID:
        print("❌ FEHLER: BLOCKFROST_PROJECT_ID Environment Variable fehlt!")
        return

    ada_per_night, ada_per_snek = get_minswap_prices_via_blockfrost()
    
    if ada_per_night is None or ada_per_snek is None:
        print("❌ FEHLER: On-Chain Daten über Blockfrost-Minswap-Brücke konnten nicht geladen werden.")
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
