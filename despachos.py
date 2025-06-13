import requests
from datetime import datetime
from config import BUS_ID
from ComandosNextion import send_to_nextion
from db import guardar_en_sqlite,cargar_desde_sqlite
import serial
import time



def obtener_datos_itinerario():
    url = f"https://www.ctucloja.com/despacho_display/bus/{BUS_ID}/itinerarios"
    fecha_raspberry = datetime.now().strftime("%d/%m/%Y")
    datos_obtenidos = False

    # PRIMERO: intentar consultar al servidor
    try:
        print("Consultando al servidor...")
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            fecha_servidor = data.get("fecha", "")
            codigo_itinerario = data.get("itinerario", "")
            itinerarios = data.get("itinerarios", [])

            print(f"Fecha Raspberry Pi: {fecha_raspberry}")
            print(f"Fecha del Servidor: {fecha_servidor}")

            if fecha_raspberry == fecha_servidor and codigo_itinerario and itinerarios:
                send_to_nextion(fecha_servidor, "t7")
                send_to_nextion(codigo_itinerario, "t8")

                for i in range(15):
                    if i < len(itinerarios):
                        recorrido = itinerarios[i].get("recorrido", "")
                        hora_despacho = itinerarios[i].get("hora_despacho", "")
                        hora_fin = itinerarios[i].get("hora_fin", "")
                    else:
                        recorrido = hora_despacho = hora_fin = ""

                    send_to_nextion(recorrido, f"t{9 + i}")
                    send_to_nextion(hora_despacho, f"t{24 + i}")
                    send_to_nextion(hora_fin, f"t{39 + i}")

                # Guardar en SQLite
                guardar_en_sqlite(fecha_servidor, codigo_itinerario, itinerarios)
                datos_obtenidos = True
            else:
                print("⚠️ Datos del servidor incompletos o con fecha inválida.")
        else:
            print(f"Error al obtener datos del servidor: {response.status_code}")
    except Exception as e:
        print(f"❌ Error al conectarse al servidor: {e}")

    # SI NO HAY DATOS DEL SERVIDOR, CARGAR DESDE SQLITE
    if not datos_obtenidos:
        print("Intentando cargar datos desde SQLite...")
        codigo_itinerario, itinerarios = cargar_desde_sqlite(fecha_raspberry)

        if codigo_itinerario and itinerarios:
            print("✅ Datos cargados desde SQLite")
            send_to_nextion(fecha_raspberry, "t7")
            send_to_nextion(codigo_itinerario, "t8")

            for i in range(15):
                if i < len(itinerarios):
                    recorrido = itinerarios[i].get("recorrido", "")
                    hora_despacho = itinerarios[i].get("hora_despacho", "")
                    hora_fin = itinerarios[i].get("hora_fin", "")
                else:
                    recorrido = hora_despacho = hora_fin = ""

                send_to_nextion(recorrido, f"t{9 + i}")
                send_to_nextion(hora_despacho, f"t{24 + i}")
                send_to_nextion(hora_fin, f"t{39 + i}")
        else:
            print("⚠️ No hay datos válidos en SQLite.")

def escuchar_itinerario(evento_itinerario):

    while True:
        # Solo si el evento está activo, ejecuta la función
        if evento_itinerario.is_set():
            print("Evento activado, ejecutando obtener_datos_itinerario()")
            obtener_datos_itinerario()
            evento_itinerario.clear()  # Limpiar el evento para esperar nuevo "7"
        time.sleep(0.05)