import sqlite3
import json
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from db import cargar_desde_sqlite 
from ComandosNextion import send_to_nextion,send_to_nextionPlay,nextion,last_sent_texts

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
           # print("Trama GPRMC no activa")
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

def formatear_fecha(fecha_ddmmyyyy):
    # Convierte '15/07/2025' a objeto datetime
    dt = datetime.strptime(fecha_ddmmyyyy, "%d/%m/%Y")
    # Retorna string en formato '2025-07-15'
    return dt.strftime("%Y-%m-%d")

def verificar_itinerario_actual(fecha_actual, hora_actual):
    fecha_sqlite = formatear_fecha(fecha_actual)
    codigo, itinerarios = cargar_desde_sqlite(fecha_sqlite)
    for item in itinerarios:
        hora_inicio = item["hora_despacho"]
        hora_fin = item["hora_fin"]
        if hora_inicio and hora_fin:
            if hora_inicio <= hora_actual <= hora_fin:
                send_to_nextion(hora_inicio, "t3")
                send_to_nextion(hora_fin, "t4")
                send_to_nextion(item["recorrido"], "t6")
                break


def obtener_chainpc_por_itinerario():
    """
    Extrae cada itinerario con su recorrido, hora_despacho, hora_fin, shift y los puntos chainpc filtrados
    por su horario. Retorna un diccionario estructurado por id_itinerario.
    """
    conn = sqlite3.connect('itinerarios.db')
    cursor = conn.cursor()
    cursor.execute('SELECT recorrido, hora_despacho, hora_fin, chainpc, shift_id FROM itinerarios')
    filas = cursor.fetchall()
    conn.close()

    itinerarios = {}
    id_itinerario = 1
    fmt = "%H:%M:%S"

    for recorrido, hora_despacho, hora_fin, chainpc_json, shift_id in filas:
        if not chainpc_json:
            continue
        try:
            puntos = json.loads(chainpc_json)
            try:
                hora_despacho_dt = datetime.strptime(hora_despacho, fmt)
                hora_fin_dt = datetime.strptime(hora_fin, fmt)
            except:
                continue

            puntos_filtrados = []

            for punto in puntos:
                if "hora" not in punto:
                    continue
                try:
                    hora_punto_dt = datetime.strptime(punto['hora'], fmt)
                except:
                    continue

                if hora_despacho_dt <= hora_fin_dt:
                    dentro = hora_despacho_dt <= hora_punto_dt <= hora_fin_dt
                else:
                    dentro = hora_punto_dt >= hora_despacho_dt or hora_punto_dt <= hora_fin_dt

                if dentro:
                    punto["datetime"] = datetime.now().isoformat()  # <- Agrega datetime si lo necesitas
                    puntos_filtrados.append(punto)

            itinerarios[id_itinerario] = {
                "recorrido": recorrido,
                "hora_despacho": hora_despacho,
                "hora_fin": hora_fin,
                "shift_id": shift_id,
                "puntos": puntos_filtrados
            }
            id_itinerario += 1

        except json.JSONDecodeError:
            continue

    return itinerarios
