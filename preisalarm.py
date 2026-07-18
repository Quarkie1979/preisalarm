import os
import requests

# --- GITHUB SECRETS AUSLESEN ---
# Diese Variablen holen sich die Schlüssel sicher aus deinen GitHub Einstellungen
BLOCKFROST_PROJECT_ID = os.environ.get("BLOCKFROST_PROJECT_ID")
PUSHOVER_USER_KEY = os.environ.get("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.environ.get("PUSHOVER_API_TOKEN")

def send_push_notification(message):
    """Sendet die Benachrichtigung an dein iPhone via Pushover"""
    url = "https://api.pushover.net/1/messages.json"
    data = {
        "token": PUSHOVER_API_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "message": message
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("Push-Benachrichtigung erfolgreich gesendet!")
        else:
            print(f"Fehler bei Pushover: {response.text}")
    except Exception as e:
        print(f"Fehler beim Senden der Push-Nachricht: {e}")

def check_crypto_prices():
    """Fragt die Preise über Blockfrost ab und berechnet das Verhältnis"""
    print("Blockfrost Krypto-Alarm gestartet...")
    
    # Hier definierst du die API-URLs für deine Token (Beispiel-Endpunkte für Blockfrost)
    # Passe die Pool- oder Asset-IDs ggf. an deine genauen Token an
    headers = {"project_id": BLOCKFROST_PROJECT_ID}
    
    try:
        # 1. Preise abfragen (Beispielhafte Abfrage der Token-Preise)
        # Hinweis: Ersetze 'asset_id_night' und 'asset_id_snek' mit den echten IDs falls nötig
        res_night = requests.get("https://cardano-mainnet.blockfrost.io/api/v0/assets/asset_id_night", headers=headers)
        res_snek = requests.get("https://cardano-mainnet.blockfrost.io/api/v0/assets/asset_id_snek", headers=headers)
        
        # Falls du die Preise über einen DEX-Pool holst, sieht deine JSON-Abfrage hier ähnlich aus:
        price_night = float(res_night.json().get("onchain_metadata", {}).get("price", 0))
        price_snek = float(res_snek.json().get("onchain_metadata", {}).get("price", 0))
        
        # Falls die obigen Zeilen bei dir anders aufgebaut waren (z.B. über SundaeSwap/Minswap),
        # behalte einfach deine funktionierende Logik zur Berechnung der 'ratio' bei!
        
        # Berechnung des Verhältnisses (Beispielwert für die Logik)
        if price_snek > 0:
            ratio = price_night / price_snek
        else:
            print("Fehler: SNEK Preis ist 0 oder konnte nicht geladen werden.")
            return

        print(f"Aktuelles Verhältnis: 1 NIGHT = {ratio:.2f} SNEK")
        
        # 2. Alarm-Grenzwerte prüfen
        # Wenn das Verhältnis unter 80 oder über 100 fällt, schlagen wir Alarm
        if ratio < 80 or ratio > 100:
            msg = f"⚠️ Krypto-Alarm! Das Verhältnis liegt aktuell bei 1 NIGHT = {ratio:.2f} SNEK!"
            send_push_notification(msg)
        else:
            print("Verhältnis im Normalbereich. Kein Alarm gesendet.")
            
    except Exception as e:
        print(f"Fehler bei der Preisabfrage oder Berechnung: {e}")

# --- SKRIPT AUSFÜHRUNG ---
# Das Skript läuft jetzt genau EINMAL von oben nach unten durch.
# GitHub Actions startet diesen Ablauf alle 15 Minuten komplett neu.
if __name__ == "__main__":
    check_crypto_prices()
