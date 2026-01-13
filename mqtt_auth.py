import os
import json
from pathlib import Path
from dotenv import load_dotenv
from awscrt import io, mqtt
from awsiot import mqtt_connection_builder
import threading

mqtt_lock = threading.Lock()

# -------------------------------------------------------------
# Cargar entorno
# -------------------------------------------------------------
load_dotenv()

BUS_ID = int(os.getenv("BUS_ID"))
MQTT_ENDPOINT = os.getenv("MQTT_ENDPOINT")
CERT_NAME = os.getenv("CERT_NAME")

PATH_TO_CERT = f"/home/admin/DisplayGPS/Certificados/{CERT_NAME}certificate.pem.crt"
PATH_TO_KEY = f"/home/admin/DisplayGPS/Certificados/{CERT_NAME}private.pem.key"
PATH_TO_ROOT_CA = "/home/admin/DisplayGPS/Certificados/root-CA.crt"

PENDIENTES_FILE = Path("/home/admin/DisplayGPS/pendientes_mqtt.json")

# -------------------------------------------------------------
# MQTT
# -------------------------------------------------------------
def crear_conexion_mqtt():
    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=MQTT_ENDPOINT,
        cert_filepath=PATH_TO_CERT,
        pri_key_filepath=PATH_TO_KEY,
        client_bootstrap=client_bootstrap,
        ca_filepath=PATH_TO_ROOT_CA,
        client_id=str(BUS_ID),
        clean_session=False,
        keep_alive_secs=30,
    )

    return mqtt_connection, BUS_ID

# -------------------------------------------------------------
# Pendientes
# -------------------------------------------------------------
def cargar_pendientes():
    if PENDIENTES_FILE.exists():
        try:
            with open(PENDIENTES_FILE, "r") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            pass
    return []

def guardar_pendiente(mensaje):
    pendientes = cargar_pendientes()
    pendientes.append(mensaje)

    with open(PENDIENTES_FILE, "w") as f:
        json.dump(pendientes, f, indent=2)

    print("💾 Mensaje guardado en pendientes_mqtt.json")

def eliminar_pendientes(enviados):
    if not enviados:
        return

    pendientes = cargar_pendientes()
    restantes = [p for p in pendientes if p not in enviados]

    with open(PENDIENTES_FILE, "w") as f:
        json.dump(restantes, f, indent=2)

# -------------------------------------------------------------
# Reenvío (NO bloqueante)
# -------------------------------------------------------------
def reenviar_pendientes(mqtt_connection, topic):
    pendientes = cargar_pendientes()
    if not pendientes:
        return

    enviados = []

    for msg in pendientes:
        try:
            mqtt_connection.publish(
                topic=topic,
                payload=json.dumps(msg),
                qos=mqtt.QoS.AT_LEAST_ONCE
            )
            enviados.append(msg)
        except Exception:
            break  # red caída → salir

    eliminar_pendientes(enviados)

# -------------------------------------------------------------
# Publicar mensaje
# -------------------------------------------------------------
def publicar_mensaje(mqtt_connection, topic, mensaje):
    with mqtt_lock:
        try:
            future, packet_id = mqtt_connection.publish(
                topic=topic,
                payload=json.dumps(mensaje),
                qos=mqtt.QoS.AT_LEAST_ONCE
            )

            # ⏳ Esperar confirmación REAL
            future.result(timeout=5)

            print(f"📤 MQTT enviado: {mensaje}")
            return True

        except Exception as e:
            print("⚠️ MQTT NO ENVIADO, guardando pendiente")
            print(f"   Tipo: {type(e)}")
            print(f"   Detalle: {e}")

            guardar_pendiente(mensaje)
            return False
