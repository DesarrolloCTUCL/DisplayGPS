import requests
import os
from dotenv import load_dotenv
from datetime import datetime
from ComandosNextion import send_to_nextion
from db import guardar_en_sqlite, cargar_desde_sqlite, itinerarios_diferentes
import time

# Cargar las variables desde el archivo .env
load_dotenv()

BUS_ID = int(os.getenv("BUS_ID"))

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
    fecha_raspberry = datetime.now().strftime("%Y-%m-%d")

    # Primero intentar cargar desde SQLite
    codigo_itinerario_local, itinerarios_locales = cargar_desde_sqlite(fecha_raspberry)

    if codigo_itinerario_local and itinerarios_locales:
        # Ya tenemos datos del día en SQLite → usar directamente
        print("✅ Usando datos locales desde SQLite")
        datos_a_mostrar = (fecha_raspberry, codigo_itinerario_local, itinerarios_locales)
    else:
        # No hay datos del día → consultar al servidor
        url = f"https://www.ctucloja.com/api/despacho_display/bus/{BUS_ID}/itinerarios?date={fecha_raspberry}"
        try:
            print(f"Consultando al servidor con fecha: {fecha_raspberry}...")
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                datos = data.get("data", {})
                codigo_itinerario_servidor = datos.get("itinerary", "")
                itinerarios_servidor = datos.get("itinerarios", [])

                if codigo_itinerario_servidor and itinerarios_servidor:
                    print("🆕 Datos obtenidos del servidor. Guardando en SQLite...")
                    guardar_en_sqlite(fecha_raspberry, codigo_itinerario_servidor, itinerarios_servidor)
                    datos_a_mostrar = (fecha_raspberry, codigo_itinerario_servidor, itinerarios_servidor)
                else:
                    print("⚠️ El servidor no devolvió datos válidos, intentando cargar SQLite...")
                    datos_a_mostrar = (fecha_raspberry, codigo_itinerario_local or "", itinerarios_locales or [])
            else:
                print(f"❌ Error HTTP: {response.status_code}. Usando SQLite si hay datos")
                datos_a_mostrar = (fecha_raspberry, codigo_itinerario_local or "", itinerarios_locales or [])

        except Exception as e:
            print(f"❌ Error de conexión: {str(e)}. Usando SQLite si hay datos")
            datos_a_mostrar = (fecha_raspberry, codigo_itinerario_local or "", itinerarios_locales or [])

    # Envío a Nextion
    fecha_mostrar, codigo_mostrar, itinerarios_mostrar = datos_a_mostrar
    limpiar_pantalla()
    send_to_nextion(fecha_mostrar, "t7")
    send_to_nextion(codigo_mostrar, "t8")

    por_pagina = 15
    for i, itinerario in enumerate(itinerarios_mostrar):
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
            print("Evento activado, ejecutando obtener_datos_itinerario()")
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
    # Si en el futuro hay más páginas, aquí agregas más rangos
        # Limpiar cabecera (fecha y código)
    send_to_nextion("", "t7")
    time.sleep(0.02)
    send_to_nextion("", "t8")
    time.sleep(0.02)