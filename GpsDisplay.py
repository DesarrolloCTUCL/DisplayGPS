import socket
import time
import os
from dotenv import load_dotenv
from datetime import datetime,timedelta
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
import json
from ComandosNextion import send_to_nextion, send_to_nextionPlay, nextion, last_sent_texts
from despachos import obtener_datos_itinerario
from funciones import calcular_distancia, parse_gprmc, verificar_itinerario_actual,obtener_chainpc_por_itinerario
import threading


# Cargar las variables desde el archivo .env
load_dotenv()

BUS_ID = int(os.getenv("BUS_ID"))
RADIO = int(os.getenv("RADIO"))
MQTT_ENDPOINT = os.getenv("MQTT_ENDPOINT")
CERT_NAME = os.getenv("CERT_NAME")


# Configuración del servidor de sockets
HOST = '0.0.0.0'  # Escucha en todas las interfaces de red
PORT = 8500       # Mismo puerto configurado en el Teltonika

# Configuración de AWS IoT MQTT
ENDPOINT = MQTT_ENDPOINT
CLIENT_ID = str(BUS_ID)
PATH_TO_CERT = f"/home/admin/DisplayGPS/Certificados/{CERT_NAME}certificate.pem.crt"
PATH_TO_KEY = f"/home/admin/DisplayGPS/Certificados/{CERT_NAME}private.pem.key"
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
        send_to_nextion(CLIENT_ID, "t2")
        verificar_itinerario_actual(hora_local.strftime("%d/%m/%Y"), hora_local.strftime("%H:%M:%S"))
        time.sleep(1)

def iniciar_gps_display():
    threading.Thread(target=actualizar_hora_local, daemon=True).start()

    # Conectar a AWS IoT con reintentos cada 5 segundos si falla
    ruta_iniciada = False
    ruta_anterior = None
    while True:
        try:
            print("[Main] Sistema iniciado. Esperando comandos...")
            send_to_nextion("Espere", "g0")
            connect_future = mqtt_connection.connect()
            connect_future.result(timeout=10)
            print("✅ Conectado a AWS IoT Core")
            obtener_datos_itinerario()
            last_sent_texts.clear()
            break
        except Exception as e:
            hora_local = datetime.now()
            print(f"❌ Error de conexión: {e}")       
            send_to_nextion("No señal", "g0")
            print("🔄 Reintentando en 5 segundos...")
            time.sleep(5)

    TOPIC = f"buses/gps/{BUS_ID}"

    # Iniciar hilo para actualizar hora local
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
                            if diferencia > 3:
                                continue  # Ignorar trama vieja

                            with gps_lock:
                                gps_activo = True

                            send_to_nextion(parsed_data['fecha'], "t1")
                            send_to_nextion(parsed_data['hora'], "t0")
                            verificar_itinerario_actual(hora_local.strftime("%d/%m/%Y"), hora_local.strftime("%H:%M:%S"))
                            hora_actual_dt = datetime.strptime(parsed_data['hora'], "%H:%M:%S")

                            turnos = obtener_chainpc_por_itinerario()
                            itinerario_activo = None
                            id_itin_activo = None

                            for id_itin, data in sorted(turnos.items(), key=lambda x: datetime.strptime(x[1]['hora_despacho'], "%H:%M:%S"), reverse=True):
                                hora_despacho_dt = datetime.strptime(data["hora_despacho"], "%H:%M:%S")
                                hora_fin_dt = datetime.strptime(data["hora_fin"], "%H:%M:%S")

                                # Márgenes
                                margen_inicio = timedelta(minutes=2)   # 2 min antes del inicio
                                margen_final = timedelta(minutes=10)   # 10 min después del fin
                                hora_despacho_margen = hora_despacho_dt - margen_inicio
                                hora_fin_margen = hora_fin_dt + margen_final

                                # Verificar si el itinerario está activo
                                if hora_despacho_dt <= hora_fin_dt:
                                    activo = hora_despacho_margen <= hora_actual_dt <= hora_fin_margen
                                else:  # itinerario que cruza medianoche
                                    activo = hora_actual_dt >= hora_despacho_margen or hora_actual_dt <= hora_fin_margen

                                if activo:
                                    itinerario_activo = data
                                    id_itin_activo = id_itin


                            if itinerario_activo:
                                #print(f"🧭 Itinerario {id_itin_activo} con rango horario {itinerario_activo['hora_despacho']} - {itinerario_activo['hora_fin']} (Activo)")
                                shift_id = itinerario_activo.get("shift_id")  # Obtén shift_id del itinerario activo
                                puntos = itinerario_activo.get("puntos", [])

                                # Mostrar primer punto de control solo cuando inicia o cambia el itinerario
                                if not ruta_iniciada or ruta_anterior != id_itin_activo:
                                    print(f"🔁 Ruta iniciada = {ruta_iniciada}, anterior = {ruta_anterior}, actual = {id_itin_activo}")
                                    if puntos:
                                        primer_punto = puntos[0]
                                        nombre = primer_punto.get("name", "Inicio")
                                        hora_prog = primer_punto.get("hora", "--:--:--")
                                        send_to_nextion(nombre, "g0")
                                        send_to_nextion(hora_prog, "t5")
                                        print(f"🟢 Mostrando primer punto de control al iniciar ruta: {nombre}")
                                    ruta_iniciada = True
                                    ruta_anterior = id_itin_activo
                            else:
                                puntos = []
                                send_to_nextion("ESPERANDO PRÓXIMA RUTA", "g0")
                                send_to_nextion("--:--:--", "t5")
                                ruta_iniciada = False
                                ruta_anterior = None


                            for punto in puntos:
                                name = punto.get("name", "Sin nombre")
                                lat = punto.get("lat")
                                lon = punto.get("long")
                                numero = punto.get("numero")
                                radius = punto.get("radius",50)

                                if numero is None:
                                    continue

                                distancia = calcular_distancia(parsed_data['latitud'], parsed_data['longitud'], lat, lon)
                                if distancia <= radius:
                                    if name not in puntos_notificados:
                                        print(f"Punto de control alcanzado: {name}, enviando comando de audio...")
                                        #send_to_nextion(name, "g0")
                                        send_to_nextionPlay(0, int(numero) - 1)

                                        # Buscar siguiente punto
                                        index_actual = next((i for i, p in enumerate(puntos) if p.get("numero") == numero), None)
                                        if index_actual is not None and index_actual + 1 < len(puntos):
                                            siguiente_punto = puntos[index_actual + 1]
                                            siguiente_nombre = siguiente_punto.get("name", "Siguiente")
                                            siguiente_hora = siguiente_punto.get("hora", "--:--:--")

                                            send_to_nextion(siguiente_nombre, "g0")  # Nombre del siguiente punto
                                            send_to_nextion(siguiente_hora, "t5")    # Hora programada del siguiente punto
                                        else:
                                            send_to_nextion("FIN", "g0")
                                            send_to_nextion("--:--:--", "t5")

                                        mensaje_mqtt = {
                                            "BusID": CLIENT_ID,
                                            "datetime": f"{parsed_data['fecha']} {parsed_data['hora']}",  # ej. '2025-07-18 14:35:22'
                                            "punto_control_id": numero,
                                            "punto_controlname": name,
                                            "shift_id": shift_id,  # Aquí agregas shift_id
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
