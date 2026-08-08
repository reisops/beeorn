"""
BeeBee — Ingestor

EN: Subscribes to MQTT hive telemetry and writes each reading into InfluxDB.
    This is the ONLY piece that knows about the database — sensors (real or
    simulated) never talk to InfluxDB directly, only to MQTT.
PT: Assina a telemetria das colmeias no MQTT e grava cada leitura no InfluxDB.
    Essa é a ÚNICA peça que conhece o banco — sensores (reais ou simulados)
    nunca falam direto com o InfluxDB, só com o MQTT.
"""

import os
import json
import logging
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
# EN: "+" is an MQTT wildcard — matches any hive ID, already ready for multiple hives.
# PT: "+" é um coringa MQTT — casa com qualquer ID de colmeia, já pronto pra várias colmeias.
MQTT_TOPIC = "beebee/hives/+/telemetry"

INFLUX_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUX_ORG = os.getenv("INFLUXDB_ORG", "beebee-org")
INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET", "hive-data")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("beebee.ingestor")

influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)


def on_connect(client, userdata, flags, reason_code, properties):
    log.info(f"Conectado ao broker MQTT (código {reason_code}). Assinando '{MQTT_TOPIC}'...")
    client.subscribe(MQTT_TOPIC, qos=1)


def on_message(client, userdata, msg):
    # EN: Parse the JSON payload and write it as a point in InfluxDB.
    # PT: Interpreta o JSON recebido e grava como um ponto no InfluxDB.
    try:
        data = json.loads(msg.payload.decode())
        hive_id = data.get("hive_id", "unknown")

        point = Point("hive_metrics").tag("hive_id", hive_id)
        for field in ["weight_kg", "temp_c", "humidity_pct", "honey_kg",
                      "pollen_kg", "nectar_kg", "queen_health", "activity",
                      "device_battery_pct"]:
            if field in data:
                point = point.field(field, float(data[field]))
        if "population" in data:
            point = point.field("population", int(data["population"]))
        if "device_rssi" in data:
            point = point.field("device_rssi", int(data["device_rssi"]))

        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        log.info(f"Gravado: {hive_id} | peso={data.get('weight_kg')}kg")

    except Exception as e:
        log.error(f"Erro ao processar mensagem: {e}")


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="beebee-ingestor")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    log.info("Ingestor iniciado.")
    client.loop_forever()


if __name__ == "__main__":
    main()
