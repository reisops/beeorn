"""
BeeBee — Simulador de colmeia (Hive Simulator)

EN: Simulates a beehive's biological state (population, honey, temperature...)
    and publishes readings to an MQTT broker, exactly like a real sensor would.
PT: Simula o estado biológico de uma colmeia (população, mel, temperatura...)
    e publica as leituras num broker MQTT, do mesmo jeito que um sensor real faria.
"""

import os
import time
import random
import math
import json
import logging
import numpy as np
from datetime import datetime, UTC
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

# --- Config ---
# EN: Load settings from environment variables (.env file), never hardcoded.
# PT: Carrega as configurações de variáveis de ambiente (arquivo .env), nunca fixas no código.
load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
HIVE_ID = os.getenv("HIVE_ID", "hive-01")
MQTT_TOPIC = f"beebee/hives/{HIVE_ID}/telemetry"
INTERVAL_SECONDS = 10

# --- Logging ---
# EN: Structured logging instead of print() — includes timestamp and level (INFO/ERROR/...).
# PT: Log estruturado em vez de print() — já inclui hora e nível (INFO/ERROR/...).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("beebee.simulator")

# --- Physical/biological constants ---
# EN: Rough real-world approximations, for educational purposes.
# PT: Aproximações da vida real, com propósito educativo.
EMPTY_BOX_KG = 22.0
BEE_WEIGHT_KG = 0.0001
WAX_KG = 1.2

# --- Colony internal state ---
# EN: Weight/temperature/humidity are CONSEQUENCES of this state, not random numbers.
# PT: Peso/temperatura/umidade são CONSEQUÊNCIA desse estado, não números soltos.
state = {
    "population": 38000,
    "queen_health": 0.97,
    "honey_kg": 16.0,
    "pollen_kg": 2.0,
    "nectar_kg": 0.5,
    "hive_temp": 34.6,
    "hive_humidity": 58.0,
}


def time_of_day_factor():
    """
    EN: Returns an activity factor 0-1 based on the real clock (0 = night, 1 = midday peak).
    PT: Retorna um fator de atividade 0-1 baseado no horário real (0 = noite, 1 = pico do meio-dia).
    """
    hour = datetime.now().hour + datetime.now().minute / 60
    if 5 <= hour <= 21:
        return math.sin(math.pi * (hour - 5) / 16)
    return 0.0


def step():
    """
    EN: Advances the simulation by one tick — updates population's foraging,
        honey curing, temperature and humidity based on current activity.
    PT: Avança a simulação em um passo — atualiza forrageamento, cura do mel,
        temperatura e umidade com base na atividade atual.
    """
    activity = time_of_day_factor()

    # EN: Foragers collect nectar during the day.
    # PT: Campeiras coletam néctar durante o dia.
    forager_fraction = 0.35 * activity
    nectar_gain = forager_fraction * state["population"] * 0.000004
    state["nectar_kg"] += nectar_gain

    # EN: Nectar slowly cures into honey (loses water), mostly overnight.
    # PT: Néctar aos poucos vira mel (perde água), principalmente à noite.
    curing_rate = 0.02 if activity < 0.1 else 0.005
    cured = state["nectar_kg"] * curing_rate
    state["nectar_kg"] -= cured
    state["honey_kg"] += cured * 0.6

    # EN: Colony always consumes some honey for energy.
    # PT: A colônia sempre consome um pouco de mel pra energia.
    consumption = state["population"] * 0.0000003
    state["honey_kg"] = max(0, state["honey_kg"] - consumption)

    # EN: Internal temperature drifts toward a target influenced by activity.
    # PT: Temperatura interna caminha em direção a um alvo influenciado pela atividade.
    target_temp = 34.5 + activity * 1.0 + np.random.normal(0, 0.1)
    state["hive_temp"] += (target_temp - state["hive_temp"]) * 0.3

    # EN: Humidity rises with fresh nectar, falls with ventilation (high activity).
    # PT: Umidade sobe com néctar fresco, cai com ventilação (atividade alta).
    target_humidity = 60 - activity * 8 + nectar_gain * 20
    state["hive_humidity"] += (target_humidity - state["hive_humidity"]) * 0.2
    state["hive_humidity"] = min(max(state["hive_humidity"], 40), 75)

    # EN: Pollen trickles in during the day, consumed slowly.
    # PT: Pólen entra aos poucos durante o dia, consumido devagar.
    state["pollen_kg"] += forager_fraction * 0.00005
    state["pollen_kg"] = max(0, state["pollen_kg"] - state["population"] * 0.00000005)


def maybe_trigger_event():
    """
    EN: Rare random event — swarming (part of the colony leaves).
    PT: Evento raro e aleatório — enxameação (parte da colônia vai embora).
    """
    if random.random() < 0.0008:
        log.warning("EVENTO: Enxameação — parte da colônia deixou a colmeia")
        state["population"] = int(state["population"] * random.uniform(0.5, 0.65))
        state["honey_kg"] *= 0.9
        state["queen_health"] = min(1.0, state["queen_health"] + 0.02)


def total_weight():
    """
    EN: Total hive weight = box + wax + bees + honey + pollen + nectar.
    PT: Peso total da colmeia = caixa + cera + abelhas + mel + pólen + néctar.
    """
    bees_kg = state["population"] * BEE_WEIGHT_KG
    return EMPTY_BOX_KG + WAX_KG + bees_kg + state["honey_kg"] + state["pollen_kg"] + state["nectar_kg"]


def build_payload():
    """
    EN: Builds the JSON message that gets published to MQTT — mimics what a real sensor would send.
    PT: Monta a mensagem JSON publicada no MQTT — imita o que um sensor real enviaria.
    """
    return {
        "hive_id": HIVE_ID,
        "timestamp": datetime.now(UTC).isoformat() + "Z",
        "weight_kg": round(total_weight(), 3),
        "temp_c": round(state["hive_temp"], 2),
        "humidity_pct": round(state["hive_humidity"], 2),
        "population": state["population"],
        "honey_kg": round(state["honey_kg"], 3),
        "pollen_kg": round(state["pollen_kg"], 3),
        "nectar_kg": round(state["nectar_kg"], 3),
        "queen_health": round(state["queen_health"], 3),
        "activity": round(time_of_day_factor(), 3),
        # EN: Device telemetry (not hive data) — battery/signal, as a real IoT node would report.
        # PT: Telemetria do dispositivo (não da colmeia) — bateria/sinal, como um nó IoT real reportaria.
        "device_battery_pct": round(random.uniform(85, 100), 1),
        "device_rssi": random.randint(-80, -40),
    }


def main():
    # EN: Connect to the MQTT broker and start the publish loop.
    # PT: Conecta ao broker MQTT e inicia o loop de publicação.
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"simulator-{HIVE_ID}")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    log.info(f"Publicando simulação da {HIVE_ID} em '{MQTT_TOPIC}'")
    try:
        while True:
            step()
            maybe_trigger_event()
            payload = build_payload()
            client.publish(MQTT_TOPIC, json.dumps(payload), qos=1)
            log.info(
                f"peso={payload['weight_kg']}kg pop={payload['population']} "
                f"bateria={payload['device_battery_pct']}%"
            )
            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        log.info("Encerrando simulador...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
