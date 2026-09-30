import os
import sys
import requests

# --- CONFIGURATION ---
STATE_FILE = "alarm_state.txt"
UNTERE_GRENZE = 3
OBERE_GRENZE = 62
NIGHT_PROZENT = 2  # Mindest-Preisanstieg in % für den $NIGHT-Preisalarm
NIGHT_PREIS_STATE_FILE = "nightpreis.txt"

# Die LP Asset Units der Minswap Pools (PolicyID + Hex Token Name)
# Dies identifiziert die Pools auf Cardano eindeutig
POOL_LP_NIGHT_SNEK = "f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c3b3318a251bb71f8345c5affcd29645af2f56859eea740bec2a27c91027cb01d"
POOL_LP_NIGHT_ADA = "f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4ce74c52975908a612d5ce68327040d449aae99f8b463bb6de046a1b23c5713169"
POOL_LP_ADA_USDM = "f5808c2c990d86da54bfc97d89cee6efa20cd8461616359478d96b4c7dd6988c5a86693c76aeec1ea94afa41770be0de21a775ca7a2a1eabdb6a0171"

# Bekannte Asset-Units der Token für die Erkennung
# SNEK (Policy: 279c2bcc710aa108144095ba7ed6ff7387e668fa61827c193b329afa, Name: SNEK)
SNEK_UNIT = "279c2bcc710aa108144095ba7ed6ff7387e668fa61827c193b329afa534e454b"
# USDM (Policy: c48cbb3d5e57ed56e276bc45f99ab3925e80503d14e373fa869ac004, Name: USDM)
USDM_UNIT = "c48cbb3d5e57ed56e276bc45f99ab3925e80503d14e373fa869ac0045553444d"

# Dezimalstellen der Token
DECIMALS_ADA = 6
DECIMALS_USDM = 6
DECIMALS_SNEK = 0
DECIMALS_NIGHT = 6  # Standard Midnight NIGHT Test/Pre-Tokens (6 Dezimalen)

# --- ENVIRONMENT SECRETS ---
PUSHOVER_USER_KEY = os.environ.get("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.environ.get("PUSHOVER_API_TOKEN")
BLOCKFROST_PROJECT_ID = os.environ.get("BLOCKFROST_PROJECT_ID")

BLOCKFROST_URL = "https://cardano-mainnet.blockfrost.io/api/v0"


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


def get_pool_utxo_amounts(pool_lp_asset):
    """
    Findet über Blockfrost die Adresse und das aktive UTxO des Pools,
    in dem das Minswap LP-Asset liegt, und liefert alle aktuellen Token-Mengen.
    """
    if not BLOCKFROST_PROJECT_ID:
        raise RuntimeError("BLOCKFROST_PROJECT_ID fehlt in den Umgebungsvariablen!")

    headers = {"project_id": BLOCKFROST_PROJECT_ID}

    # 1. Adresse finden, die das LP-Asset aktuell hält
    addr_url = f"{BLOCKFROST_URL}/assets/{pool_lp_asset}/addresses?order=desc&count=1"
    r = requests.get(addr_url, headers=headers, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"Blockfrost Fehler bei Pool-Adresse ({r.status_code}): {r.text}")
    
    addresses = r.json()
    if not addresses:
        raise RuntimeError(f"Keine Adresse für Pool {pool_lp_asset} gefunden.")
    pool_address = addresses[0]["address"]

    # 2. Aktive UTxOs an dieser Pool-Adresse abrufen
    utxos_url = f"{BLOCKFROST_URL}/addresses/{pool_address}/utxos"
    r = requests.get(utxos_url, headers=headers, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"Blockfrost Fehler bei UTxO-Abruf ({r.status_code}): {r.text}")
    
    utxos = r.json()

    # Den UTxO identifizieren, der das Pool-LP Token hält (das ist der Live-State des Pools)
    for u in utxos:
        units = {item["unit"]: int(item["quantity"]) for item in u["amount"]}
        if pool_lp_asset in units:
            return units

    raise RuntimeError(f"Kein aktives UTxO mit LP-Token an Adresse {pool_address} gefunden.")


def get_night_snek_ratio():
    """Fragt den NIGHT-SNEK Pool on-chain ab."""
    print("Rufe NIGHT/SNEK Pool-Daten live via Blockfrost ab...")
    amounts = get_pool_utxo_amounts(POOL_LP_NIGHT_SNEK)

    # NIGHT identifizieren: das Token, das weder lovelace, noch LP-Asset, noch SNEK ist
    night_amount = 0
    snek_amount = 0

    for unit, qty in amounts.items():
        if unit == SNEK_UNIT:
            snek_amount = qty / (10 ** DECIMALS_SNEK)
        elif unit != "lovelace" and unit != POOL_LP_NIGHT_SNEK:
            night_amount = qty / (10 ** DECIMALS_NIGHT)

    if night_amount == 0 or snek_amount == 0:
        raise RuntimeError(f"Konnte NIGHT oder SNEK im Pool nicht ermitteln: {amounts}")

    print(f"Pool-Zusammensetzung: NIGHT ({night_amount:,.2f}) / SNEK ({snek_amount:,.0f})")
    return snek_amount / night_amount


def check_crypto_prices():
    print("Starte Preisabfrage via Blockfrost on-chain...")
    try:
        ratio = get_night_snek_ratio()
        print(f"Aktuelles Verhältnis: 1 NIGHT = {ratio:.2f} SNEK")

        int_ratio = int(ratio)
        last_alerted = load_last_alert_threshold()
        print(f"Zuletzt alarmierter Wert im Speicher: {last_alerted}")

        if int_ratio > OBERE_GRENZE:
            if last_alerted is None or int_ratio > last_alerted:
                msg = f"📈 Krypto-Alarm (Steigt)! Verhältnis bei 1 NIGHT = {ratio:.2f} SNEK!"
                send_push_notification(msg)
                save_alert_threshold(int_ratio)
            else:
                print(f"Verhältnis ({int_ratio}) ist nicht höher als der letzte Alarm ({last_alerted}). Kein Spam.")
        elif int_ratio < UNTERE_GRENZE:
            if last_alerted is None or int_ratio < last_alerted:
                msg = f"📉 Krypto-Alarm (Fällt)! Verhältnis bei 1 NIGHT = {ratio:.2f} SNEK!"
                send_push_notification(msg)
                save_alert_threshold(int_ratio)
            else:
                print(f"Verhältnis ({int_ratio}) ist nicht tiefer als der letzte Alarm ({last_alerted}). Kein Spam.")
        else:
            print("Verhältnis im Normalbereich. Kein Alarm gesendet.")
            if last_alerted is not None:
                clear_alert_state()

    except Exception as e:
        print(f"Fehler bei der On-Chain Abfrage: {e}")


def get_night_ada_ratio():
    """Fragt den NIGHT/ADA-Pool on-chain ab und liefert: 1 NIGHT = X ADA."""
    print("Rufe NIGHT/ADA Pool-Daten live via Blockfrost ab...")
    amounts = get_pool_utxo_amounts(POOL_LP_NIGHT_ADA)

    ada_amount = amounts.get("lovelace", 0) / (10 ** DECIMALS_ADA)
    night_amount = 0

    for unit, qty in amounts.items():
        if unit != "lovelace" and unit != POOL_LP_NIGHT_ADA:
            night_amount = qty / (10 ** DECIMALS_NIGHT)
            break

    if ada_amount == 0 or night_amount == 0:
        raise RuntimeError(f"Konnte NIGHT/ADA Reserven nicht ermitteln: {amounts}")

    print(f"Pool-Zusammensetzung: ADA ({ada_amount:,.2f}) / NIGHT ({night_amount:,.2f})")
    return ada_amount / night_amount


def get_ada_usdm_ratio():
    """Fragt den ADA/USDM-Pool on-chain ab und liefert: 1 ADA = X USDM (≈ USD)."""
    print("Rufe ADA/USDM Pool-Daten live via Blockfrost ab...")
    amounts = get_pool_utxo_amounts(POOL_LP_ADA_USDM)

    ada_amount = amounts.get("lovelace", 0) / (10 ** DECIMALS_ADA)
    usdm_amount = amounts.get(USDM_UNIT, 0) / (10 ** DECIMALS_USDM)

    if ada_amount == 0 or usdm_amount == 0:
        raise RuntimeError(f"Konnte ADA/USDM Reserven nicht ermitteln: {amounts}")

    print(f"Pool-Zusammensetzung: ADA ({ada_amount:,.2f}) / USDM ({usdm_amount:,.2f})")
    return usdm_amount / ada_amount


def get_night_usd_price():
    night_in_ada = get_night_ada_ratio()
    ada_in_usd = get_ada_usdm_ratio()
    night_in_usd = night_in_ada * ada_in_usd

    print(f"1 NIGHT = {night_in_ada:.6f} ADA, 1 ADA = {ada_in_usd:.4f} USD "
          f"=> 1 NIGHT = ${night_in_usd:.6f}")
    return night_in_usd


def load_last_night_price():
    if os.path.exists(NIGHT_PREIS_STATE_FILE):
        try:
            with open(NIGHT_PREIS_STATE_FILE, "r") as f:
                content = f.read().strip()
                if content:
                    return float(content)
        except Exception as e:
            print(f"Fehler beim Lesen der NIGHT-Preisdatei: {e}")
    return None


def save_night_price(value):
    try:
        with open(NIGHT_PREIS_STATE_FILE, "w") as f:
            f.write(str(value))
        print(f"Neuer NIGHT-Referenzpreis gespeichert: {value}")
    except Exception as e:
        print(f"Fehler beim Schreiben der NIGHT-Preisdatei: {e}")


def check_night_price():
    print("Starte $NIGHT-Preisabfrage via Blockfrost (NIGHT/ADA * ADA/USDM)...")
    try:
        aktueller_preis = get_night_usd_price()
        print(f"Aktueller $NIGHT-Preis: ${aktueller_preis:.6f}")

        letzter_preis = load_last_night_price()
        if letzter_preis is None:
            print("Noch kein Referenzwert vorhanden. Lege nightpreis.txt neu an.")
            save_night_price(aktueller_preis)
            return

        print(f"Gespeicherter Referenzpreis: ${letzter_preis:.6f}")
        veraenderung_prozent = ((aktueller_preis - letzter_preis) / letzter_preis) * 100

        if veraenderung_prozent >= NIGHT_PROZENT:
            msg = (
                f"$Night um {veraenderung_prozent:.2f}% gestiegen von "
                f"${letzter_preis:.6f} auf ${aktueller_preis:.6f}"
            )
            send_push_notification(msg)
            save_night_price(aktueller_preis)
        elif veraenderung_prozent > 0:
            print(
                f"Preis ist um {veraenderung_prozent:.2f}% gestiegen, "
                f"das liegt unter der Schwelle von {NIGHT_PROZENT}%. Kein Alarm, kein Update."
            )
        else:
            print(
                f"Preis ist gefallen oder gleich geblieben ({veraenderung_prozent:.2f}%). "
                f"Kein Alarm, Referenzwert bleibt unverändert."
            )

    except Exception as e:
        print(f"Fehler bei der $NIGHT-Preisabfrage: {e}")


if __name__ == "__main__":
    print("=== SKRIPT-DURCHLAUF START ===")
    check_crypto_prices()
    check_night_price()
    print("=== SKRIPT-DURCHLAUF BEENDET ===")
    sys.exit(0)
