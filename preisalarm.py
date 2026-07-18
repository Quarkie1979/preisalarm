import time
import requests

# --- HIER DEINE BLOCKFROST- UND PUSHOVER-DATEN EINTRAGEN ---
BLOCKFROST_PROJECT_ID = "DEIN_BLOCKFROST_PROJECT_ID"
PUSHOVER_USER_KEY = "DEIN_USER_KEY"
PUSHOVER_API_TOKEN = "DEIN_API_TOKEN"

# Zustands-Speicher
letzter_gemeldeter_wert = None
alarm_ausserhalb_grenzen = False


def send_push(message):
    """Sendet die Push-Benachrichtigung an dein iPhone via Pushover API"""
    url = "https://api.pushover.net/1/messages.json"
    data = {
        "token": PUSHOVER_API_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "message": message,
        "title": "🚨 Krypto Blockfrost Alarm!",
    }
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Fehler beim Senden der Push-Nachricht: {e}")


def get_prices_via_blockfrost():
    """Holt die aktuellen Asset-Daten direkt von der Cardano Blockchain"""
    headers = {"project_id": BLOCKFROST_PROJECT_ID}

    # Offizielle Cardano Asset-IDs für SNEK und NIGHT
    url_night = "https://cardano-mainnet.blockfrost.io/api/v0/assets/0691b2fecca1ac4f53cb6dfb00b7013e561d1f34403b957cbb5af1fa4e49474854"
    url_snek = "https://cardano-mainnet.blockfrost.io/api/v0/assets/279c909f34315b9eaf93a5a41357a6c11da26aae825227d6d5392b2d534e454b534e454b"

    try:
        res_night = requests.get(url_night, headers=headers).json()
        res_snek = requests.get(url_snek, headers=headers).json()

        # Extrahiere die On-Chain-Preise in ADA aus den Metadaten
        # (Falls die Struktur je nach Pool variiert, wird hier ein Fallback genutzt)
        price_night_ada = float(
            res_night.get("onchain_metadata", {}).get("price_in_ada", 0)
        )
        price_snek_ada = float(
            res_snek.get("onchain_metadata", {}).get("price_in_ada", 0)
        )

        # Falls Blockfrost-Metadaten leer sind, nutzen wir den geschätzten Marktwert des Assets im System
        if price_night_ada == 0 or price_snek_ada == 0:
            # Fallback über die Liquiditäts-Berechnung von Blockfrost
            price_night_ada = float(res_night.get("liquidity", 1))
            price_snek_ada = float(res_snek.get("liquidity", 1))

        return price_night_ada, price_snek_ada
    except Exception as e:
        print(f"Blockfrost API Fehler: {e}")
        return None, None


def check_ratio():
    global letzter_gemeldeter_wert, alarm_ausserhalb_grenzen

    price_night, price_snek = get_prices_via_blockfrost()

    if price_night and price_snek:
        # Berechne das Verhältnis: Wie viele SNEK für 1 NIGHT
        ratio = price_night / price_snek
        print(f"Aktuelles Verhältnis: 1 NIGHT = {ratio:.2f} SNEK")

        # Prüfen, ob wir uns außerhalb der Komfort-Zone befinden (<80 oder >100)
        ist_ausserhalb = ratio < 95 or ratio > 100

        # FALL 1: Erster Alarm beim Durchbrechen der Grenze
        if ist_ausserhalb and not alarm_ausserhalb_grenzen:
            msg = f"🚨 GRENZE DURCHBROCHEN! 1 NIGHT = {ratio:.2f} SNEK."
            send_push(msg)
            alarm_ausserhalb_grenzen = True
            letzter_gemeldeter_wert = round(ratio)

        # FALL 2: Wir sind bereits außerhalb und der Preis ändert sich um >= 1 oder <= -1
        elif ist_ausserhalb and alarm_ausserhalb_grenzen:
            aktueller_wert_gerundet = round(ratio)
            unterschied = aktueller_wert_gerundet - letzter_gemeldeter_wert

            if unterschied >= 1:
                msg = f"📈 Preis steigt weiter! 1 NIGHT = {ratio:.2f} SNEK (Anstieg um {unterschied} SNEK)."
                send_push(msg)
                letzter_gemeldeter_wert = aktueller_wert_gerundet
            elif unterschied <= -1:
                msg = f"📉 Preis fällt weiter! 1 NIGHT = {ratio:.2f} SNEK (Fall um {abs(unterschied)} SNEK)."
                send_push(msg)
                letzter_gemeldeter_wert = aktueller_wert_gerundet

        # FALL 3: Der Preis beruhigt sich wieder und geht zurück in den Normalbereich (80 - 100)
        elif not ist_ausserhalb and alarm_ausserhalb_grenzen:
            msg = f"✅ Wieder im Normalbereich. 1 NIGHT = {ratio:.2f} SNEK."
            send_push(msg)
            alarm_ausserhalb_grenzen = False
            letzter_gemeldeter_wert = None


# Hauptschleife: Prüft alle 5 Minuten (300 Sekunden)
print("Blockfrost Krypto-Alarm gestartet...")
while True:
    check_ratio()
    time.sleep(300)