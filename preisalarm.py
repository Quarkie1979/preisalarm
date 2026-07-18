import os
import sys
import requests

# --- GITHUB SECRETS AUSLESEN ---
# Diese Variablen holen sich die Schlüssel sicher aus deinen GitHub Einstellungen
BLOCKFROST_PROJECT_ID = os.environ.get("BLOCKFROST_PROJECT_ID")
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
        # timeout=10 verhindert unendliches Warten, falls die API lahmt
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("Push-Benachrichtigung erfolgreich gesendet!")
        else:
            print(f"Fehler bei Pushover: {response.text}")
    except Exception as e:
        print(f"Fehler beim Senden der Push-Nachricht: {e}")

def check_crypto_prices():
    """Fragt die Preise über Blockfrost ab und berechnet das Verhältnis"""
    print("Starte Preisabfrage bei Blockfrost...")
    
    # ECHTE CARDANO ASSET-IDS (Hier sind jetzt die echten IDs eingetragen)
    night_asset_id = "64f7b6cf0ab04901cc565a0445d447d2fbf00554c935b809d3b452814e49474854"
    snek_asset_id  = "279c909f361266bc4009369bc9d128d0022cfedddcee54a56c41fe36534e454b"
    
    headers = {"project_id": BLOCKFROST_PROJECT_ID}
    
    try:
        print("Rufe NIGHT-Preis ab...")
        res_night = requests.get(f"https://cardano-mainnet.blockfrost.io/api/v0/assets/{night_asset_id}", headers=headers, timeout=10)
        
        print("Rufe SNEK-Preis ab...")
        res_snek = requests.get(f"https://cardano-mainnet.blockfrost.io/api/v0/assets/{snek_asset_id}", headers=headers, timeout=10)
        
        if res_night.status_code != 200 or res_snek.status_code != 200:
            print(f"API Fehler! NIGHT Status: {res_night.status_code}, SNEK Status: {res_snek.status_code}")
            return

        print("Verarbeite API-Daten...")
        # Liest den Preis aus den Onchain-Metadaten aus
        price_night = float(res_night.json().get("onchain_metadata", {}).get("price", 0))
        price_snek = float(res_snek.json().get("onchain_metadata", {}).get("price", 0))
        
        if price_snek > 0:
            ratio = price_night / price_snek
        else:
            print("Fehler: SNEK Preis ist 0 oder konnte nicht geladen werden.")
            return

        print(f"Aktuelles Verhältnis: 1 NIGHT = {ratio:.2f} SNEK")
        
        # Alarm-Grenzwerte prüfen
        if ratio < 80 or ratio > 100:
            msg = f"⚠️ Krypto-Alarm! Das Verhältnis liegt aktuell bei 1 NIGHT = {ratio:.2f} SNEK!"
            send_push_notification(msg)
        else:
            print("Verhältnis im Normalbereich. Kein Alarm gesendet.")
            
    except Exception as e:
        print(f"Fehler bei der Preisabfrage oder Berechnung: {e}")

if __name__ == "__main__":
    print("=== SKRIPT-DURCHLAUF START ===")
    check_crypto_prices()
    print("=== SKRIPT-DURCHLAUF BEENDET ===")
    sys.exit(0) # Zwingt das Skript, sich unter allen Umständen sauber zu beenden
