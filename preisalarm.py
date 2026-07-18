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

def get_token_price_from_minswap_via_blockfrost(pool_nft_id, token_decimals):
    """
    Findet den Minswap-Pool anhand seiner eindeutigen Pool-NFT-ID über Blockfrost
    und berechnet den exakten ADA-Preis des Tokens ohne fehleranfällige Adressen.
    """
    # Schritt 1: Wir fragen Blockfrost, auf welcher Adresse das Pool-NFT aktuell liegt
    url_asset = f"https://cardano-mainnet.blockfrost.io/api/v0/assets/{pool_nft_id}/addresses"
    headers = {"project_id": BLOCKFROST_PROJECT_ID}
    
    try:
        res_asset = requests.get(url_asset, headers=headers, timeout=15)
        if res_asset.status_code != 200:
            print(f"❌ Blockfrost Asset-Suche fehlgeschlagen (Status {res_asset.status_code})")
            return None
            
        asset_data = res_asset.json()
        if not asset_data:
            print(f"❌ Pool NFT {pool_nft_id[:10]}... nicht auf der Blockchain gefunden.")
            return None
            
        pool_address = asset_data[0].get("address")
        
        # Schritt 2: Wir holen die Live-UTXOs genau dieser Pool-Adresse
        url_utxo = f"https://cardano-mainnet.blockfrost.io/api/v0/addresses/{pool_address}/utxos"
        res_utxo = requests.get(url_utxo, headers=headers, timeout=15)
        
        if res_utxo.status_code != 200:
            print(f"❌ Blockfrost UTXO-Abfrage fehlgeschlagen (Status {res_utxo.status_code})")
            return None
            
        utxos = res_utxo.json()
        
        ada_lovelace = 0
        token_units = 0
        
        # Wir suchen in den UTXOs nach dem Pool, der unser NFT enthält
        for utxo in utxos:
            amounts = utxo.get("amount", [])
            # Prüfen, ob dieses spezifische Pool-NFT in diesem UTXO liegt
            has_nft = any(item.get("unit") == pool_nft_id for item in amounts)
            
            if has_nft:
                for item in amounts:
                    unit = item.get("unit")
                    quantity = int(item.get("quantity", 0))
                    
                    if unit == "lovelace":
                        ada_lovelace = quantity
                    elif unit != pool_nft_id and not unit.startswith("0ea486b34b909f2c623b11da147db618e330d180ae34fe772022d202"):
                        # Das ist unser gesuchtes Token (weder Lovelace, noch das Pool-NFT/LP-Token)
                        token_units = quantity
                break
                
        if ada_lovelace == 0 or token_units == 0:
            print("❌ Fehler: Pool-Mengen konnten nicht isoliert werden.")
            return None
            
        real_ada = ada_lovelace / 1_000_000
        real_tokens = token_units / (10 ** token_decimals)
        
        return real_ada / real_tokens if real_tokens > 0 else 0

    except Exception as e:
        print(f"Verbindungsfehler bei Blockfrost: {e}")
        return None

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
    print("Starte On-Chain Pool-Abfrage über Blockfrost Asset-Tracking...")
    
    if not BLOCKFROST_PROJECT_ID:
        print("❌ FEHLER: BLOCKFROST_PROJECT_ID Environment Variable fehlt!")
        return

    # Offizielle, unveränderliche Minswap V1 Pool-NFT IDs für die beiden Paare
    # Blockfrost findet darüber automatisch die korrekte Smart-Contract-Box.
    NIGHT_ADA_POOL_NFT = "0ea486b34b909f2c623b11da147db618e330d180ae34fe772022d2026e696768745f6164615f6c70"
    SNEK_ADA_POOL_NFT  = "0ea486b34b909f2c623b11da147db618e330d180ae34fe772022d202736e656b5f6164615f6c70"

    # 1. ADA-Wert pro NIGHT (6 Decimals)
    ada_per_night = get_token_price_from_minswap_via_blockfrost(NIGHT_ADA_POOL_NFT, token_decimals=6)
    
    # 2. ADA-Wert pro SNEK (0 Decimals)
    ada_per_snek = get_token_price_from_minswap_via_blockfrost(SNEK_ADA_POOL_NFT, token_decimals=0)
    
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
