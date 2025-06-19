import requests
from datetime import datetime
from config import BUS_ID
from ComandosNextion import send_to_nextion
from db import guardar_en_sqlite, cargar_desde_sqlite, itinerarios_diferentes
import time

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
    url = f"https://www.ctucloja.com/despacho_display/bus/{BUS_ID}/itinerarios"
    fecha_raspberry = datetime.now().strftime("%d/%m/%Y")
    datos_obtenidos = False

    try:
        print("Consultando al servidor...")
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            fecha_servidor = data.get("fecha", "")
            codigo_itinerario_servidor = data.get("itinerario", "")
            itinerarios_servidor = data.get("itinerarios", [])

            print(f"Fecha Raspberry Pi: {fecha_raspberry}")
            print(f"Fecha del Servidor: {fecha_servidor}")

            if fecha_raspberry == fecha_servidor and codigo_itinerario_servidor and itinerarios_servidor:
                codigo_itinerario_local, itinerarios_locales = cargar_desde_sqlite(fecha_raspberry)

                if (
                    codigo_itinerario_servidor != codigo_itinerario_local or
                    itinerarios_diferentes(itinerarios_locales, itinerarios_servidor)
                ):
                    print("🆕 Datos nuevos o diferentes detectados. Guardando en SQLite...")
                    guardar_en_sqlite(fecha_servidor, codigo_itinerario_servidor, itinerarios_servidor)
                else:
                    print("📦 Datos del servidor ya están guardados localmente.")

                datos_a_mostrar = (fecha_servidor, codigo_itinerario_servidor, itinerarios_servidor)
                datos_obtenidos = True
            else:
                print("⚠️ Datos del servidor incompletos o con fecha inválida.")
        else:
            print(f"❌ Error al obtener datos del servidor: {response.status_code}")
    except Exception as e:
        print(f"❌ Error al conectarse al servidor: {e}")

    if not datos_obtenidos:
        print("Intentando cargar datos desde SQLite...")
        codigo_itinerario, itinerarios = cargar_desde_sqlite(fecha_raspberry)
        if codigo_itinerario and itinerarios:
            print("✅ Datos cargados desde SQLite")
            datos_a_mostrar = (fecha_raspberry, codigo_itinerario, itinerarios)
        else:
            print("⚠️ No hay datos válidos en SQLite.")
            datos_a_mostrar = (fecha_raspberry, "", [])

    # Mostrar datos en Nextion sin sobrescribir con campos vacíos
    fecha_mostrar, codigo_mostrar, itinerarios_mostrar = datos_a_mostrar

    send_to_nextion(fecha_mostrar, "t7")
    send_to_nextion(codigo_mostrar, "t8")

    for i in range(15):
        if i < len(itinerarios_mostrar):
            recorrido = itinerarios_mostrar[i].get("recorrido", "").strip()
            hora_despacho = itinerarios_mostrar[i].get("hora_despacho", "").strip()
            hora_fin = itinerarios_mostrar[i].get("hora_fin", "").strip()
        else:
            recorrido = hora_despacho = hora_fin = ""

        if recorrido:
            send_to_nextion(recorrido, f"t{9 + i}")
            time.sleep(0.02)
        if hora_despacho:
            send_to_nextion(hora_despacho, f"t{24 + i}")
            time.sleep(0.02)
        if hora_fin:
            send_to_nextion(hora_fin, f"t{39 + i}")
            time.sleep(0.02)

def escuchar_itinerario(evento_itinerario):
    while True:
        if evento_itinerario.is_set():
            print("Evento activado, ejecutando obtener_datos_itinerario()")
            obtener_datos_itinerario()
            evento_itinerario.clear()
        time.sleep(0.05)
