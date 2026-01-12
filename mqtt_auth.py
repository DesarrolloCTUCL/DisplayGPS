import os
import json
from pathlib import Path
from dotenv import load_dotenv
from awscrt import io, mqtt
from awsiot import mqtt_connection_builder
import threading
mqtt_lock = threading.Lock()

# Cargar variables de entorno
load_dotenv()

# Variables globales desde el entorno
BUS_ID = int(os.getenv("BUS_ID"))
MQTT_ENDPOINT = os.getenv("MQTT_ENDPOINT")
CERT_NAME = os.getenv("CERT_NAME")

# Rutas de certificados
PATH_TO_CERT = f"/home/admin/DisplayGPS/Certificados/{CERT_NAME}certificate.pem.crt"
PATH_TO_KEY = f"/home/admin/DisplayGPS/Certificados/{CERT_NAME}private.pem.key"
PATH_TO_ROOT_CA = "/home/admin/DisplayGPS/Certificados/root-CA.crt"

# Archivo donde se guardan los mensajes pendientes
PENDIENTES_FILE = Path("/home/admin/DisplayGPS/pendientes_mqtt.json")

# -------------------------------------------------------------
# 🔹 FUNCIONES DE AUTENTICACIÓN Y CONEXIÓN MQTT
# -------------------------------------------------------------
def crear_conexion_mqtt():
    """Crea y devuelve una conexión MQTT autenticada con AWS IoT."""
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
# 🔹 FUNCIONES DE GESTIÓN DE MENSAJES PENDIENTES
# -------------------------------------------------------------
def cargar_pendientes():
    """Carga los mensajes pendientes desde el archivo JSON."""
    if PENDIENTES_FILE.exists():
        try:
            with open(PENDIENTES_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"⚠️ Error leyendo pendientes: {e}")
    return []

def guardar_pendiente(mensaje):
    """Guarda un mensaje pendiente en el archivo JSON."""
    pendientes = cargar_pendientes()
    pendientes.append(mensaje)
    try:
        with open(PENDIENTES_FILE, "w") as f:
            json.dump(pendientes, f, indent=2)
        print("💾 Mensaje guardado en pendientes_mqtt.json")
    except Exception as e:
        print(f"⚠️ No se pudo guardar pendiente: {e}")

def reenviar_pendientes(mqtt_connection, topic):
    pendientes = cargar_pendientes()
    if not pendientes:
        return

    enviados_ok = []

    for msg in pendientes:
        try:
            future, _ = mqtt_connection.publish(
                topic=topic,
                payload=json.dumps(msg),
                qos=mqtt.QoS.AT_LEAST_ONCE
            )

            future.result(timeout=10)
            print(f"📤 Reenviado CONFIRMADO: {msg}")
            enviados_ok.append(msg)

        except Exception as e:
            print("⚠️ Error reenviando pendiente")
            print(f"   Tipo: {type(e)}")
            print(f"   Detalle: {repr(e)}")
            break  # NO sigas, la conexión está inestable

    restantes = [m for m in pendientes if m not in enviados_ok]
    with open(PENDIENTES_FILE, "w") as f:
        json.dump(restantes, f, indent=2)



def publicar_mensaje(mqtt_connection, topic, mensaje):
    with mqtt_lock:
        reenviar_pendientes(mqtt_connection, topic)
        try:
            future, _ = mqtt_connection.publish(
                topic=topic,
                payload=json.dumps(mensaje),
                qos=mqtt.QoS.AT_LEAST_ONCE
            )
            future.result(timeout=10)
            print(f"📡 Publicado CONFIRMADO MQTT: {mensaje}")
            return True
        except Exception as e:
            print("⚠️ Error REAL al publicar MQTT")
            print(f"   Tipo: {type(e)}")
            print(f"   Detalle: {repr(e)}")
            guardar_pendiente(mensaje)
            return False
