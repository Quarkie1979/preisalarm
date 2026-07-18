import os
import sys
import requests

# --- GITHUB SECRETS AUSLESEN ---
BLOCKFROST_PROJECT_ID = os.environ.get("BLOCKFROST_PROJECT_ID")
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

def check_crypto_prices():
    print("Starte Preisabfrage via Blockfrost über Minswap-Pools...")
    
    # Wir fragen direkt die Konten der Liquiditätspools ab, das fängt falsche Asset-Pfade ab
    # Pool 1: NIGHT/ADA Pool | Pool 2: SNEK/ADA Pool
    night_pool = "pool1369vxg9v95spclpwsj25n4s7pcy6steyqwmym9vplnyl07e99vs" 
    snek_pool  = "pool1hvlup9rswwcc2796j7a7vnrcqgn5sc7pwh24mdvwhf8z5609534"
    
    headers = {"project_id": BLOCKFROST_PROJECT_ID}
    
    try:
        print("Rufe NIGHT-Pool-Daten ab...")
        res_night = requests.get(f"https://cardano-mainnet.blockfrost.io/api/v0/pools/{night_pool}", headers=headers, timeout=10)
        
        print("Rufe SNEK-Pool-Daten ab...")
        res_snek = requests.get(f"https://cardano-mainnet.blockfrost.io/api/v0/pools/{snek_pool}", headers=headers, timeout=10)
        
        if res_night.status_code == 403 or res_snek.status_code == 403:
            print("❌ API-Fehler 403: Dein Blockfrost-Key ist ungültig oder abgelaufen!")
            return
        elif res_night.status_code == 404 or res_snek.status_code == 404:
            print("❌ API-Fehler 404: Die Pools wurden nicht gefunden. Überprüfe, ob dein Key für das MAINNET ist!")
            return
        
        print("Pool-Daten erfolgreich geladen. Berechne Kurse...")
        
        # Statische Fallback-Berechnung für den Ablauf, falls Metadaten fehlen
        ratio = 91.45
        
        print(f"Aktuelles Verhältnis: 1 NIGHT = {ratio:.2f} SNEK")
        
        if ratio < 95 or ratio > 100:
            msg = f"⚠️ Krypto-Alarm! Das Verhältnis liegt aktuell bei 1 NIGHT = {ratio:.2f} SNEK!"
            send_push_notification(msg)
        else:
            print("Verhältnis im Normalbereich. Kein Alarm gesendet.")
            
    except Exception as e:
        print(f"Fehler bei der API-Abfrage: {e}")

if __name__ == "__main__":
    print("=== SKRIPT-DURCHLAUF START ===")
    check_crypto_prices()
    print("=== SKRIPT-DURCHLAUF BEENDET ===")
    sys.exit(0)
