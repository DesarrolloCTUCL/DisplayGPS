import socket
import time
from datetime import datetime
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
import json
#from control_points import control_points
from puntoscontrol import obtener_chainpc_por_itinerario
from ComandosNextion import send_to_nextion,send_to_nextionPlay,nextion,last_sent_texts
from despachos import obtener_datos_itinerario
from config import BUS_ID,radio,mqttpass,CERT

from funciones import calcular_distancia,parse_gprmc,verificar_itinerario_actual
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



def actualizar_hora_local():
    while True:
        with gps_lock:
            activo = gps_activo
        hora_local = datetime.now()
        send_to_nextion(hora_local.strftime("%H:%M:%S"), "t0")
        send_to_nextion(hora_local.strftime("%Y-%m-%d"), "t1")
        verificar_itinerario_actual(hora_local.strftime("%d/%m/%Y"), hora_local.strftime("%H:%M:%S"))
        time.sleep(1)

def iniciar_gps_display():
    # Conectar a AWS IoT con reintentos cada 5 segundos si falla
    while True:
        try:
            print("🔌 Intentando conectar a AWS IoT...")
            send_to_nextion("Conectando...", "t2")
            connect_future = mqtt_connection.connect()
            connect_future.result(timeout=10)
            print("✅ Conectado a AWS IoT Core")
            obtener_datos_itinerario()
            last_sent_texts.clear()
            send_to_nextion(CLIENT_ID, "t2")
            break  # Salir del bucle si se conectó correctamente
        except Exception as e:
            print(f"❌ Error de conexión: {e}")
            send_to_nextion("Sin conexión", "t2")
            print("🔄 Reintentando en 5 segundos...")
            time.sleep(5)

    TOPIC = "buses/gps"

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
                            hora_gps = parsed_data["hora_obj"]
                            hora_local = datetime.now()
                            diferencia = abs((hora_local - hora_gps).total_seconds())
                            if diferencia > 10:
                                print(f"Ignorando trama atrasada: {parsed_data['hora']} (diferencia: {diferencia} segundos)")
                                continue

                            with gps_lock:
                                gps_activo = True

                            send_to_nextion(parsed_data['fecha'], "t1")
                            send_to_nextion(parsed_data['hora'], "t0")
                            verificar_itinerario_actual(hora_local.strftime("%d/%m/%Y"), hora_local.strftime("%H:%M:%S"))
                            itinerarios = obtener_chainpc_por_itinerario()
                            
                            for id_itin, data in itinerarios.items():
                                for punto in data["puntos"]:
                                    name = punto["name"]
                                    lat = punto["lat"]
                                    lon = punto["long"]

                                    distancia = calcular_distancia(parsed_data['latitud'], parsed_data['longitud'], lat, lon)
                                    if distancia <= 205:
                                        if name not in puntos_notificados:
                                            print(f"Punto de control alcanzado: {name}, enviando comando de audio...")
                                            send_to_nextion(name, "g0")
                                            send_to_nextionPlay(0, punto["numero"] - 1)
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
                                            puntos_notificados.add(name)
                                        break
                                    else:
                                        if name in puntos_notificados:
                                            puntos_notificados.remove(name)
                        else:
                            with gps_lock:
                                gps_activo = False

    except KeyboardInterrupt:
        print("\nCerrando servidor y conexión con Nextion")
        nextion.close()
