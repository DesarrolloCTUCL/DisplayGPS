import time
from datetime import datetime
import threading
from puntoscontrol import obtener_chainpc_por_itinerario
from ComandosNextion import send_to_nextion, send_to_nextionPlay, nextion, last_sent_texts
from despachos import obtener_datos_itinerario
from config import BUS_ID
from funciones import calcular_distancia, verificar_itinerario_actual

gps_activo = False
gps_lock = threading.Lock()
puntos_notificados = set()

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
    # Coordenadas simuladas cerca del punto de control
    coordenadas_simuladas = [
        {"latitud": -3.94620515, "longitud": -79.233946, "velocidad_kmh": 10.0},
        {"latitud": -3.941728, "longitud": -79.227538, "velocidad_kmh": 20.0},
        {"latitud": -3.9578, "longitud": -79.2204, "velocidad_kmh": 30.0},
        {"latitud": -4.01303197, "longitud": -79.2058273, "velocidad_kmh": 25.0},
        {"latitud": -4.0266216, "longitud": -79.207551, "velocidad_kmh": 15.0},
        {"latitud": -4.03082217, "longitud": -79.2068375, "velocidad_kmh": 10.0},
        {"latitud": -4.04817194, "longitud": -79.21165408, "velocidad_kmh": 20.0},
        {"latitud": -3.95929, "longitud": -79.23405, "velocidad_kmh": 30.0},
        {"latitud": -3.928058, "longitud": -79.235322, "velocidad_kmh": 15.0},
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
        if hora_despacho_dt <= hora_fin_dt:
            activo = hora_despacho_dt <= hora_actual_dt <= hora_fin_dt
        else:
            activo = hora_actual_dt >= hora_despacho_dt or hora_actual_dt <= hora_fin_dt

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
            if distancia <= 850:
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
        time.sleep(3)

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
