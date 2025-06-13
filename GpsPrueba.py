import time
import json
import serial
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
from control_points import control_points
from ComandosNextion import send_to_nextion,send_to_nextionPlay
import threading

# Configuración de la pantalla Nextion
nextion = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)

# Configuración de AWS IoT MQTT
ENDPOINT = "a3okayccf7oceg-ats.iot.us-east-1.amazonaws.com"
CLIENT_ID = "1539"
PATH_TO_CERT = "/home/admin/Certificados/RTDESA/RTDESA.cert.pem"
PATH_TO_KEY = "/home/admin/Certificados/RTDESA/RTDESA.private.key"
PATH_TO_ROOT_CA = "/home/admin/Certificados/RTDESA/root-CA.crt"

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

# Variables de sincronización
gps_activo = False
gps_lock = threading.Lock()

# Función para calcular distancia entre coordenadas
def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# Función para parsear tramas GPRMC
def parse_gprmc(trama):
    parts = trama.split(',')
    if parts[0] != "$GPRMC":
        return None
    try:
        if parts[2] != 'A':
            return None

        def convertir_a_decimal(gm, dir, is_longitud=False):
            if not gm:
                return None
            grados = int(gm[:3] if is_longitud else gm[:2])
            minutos = float(gm[3:] if is_longitud else gm[2:])
            decimal = grados + minutos / 60
            return -decimal if dir in ['S', 'W'] else decimal

        lat = convertir_a_decimal(parts[3], parts[4])
        lon = convertir_a_decimal(parts[5], parts[6], True)
        if lat is None or lon is None:
            return None

        hora = parts[1].split('.')[0]
        fecha = parts[9]
        dt = datetime.strptime(fecha + hora, "%d%m%y%H%M%S") - timedelta(hours=5)

        vel_nudos = float(parts[7]) if parts[7] else 0.0
        vel_kmh = round(vel_nudos * 1.852, 2)

        return {
            "fecha": dt.strftime("%Y-%m-%d"),
            "hora": dt.strftime("%H:%M:%S"),
            "hora_obj": dt,
            "latitud": round(lat, 6),
            "longitud": round(lon, 6),
            "velocidad_kmh": vel_kmh
        }
    except:
        return None



# Hilo para actualizar hora local si GPS no está activo
def actualizar_hora_local():
    while True:
        with gps_lock:
            activo = gps_activo
        if not activo:
            ahora = datetime.now()
            send_to_nextion(ahora.strftime("%H:%M:%S"), "t0")
            send_to_nextion(ahora.strftime("%Y-%m-%d"), "t1")
        time.sleep(1)


def decimal_a_grados_minutos(coord, es_longitud=False):
    grados = int(abs(coord))
    minutos = (abs(coord) - grados) * 60
    if es_longitud:
        # longitud: 3 dígitos para grados
        return f"{grados:03d}{minutos:06.3f}"
    else:
        # latitud: 2 dígitos para grados
        return f"{grados:02d}{minutos:06.3f}"

def crear_trama_simulada(lat_decimal, lon_decimal):
    now = datetime.utcnow()
    hora_gps = now.strftime("%H%M%S.00")
    fecha_gps = now.strftime("%d%m%y")

    lat_grados_minutos = decimal_a_grados_minutos(lat_decimal, es_longitud=False)
    lat_dir = 'N' if lat_decimal >= 0 else 'S'

    lon_grados_minutos = decimal_a_grados_minutos(lon_decimal, es_longitud=True)
    lon_dir = 'E' if lon_decimal >= 0 else 'W'

    base = "$GPRMC,{hora},A,{lat},{lat_dir},{lon},{lon_dir},0.0,0.0,{fecha},,,*1C\r\n"
    return base.format(hora=hora_gps, lat=lat_grados_minutos, lat_dir=lat_dir,
                       lon=lon_grados_minutos, lon_dir=lon_dir, fecha=fecha_gps)

# Conectar a AWS
print("Conectando a AWS IoT...")
connect_future = mqtt_connection.connect()
connect_future.result()
print("✅ Conectado a AWS IoT Core")
TOPIC = "buses/gps"

# Mostrar ID del bus en pantalla
send_to_nextion(CLIENT_ID, "t2")

# Iniciar hilo para hora local
threading.Thread(target=actualizar_hora_local, daemon=True).start()
puntos_notificados = set()
# Bucle de simulación
try:
    while True:
        # Trama simul<aada
        trama_simulada =  crear_trama_simulada(-3.98242, -79.1998)
        parsed_data = parse_gprmc(trama_simulada)
        dato_nextion = "5"  # Simulación de valor retornado

        if parsed_data:
            hora_local = datetime.now()
            hora_gps = parsed_data["hora_obj"]
            diferencia = abs((hora_local - hora_gps).total_seconds())

            #send_to_nextion(f"{parsed_data['velocidad_kmh']} km/h", "t16")
            send_to_nextion(parsed_data["fecha"], "t1")

            if diferencia > 5:
                send_to_nextion(parsed_data["hora"], "t0")
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
            print("❌ Trama inválida")

        time.sleep(1)

except KeyboardInterrupt:
    print("⛔ Finalizando simulación")
    nextion.close()

