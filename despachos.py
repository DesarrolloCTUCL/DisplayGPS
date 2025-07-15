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
    fecha_raspberry = datetime.now().strftime("%Y-%m-%d")
    url = f"https://www.ctucloja.com/api/despacho_display/bus/{BUS_ID}/itinerarios?date={fecha_raspberry}"
    datos_a_mostrar = (fecha_raspberry, "", [])
    datos_obtenidos = False

    try:
        print(f"Consultando al servidor con fecha: {fecha_raspberry}...")
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            print("Respuesta del servidor recibida correctamente")
            
            # Extraer datos de la nueva estructura
            datos = data.get("data", {})
            codigo_itinerario_servidor = datos.get("itinerary", "")
            itinerarios_servidor = datos.get("itinerarios", [])

            if codigo_itinerario_servidor and itinerarios_servidor:
               # print(f"📋 Itinerario: {codigo_itinerario_servidor}")
                #print(f"📅 Número de recorridos: {len(itinerarios_servidor)}")
                
                # Guardar en SQLite si es diferente
                codigo_itinerario_local, itinerarios_locales = cargar_desde_sqlite(fecha_raspberry)
                
                if (codigo_itinerario_servidor != codigo_itinerario_local or
                    itinerarios_diferentes(itinerarios_locales, itinerarios_servidor)):
                    print("🆕 Datos nuevos detectados. Guardando en SQLite...")
                    guardar_en_sqlite(fecha_raspberry, codigo_itinerario_servidor, itinerarios_servidor)
                
                datos_a_mostrar = (fecha_raspberry, codigo_itinerario_servidor, itinerarios_servidor)
                datos_obtenidos = True
            else:
                print("⚠️ El servidor no devolvió datos válidos (itinerary o itinerarios vacíos)")
        else:
            print(f"❌ Error HTTP: {response.status_code}")
    except Exception as e:
        print(f"❌ Error de conexión: {str(e)}")

    if not datos_obtenidos:
        print("Intentando cargar datos desde SQLite...")
        codigo_itinerario, itinerarios = cargar_desde_sqlite(fecha_raspberry)
        if codigo_itinerario and itinerarios:
            print("✅ Datos cargados desde SQLite")
            datos_a_mostrar = (fecha_raspberry, codigo_itinerario, itinerarios)
        else:
            print("⚠️ No hay datos válidos en SQLite.")
            datos_a_mostrar = (fecha_raspberry, "", [])

    # Envío a Nextion con verificación
    fecha_mostrar, codigo_mostrar, itinerarios_mostrar = datos_a_mostrar
    
    # Enviar fecha y código
    send_to_nextion(fecha_mostrar, "t7")
    send_to_nextion(codigo_mostrar, "t8")
    
    # Enviar itinerarios
    for i in range(15):  # Ajusta según tu pantalla Nextion
        if i < len(itinerarios_mostrar):
            recorrido = itinerarios_mostrar[i].get("recorrido", "").strip()
            hora_despacho = itinerarios_mostrar[i].get("hora_despacho", "").split(':')[0:2]  # Formato HH:MM
            hora_despacho = ':'.join(hora_despacho) if hora_despacho else ""
            hora_fin = itinerarios_mostrar[i].get("hora_fin", "").split(':')[0:2]
            hora_fin = ':'.join(hora_fin) if hora_fin else ""
        else:
            recorrido = hora_despacho = hora_fin = ""
        
        if recorrido:
            send_to_nextion(recorrido, f"t{9 + i}")
            time.sleep(0.1)
        if hora_despacho:
            send_to_nextion(hora_despacho, f"t{24 + i}")
            time.sleep(0.1)
        if hora_fin:
            send_to_nextion(hora_fin, f"t{39 + i}")
            time.sleep(0.1)

def escuchar_itinerario(evento_itinerario):
    while True:
        if evento_itinerario.is_set():
            print("Evento activado, ejecutando obtener_datos_itinerario()")
            obtener_datos_itinerario()
            evento_itinerario.clear()
        time.sleep(0.05)
