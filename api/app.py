"""
Beeorn — API

EN: Reads hive readings from InfluxDB and exposes them as JSON — one endpoint
    per hive, plus one that lists all hives currently reporting (the "fleet").
PT: Lê leituras de colmeias no InfluxDB e expõe como JSON — um endpoint por
    colmeia, além de um que lista todas as colmeias reportando ("a frota").
"""

import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient

load_dotenv()

INFLUX_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUX_ORG = os.getenv("INFLUXDB_ORG", "beeorn-org")
INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET", "hive-data")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("beeorn.api")

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:8000"}})

FIELDS = ["weight_kg", "temp_c", "humidity_pct", "population",
          "honey_kg", "pollen_kg", "nectar_kg", "queen_health", "activity",
          "device_battery_pct", "device_rssi"]


def get_latest(hive_id):
    safe_hive_id = hive_id.replace("\\", "\\\\").replace('"', '\\"')
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -10m)
      |> filter(fn: (r) => r._measurement == "hive_metrics")
      |> filter(fn: (r) => r.hive_id == "{safe_hive_id}")
      |> last()
    '''
    with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
        tables = client.query_api().query(query, org=INFLUX_ORG)
        result = {}
        for table in tables:
            for record in table.records:
                result[record.get_field()] = record.get_value()
        return result


def classify_status(data):
    weight = data.get("weight_kg", 35)
    temp = data.get("temp_c", 34.5)
    population = data.get("population", 35000)

    if temp < 32 or temp > 37 or population < 15000:
        return "alerta"
    elif weight < 30 or population < 25000:
        return "atencao"
    return "normal"


@app.route("/api/hives")
def list_hives():
    # EN: Discover which hive_ids have reported data in the last 10 minutes.
    # PT: Descobre quais hive_ids reportaram dado nos últimos 10 minutos.
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -10m)
      |> filter(fn: (r) => r._measurement == "hive_metrics")
      |> filter(fn: (r) => r._field == "weight_kg")
      |> group(columns: ["hive_id"])
      |> last()
    '''
    with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
        tables = client.query_api().query(query, org=INFLUX_ORG)
        hive_ids = sorted({record.values.get("hive_id") for table in tables for record in table.records})

    hives = []
    for hive_id in hive_ids:
        data = get_latest(hive_id)
        if data:
            hives.append({
                "hive_id": hive_id,
                "status": classify_status(data),
                "weight_kg": data.get("weight_kg"),
                "population": data.get("population"),
                "device_battery_pct": data.get("device_battery_pct"),
            })

    return jsonify({"hives": hives, "count": len(hives)})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "beeorn-api"})


@app.route("/api/hive/<hive_id>/status")
def hive_status(hive_id):
    data = get_latest(hive_id)
    if not data:
        log.warning(f"Sem dados para {hive_id}")
        return jsonify({"error": "sem dados ainda"}), 404

    response = {f: data.get(f) for f in FIELDS}
    response["hive_id"] = hive_id
    response["status"] = classify_status(data)
    return jsonify(response)


if __name__ == "__main__":
    log.info("Iniciando API Beeorn...")
    app.run(host="0.0.0.0", port=5000, debug=False)
