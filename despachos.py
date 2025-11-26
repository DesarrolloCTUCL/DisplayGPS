import requests
import os
from dotenv import load_dotenv
from datetime import datetime
from ComandosNextion import send_to_nextion
from db import guardar_en_sqlite, cargar_desde_sqlite
import time

# Cargar las variables desde el archivo .env
load_dotenv()
BUS_ID = int(os.getenv("BUS_ID"))
BUS_BD = int(os.getenv("BUS_DB"))

def itinerarios_diferentes(locales, servidor):
    if len(locales) != len(servidor):
        return True
    for i in range(len(servidor)):
        loc = locales[i] if i < len(locales) else {}
        serv = servidor[i]
        if (
            loc.get("recorrido", "").strip() != serv.get("recorrido", "").strip() or
            loc.get("hora_despacho", "").strip() != serv.get("hora_despacho", "").strip() or
            loc.get("hora_fin", "").strip() != serv.get("hora_fin", "").strip()
        ):
            return True
    return False
def obtener_datos_itinerario():
    fecha_actual = datetime.now().strftime("%Y-%m-%d")

    # 🔹 Intentamos cargar datos locales primero
    codigo_local, itinerarios_locales = cargar_desde_sqlite(fecha_actual)

    if codigo_local and itinerarios_locales:
        print(f"✅ Usando datos locales desde SQLite (fecha {fecha_actual})")
        limpiar_pantalla()
        send_to_nextion(fecha_actual, "t7")
        send_to_nextion(codigo_local, "t8")

        por_pagina = 15
        for i, itinerario in enumerate(itinerarios_locales):
            pagina = i // por_pagina
            fila = i % por_pagina
            offset = pagina * 45

            idx_recorrido = 9 + offset + fila
            idx_despacho  = 24 + offset + fila
            idx_fin       = 39 + offset + fila

            recorrido = itinerario.get("recorrido", "").strip()
            hora_despacho = itinerario.get("hora_despacho", "")
            hora_despacho = ':'.join(hora_despacho.split(':')[0:2]) if hora_despacho else ""
            hora_fin = itinerario.get("hora_fin", "")
            hora_fin = ':'.join(hora_fin.split(':')[0:2]) if hora_fin else ""

            if recorrido:
                send_to_nextion(recorrido, f"t{idx_recorrido}")
                time.sleep(0.1)
            if hora_despacho:
                send_to_nextion(hora_despacho, f"t{idx_despacho}")
                time.sleep(0.1)
            if hora_fin:
                send_to_nextion(hora_fin, f"t{idx_fin}")
                time.sleep(0.1)
        return  # ✅ Salimos porque ya usamos datos locales válidos

    # 🌐 Si no hay datos locales para hoy, intentamos descargarlos del servidor
    url = f"https://www.ctucloja.com/api/despacho_display/bus/{BUS_BD}/itinerarios?date={fecha_actual}"
    codigo_servidor = None
    itinerarios_servidor = None

    tiempo_inicio = time.time()
    tiempo_limite = 60 * 60  # 1 hora

    while True:
        try:
            print(f"🌐 Consultando al servidor con fecha: {fecha_actual}...")
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                datos = data.get("data", {})
                codigo_servidor = datos.get("itinerary", "")
                itinerarios_servidor = datos.get("itinerarios", [])

                if codigo_servidor and itinerarios_servidor:
                    print("🆕 Datos obtenidos del servidor. Guardando en SQLite...")
                    guardar_en_sqlite(fecha_actual, codigo_servidor, itinerarios_servidor)
                    break
                else:
                    print("⚠️ El servidor respondió sin datos válidos. Reintentando en 5 s...")
            else:
                print(f"❌ Error HTTP {response.status_code}. Reintentando en 5 s...")

        except Exception as e:
            print(f"❌ Error de conexión: {e}. Reintentando en 5 s...")

        if time.time() - tiempo_inicio >= tiempo_limite:
            print("⏰ Se alcanzó el tiempo máximo de 1 hora sin obtener datos. Abortando reintentos.")
            return

        time.sleep(5)

    # 🧭 Enviar los datos obtenidos del servidor
    limpiar_pantalla()
    send_to_nextion(fecha_actual, "t7")
    send_to_nextion(codigo_servidor, "t8")

    por_pagina = 15
    for i, itinerario in enumerate(itinerarios_servidor):
        pagina = i // por_pagina
        fila = i % por_pagina
        offset = pagina * 45

        idx_recorrido = 9 + offset + fila
        idx_despacho  = 24 + offset + fila
        idx_fin       = 39 + offset + fila

        recorrido = itinerario.get("recorrido", "").strip()
        hora_despacho = itinerario.get("hora_despacho", "")
        hora_despacho = ':'.join(hora_despacho.split(':')[0:2]) if hora_despacho else ""
        hora_fin = itinerario.get("hora_fin", "")
        hora_fin = ':'.join(hora_fin.split(':')[0:2]) if hora_fin else ""

        if recorrido:
            send_to_nextion(recorrido, f"t{idx_recorrido}")
            time.sleep(0.1)
        if hora_despacho:
            send_to_nextion(hora_despacho, f"t{idx_despacho}")
            time.sleep(0.1)
        if hora_fin:
            send_to_nextion(hora_fin, f"t{idx_fin}")
            time.sleep(0.1)

def escuchar_itinerario(evento_itinerario):
    while True:
        if evento_itinerario.is_set():
            print("📡 Evento activado, ejecutando obtener_datos_itinerario()")
            obtener_datos_itinerario()
            evento_itinerario.clear()
        time.sleep(0.05)

def limpiar_pantalla():
    # Primera página t9..t53
    for i in range(9, 54):
        send_to_nextion("", f"t{i}")
        time.sleep(0.02)
    # Segunda página t54..t98
    for i in range(54, 99):
        send_to_nextion("", f"t{i}")
        time.sleep(0.02)
    # Limpiar cabecera (fecha y código)
    send_to_nextion("", "t7")
    time.sleep(0.02)
    send_to_nextion("", "t8")
    time.sleep(0.02)
