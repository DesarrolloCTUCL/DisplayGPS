import time
import threading
import os
from datetime import datetime, timedelta
from ComandosNextion import send_to_nextion, send_to_nextionPlay, nextion, last_sent_texts
from despachos import obtener_datos_itinerario
from funciones import calcular_distancia, verificar_itinerario_actual,obtener_chainpc_por_itinerario
from dotenv import load_dotenv
gps_activo = False
gps_lock = threading.Lock()
puntos_notificados = set()

# Cargar las variables desde el archivo .env
load_dotenv()

BUS_ID = int(os.getenv("BUS_ID"))

def actualizar_hora_local():
    while True:
        with gps_lock:
            activo = gps_activo
        hora_local = datetime.now()
        send_to_nextion(hora_local.strftime("%H:%M:%S"), "t0")
        send_to_nextion(hora_local.strftime("%Y-%m-%d"), "t1")
        verificar_itinerario_actual(hora_local.strftime("%d/%m/%Y"), hora_local.strftime("%H:%M:%S"))
        time.sleep(1)

def simular_tramas_gps():
    coordenadas_simuladas = [
        {"latitud": -3.96279, "longitud": -79.196586, "velocidad_kmh": 10.0},
        {"latitud": -3.967597, "longitud": -79.196016, "velocidad_kmh": 15.0},
        {"latitud": -3.974626, "longitud": -79.202735, "velocidad_kmh": 20.0},
        {"latitud": -3.978437, "longitud": -79.204387, "velocidad_kmh": 25.0},
        {"latitud": -3.9810868, "longitud": -79.20387622, "velocidad_kmh": 30.0},
        {"latitud": -3.98810447, "longitud": -79.2031431, "velocidad_kmh": 28.0},
        {"latitud": -3.99664296, "longitud": -79.20673718, "velocidad_kmh": 18.0},
        {"latitud": -4.00381712, "longitud": -79.20607171, "velocidad_kmh": 22.0},
        {"latitud": -4.01238453, "longitud": -79.20446589, "velocidad_kmh": 24.0},
        {"latitud": -4.01674366, "longitud": -79.20908483, "velocidad_kmh": 26.0},
        {"latitud": -4.019588, "longitud": -79.224715, "velocidad_kmh": 20.0},
    ]



    itinerarios = obtener_chainpc_por_itinerario()
    if not itinerarios:
        print("⚠️ No hay itinerarios cargados.")
        return

    id_itin_activo = None
    itinerario_activo = None
    hora_actual = datetime.now().strftime("%H:%M:%S")
    hora_actual_dt = datetime.strptime(hora_actual, "%H:%M:%S")

    # Detectar itinerario activo por horario
    for id_itin, data in itinerarios.items():
        hora_despacho_dt = datetime.strptime(data["hora_despacho"], "%H:%M:%S")
        hora_fin_dt = datetime.strptime(data["hora_fin"], "%H:%M:%S")
        # APLICAR MARGEN DE 10 MINUTOS
        margen = timedelta(minutes=10)
        hora_despacho_margen = hora_despacho_dt - margen
        hora_fin_margen = hora_fin_dt + margen

        # Lógica para rangos horarios normales y cruzados de día
        if hora_despacho_dt <= hora_fin_dt:
            activo = hora_despacho_margen <= hora_actual_dt <= hora_fin_margen
        else:
            activo = hora_actual_dt >= hora_despacho_margen or hora_actual_dt <= hora_fin_margen
        if activo:
            itinerario_activo = data
            id_itin_activo = id_itin
            break

    if not itinerario_activo:
        print("⏳ No hay un itinerario activo en este momento.")
        send_to_nextion("ESPERANDO PRÓXIMA RUTA", "g0")
        send_to_nextion("--:--:--", "t5")
        return

    puntos = itinerario_activo.get("puntos", [])
    print(f"🧭 Itinerario {id_itin_activo} activo de {itinerario_activo['hora_despacho']} a {itinerario_activo['hora_fin']}")

    for coords in coordenadas_simuladas:
        parsed_data = {
            "hora": datetime.now().strftime("%H:%M:%S"),
            "fecha": datetime.now().strftime("%d/%m/%Y"),
            "hora_obj": datetime.now(),
            "latitud": coords["latitud"],
            "longitud": coords["longitud"],
            "velocidad_kmh": coords["velocidad_kmh"]
        }

        with gps_lock:
            global gps_activo
            gps_activo = True

        send_to_nextion(parsed_data['fecha'], "t1")
        send_to_nextion(parsed_data['hora'], "t0")
        verificar_itinerario_actual(parsed_data['fecha'], parsed_data['hora'])

        for punto in puntos:
            name = punto.get("name", "Sin nombre")
            lat = punto.get("lat")
            lon = punto.get("long")
            numero = punto.get("numero")

            if numero is None:
                continue

            distancia = calcular_distancia(parsed_data['latitud'], parsed_data['longitud'], lat, lon)
            if distancia <= 60:
                if name not in puntos_notificados:
                    print(f"✅ Punto alcanzado: {name} (Distancia: {round(distancia, 2)} m)")
                    send_to_nextionPlay(0, int(numero) - 1)

                    # Enviar nombre y hora del siguiente punto
                    index_actual = next((i for i, p in enumerate(puntos) if p.get("numero") == numero), None)
                    if index_actual is not None and index_actual + 1 < len(puntos):
                        siguiente = puntos[index_actual + 1]
                        send_to_nextion(siguiente.get("name", "Siguiente"), "g0")
                        send_to_nextion(siguiente.get("hora", "--:--:--"), "t5")
                    else:
                        send_to_nextion("FIN", "g0")
                        send_to_nextion("--:--:--", "t5")

                    puntos_notificados.add(name)
                break
            else:
                if name in puntos_notificados:
                    puntos_notificados.remove(name)

        print("---- Esperando siguiente posición ----")
        time.sleep(4)

def iniciar_simulacion():
    print("[Main] Iniciando simulación de tramas GPS...")
    obtener_datos_itinerario()
    last_sent_texts.clear()
    send_to_nextion(str(BUS_ID), "t2")

    # Iniciar actualización de hora local
    threading.Thread(target=actualizar_hora_local, daemon=True).start()

    # Ejecutar simulación
    simular_tramas_gps()

if __name__ == "__main__":
    try:
        iniciar_simulacion()
    except KeyboardInterrupt:
        print("🛑 Simulación interrumpida por el usuario.")
        nextion.close()
