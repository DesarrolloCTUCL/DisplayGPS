import socket
import time
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
import json
from control_points import control_points
from ComandosNextion import send_to_nextion,send_to_nextionPlay,dato_nextion,nextion
from config import BUS_ID,radio,mqttpass,CERT
import threading

# Configuración del servidor de sockets
HOST = '0.0.0.0'  # Escucha en todas las interfaces de red
PORT = 8500  # Mismo puerto configurado en el Teltonika
# Configuración de AWS IoT MQTT
ENDPOINT = mqttpass  # Asegúrate de usar el endpoint correcto
CLIENT_ID = str(BUS_ID)  # Usa un nombre único
PATH_TO_CERT = f"/home/admin/DisplayGPS/Certificados/{CERT}.cert.pem"
PATH_TO_KEY = f"/home/admin/DisplayGPS/Certificados/{CERT}.private.key"
PATH_TO_ROOT_CA = "/home/admin/DisplayGPS/Certificados/root-CA.crt"
# Configuración de MQTT
event_loop_group = io.EventLoopGroup(1)
host_resolver = io.DefaultHostResolver(event_loop_group)
client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

mqtt_connection = mqtt_connection_builder.mtls_from_path(
    endpoint=ENDPOINT,
    cert_filepath=PATH_TO_CERT,
    pri_key_filepath=PATH_TO_KEY,
    client_bootstrap=client_bootstrap,
    ca_filepath=PATH_TO_ROOT_CA,
    client_id=CLIENT_ID,
    clean_session=False,
    keep_alive_secs=30,
)

# Variables para controlar estado GPS y sincronización de hilo
gps_activo = False
gps_lock = threading.Lock()

# Función para calcular distancia entre dos coordenadas (Haversine)
def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371000  # Radio de la Tierra en metros
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

# Función para interpretar tramas $GPRMC
def parse_gprmc(trama):
    parts = trama.split(',')
    if parts[0] != "$GPRMC":
        print("Trama no válida")
        return None

    try:
        estado = parts[2]
        if estado != 'A':  # 'A' indica datos válidos
            print("Trama GPRMC no activa")
            return None

        hora_utc = parts[1]  # Ej: 134547.00
        latitud = parts[3]
        lat_dir = parts[4]
        longitud = parts[5]
        lon_dir = parts[6]
        fecha_utc = parts[9]  # Ej: 010525
        velocidad_nudos = float(parts[7]) if parts[7] else 0.0
        velocidad_kmh = round(velocidad_nudos * 1.852, 2)

        def convertir_a_decimal(grados_minutos, direccion, is_longitud=False):
            if not grados_minutos:
                return None
            grados = int(grados_minutos[:3] if is_longitud else grados_minutos[:2])
            minutos = float(grados_minutos[3:] if is_longitud else grados_minutos[2:])
            decimal = grados + minutos / 60
            if direccion in ['S', 'W']:
                decimal *= -1
            return round(decimal, 6)

        latitud_decimal = convertir_a_decimal(latitud, lat_dir)
        longitud_decimal = convertir_a_decimal(longitud, lon_dir, is_longitud=True)

        if latitud_decimal is None or longitud_decimal is None:
            print("Error al convertir coordenadas")
            return None

        # Armar datetime con hora y fecha
        hora_clean = hora_utc.split('.')[0]  # "134547.00" → "134547"
        fecha_obj = datetime.strptime(fecha_utc + hora_clean, "%d%m%y%H%M%S")
        hora_local = fecha_obj - timedelta(hours=5)  # Ajuste a hora local

        return {
            "fecha": hora_local.strftime("%Y-%m-%d"),
            "hora": hora_local.strftime("%H:%M:%S"),
            "hora_obj": hora_local,
            "latitud": latitud_decimal,
            "longitud": longitud_decimal,
            "velocidad_kmh": velocidad_kmh
        }

    except (IndexError, ValueError) as e:
        print(f"Error al parsear GPRMC: {e}")
        return None


def actualizar_hora_local():
    while True:
        with gps_lock:
            activo = gps_activo
        if not activo:
            hora_local = datetime.now()
            send_to_nextion(hora_local.strftime("%H:%M:%S"), "t0")
            send_to_nextion(hora_local.strftime("%Y-%m-%d"), "t1")
            
        time.sleep(1)

def iniciar_gps_display():
    # Conectar a AWS IoT
    print("Conectando a AWS IoT...")
    connect_future = mqtt_connection.connect()
    connect_future.result()
    print("✅ Conectado a AWS IoT Core")
    TOPIC = "buses/gps"

    send_to_nextion(CLIENT_ID, "t2")

    # Iniciar hilo para actualizar hora local cuando GPS inactivo
    threading.Thread(target=actualizar_hora_local, daemon=True).start()
    puntos_notificados = set()
    # Iniciar el servidor de sockets
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind((HOST, PORT))
            server.listen()
            print(f"Esperando conexiones en {HOST}:{PORT}...")

            while True:
                conn, addr = server.accept()
                with conn:
                  
                    while True:
                        data = conn.recv(1024)
                        if not data:
                            break
                        trama = data.decode().strip()
                        parsed_data = parse_gprmc(trama)

                        if parsed_data:
                            with gps_lock:
                                gps_activo = True

                            hora_local = datetime.now()
                            hora_gps = parsed_data["hora_obj"]

                            diferencia = abs((hora_local - hora_gps).total_seconds())
                            send_to_nextion(parsed_data['fecha'], "t1")

                            if diferencia > 5:
                                send_to_nextion(f"{parsed_data['hora']}", "t0")
                            else:
                                send_to_nextion(hora_local.strftime("%H:%M:%S"), "t0")

                            for id, name, lat, lon in control_points():
                                distancia = calcular_distancia(parsed_data['latitud'], parsed_data['longitud'], lat, lon)
                                if distancia <= 55:
                                    if name not in puntos_notificados:
                                        print(f"Punto de control alcanzado: {name}, enviando comando de audio...")
                                        send_to_nextion(name, "g0")
                                        send_to_nextionPlay(0, id)

                                        mensaje_mqtt = {
                                            "BusID": CLIENT_ID,
                                            "fecha": parsed_data["fecha"],
                                            "hora": parsed_data["hora"],
                                            "punto_control": name,
                                            "latitud": parsed_data["latitud"],
                                            "longitud": parsed_data["longitud"],
                                            "velocidad_kmh": parsed_data["velocidad_kmh"]
                                        }

                                        mqtt_connection.publish(
                                            topic=TOPIC,
                                            payload=json.dumps(mensaje_mqtt),
                                            qos=mqtt.QoS.AT_LEAST_ONCE
                                        )
                                        print(f"📡 Publicado a MQTT: {mensaje_mqtt}")

                                        puntos_notificados.add(name)  # Marca que ya notificaste este punto
                                    break
                                else:
                                    # Si estás fuera del rango, removemos el punto de la lista para que pueda ser notificado de nuevo cuando regreses
                                    if name in puntos_notificados:
                                        puntos_notificados.remove(name)
                        else:
                            with gps_lock:
                                gps_activo = False

    except KeyboardInterrupt:
        print("\nCerrando servidor y conexión con Nextion")
        nextion.close()