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

def get_pool_ratio_from_blockfrost(pool_address, token_decimals):
    """
    Fragt die Pool-Adresse über Blockfrost ab. 
    Nutzt den erweiterten Sicherheitscheck gegen Status 400.
    """
    # Verhindert Whitespace-Fehler in der URL
    clean_address = pool_address.strip()
    url = f"https://cardano-mainnet.blockfrost.io/api/v0/addresses/{clean_address}"
    headers = {"project_id": BLOCKFROST_PROJECT_ID}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code == 400:
            print(f"❌ Blockfrost Fehler 400: Ungültiges Adressformat an Blockfrost übergeben!")
            return None
        elif res.status_code == 403:
            print("❌ Blockfrost Fehler 403: Ungültiger Project ID Key!")
            return None
        elif res.status_code == 404:
            print("❌ Blockfrost Fehler 404: Pool-Adresse auf der Blockchain nicht gefunden!")
            return None
        elif res.status_code != 200:
            print(f"⚠️ Blockfrost API meldet Status: {res.status_code}")
            return None
            
        data = res.json()
        # Fallback falls 'amount' nicht existiert
        amounts = data.get("amount", [])
        
        ada_lovelace = 0
        token_units = 0
        
        for item in amounts:
            if item.get("unit") == "lovelace":
                ada_lovelace = int(item.get("quantity", 0))
            else:
                token_units = int(item.get("quantity", 0))
                
        if ada_lovelace == 0 or token_units == 0:
            print("❌ Fehler: Pool-Bestände (ADA oder Token) sind leer oder konnten nicht identifiziert werden.")
            return None
            
        real_ada = ada_lovelace / 1_000_000
        real_tokens = token_units / (10 ** token_decimals)
        
        token_ada_price = real_ada / real_tokens if real_tokens > 0 else 0
        return token_ada_price

    except Exception as e:
        print(f"Verbindungsfehler bei Blockfrost-Abfrage: {e}")
        return None

def load_last_alert_threshold():
    """Lädt den letzten alarmierten Schwellenwert aus der Statusdatei"""
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
    """Löscht den gespeicherten Zustand"""
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
            print("Kurs wieder im Normalbereich. Alarm-Gedächtnis zurückgesetzt.")
        except Exception as e:
            print(f"Fehler beim Löschen der Statusdatei: {e}")

def check_crypto_prices():
    print("Starte On-Chain Pool-Abfrage über Blockfrost...")
    
    if not BLOCKFROST_PROJECT_ID:
        print("❌ FEHLER: BLOCKFROST_PROJECT_ID Environment Variable fehlt!")
        return

    # Offizielle Minswap V1 Kontrakt-Pools im sauberen String-Format ohne versteckte Leerzeichen
    NIGHT_ADA_POOL = "addr1z8snz5g3k822f3xzs3q480j6nrc4z3v6xfl6gfnf28876ux5w6znccu8v0tpx4cr3pxe0p3p54p7vpe6v2tpx4cr3pxs3l2d27" 
    SNEK_ADA_POOL  = "addr1z9xnz5g3k822f3xzs3q480j6nrc4z3v6xfl6gfnf28876ux5w6znccu8v0tpx4cr3pxe0p3p54p7vpe6v2tpx4cr3pxs7q9d3g"

    # 1. ADA-Wert pro NIGHT
    ada_per_night = get_pool_ratio_from_blockfrost(NIGHT_ADA_POOL, token_decimals=6)
    
    # 2. ADA-Wert pro SNEK
    ada_per_snek = get_pool_ratio_from_blockfrost(SNEK_ADA_POOL, token_decimals=0)
    
    if ada_per_night is None or ada_per_snek is None:
        print("❌ FEHLER: On-Chain Pool-Daten konnten nicht vollständig geladen werden.")
        return

    raw_ratio = ada_per_night / ada_per_snek if ada_per_snek > 0 else 0
    if raw_ratio == 0:
        print("Fehler: SNEK Pool-Wert berechnet sich als 0.")
        return

    ratio = int(raw_ratio)
    print(f"Aktuelles Verhältnis (On-Chain): 1 NIGHT = {ratio} SNEK (Exakt: {raw_ratio:.4f})")
    
    last_alerted = load_last_alert_threshold()
    print(f"Zuletzt alarmierter Höchstwert im Speicher: {last_alerted}")

    if ratio > OBERE_GRENZE:
        if last_alerted is None or ratio > last_alerted:
            msg = f"📈 Krypto-Alarm (Steigt/On-Chain)! Verhältnis bei 1 NIGHT = {ratio} SNEK!"
            send_push_notification(msg)
            save_alert_threshold(ratio)
        else:
            print(f"Verhältnis ({ratio}) ist nicht höher als der letzte Alarm ({last_alerted}). Kein Spam.")

    elif ratio < UNTERE_GRENZE:
        if last_alerted is None or ratio < last_alerted:
            msg = f"📉 Krypto-Alarm (Fällt/On-Chain)! Verhältnis bei 1 NIGHT = {ratio} SNEK!"
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
