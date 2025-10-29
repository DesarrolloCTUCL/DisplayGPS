import socket
import time
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
import json
from ComandosNextion import send_to_nextion, send_to_nextionPlay, nextion, last_sent_texts
from despachos import obtener_datos_itinerario
from funciones import calcular_distancia, parse_gprmc, verificar_itinerario_actual, obtener_chainpc_por_itinerario
from mqtt_auth import (
    crear_conexion_mqtt,
    guardar_pendiente,
    reenviar_pendientes,
    publicar_mensaje
)

import threading

# Cargar variables de entorno
load_dotenv()

BUS_ID = int(os.getenv("BUS_ID"))
RADIO = int(os.getenv("RADIO"))


# Configuración de servidor de sockets
HOST = '0.0.0.0'
PORT = 8500


mqtt_connection, CLIENT_ID = crear_conexion_mqtt()
TOPIC = f"buses/gps/{BUS_ID}"

# Variables globales
gps_activo = False
gps_lock = threading.Lock()
fecha_ultima_actualizacion = datetime.now().date()  # ← Inicialización


import json
from pathlib import Path



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
    global fecha_ultima_actualizacion
    threading.Thread(target=actualizar_hora_local, daemon=True).start()

    # Conexión a AWS IoT con reintentos
    ruta_iniciada = False
    ruta_anterior = None
    ruta_activa_id = None
    esperando_ruta = False
    ruta_finalizada = False
    ruta_notificada = False 

    while True:
        try:
            print("[Main] Sistema iniciado. Esperando comandos...")
            send_to_nextion("Espere", "g0")
            connect_future = mqtt_connection.connect()
            connect_future.result(timeout=10)
            print("✅ Conectado a AWS IoT Core")
            obtener_datos_itinerario()
            reenviar_pendientes(mqtt_connection, TOPIC)
            last_sent_texts.clear()
            break
        except Exception as e:
            print(f"❌ Error de conexión: {e}")
            send_to_nextion("No señal", "g0")
            print("🔄 Reintentando en 5 segundos...")
            time.sleep(5)

    
    puntos_notificados = set()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind((HOST, PORT))
            server.listen()
            print(f"Esperando señal GPS")

            while True:
                conn, addr = server.accept()
                with conn:
                    while True:
                        data = conn.recv(1024)
                        if not data:
                            break

                        # 🟡 Verificar cambio de día
                        fecha_actual = datetime.now().date()
                        if fecha_actual != fecha_ultima_actualizacion:
                            print(f"📅 Cambio de día detectado ({fecha_ultima_actualizacion} → {fecha_actual}). Refrescando itinerarios...")
                            obtener_datos_itinerario()
                            fecha_ultima_actualizacion = fecha_actual

                            # Reiniciar variables de control de rutas
                            ruta_iniciada = False
                            ruta_anterior = None
                            ruta_activa_id = None
                            esperando_ruta = False
                            ruta_finalizada= False
                            ruta_notificada=False
                            puntos_notificados.clear()

                        trama = data.decode().strip()
                        parsed_data = parse_gprmc(trama)
                        if parsed_data:
                            hora_gps = parsed_data["hora_obj"]
                            hora_local = datetime.now()
                            diferencia = abs((hora_local - hora_gps).total_seconds())
                            if diferencia > 3:
                                continue

                            with gps_lock:
                                gps_activo = True

                            send_to_nextion(parsed_data['fecha'], "t1")
                            send_to_nextion(parsed_data['hora'], "t0")
                            verificar_itinerario_actual(hora_local.strftime("%d/%m/%Y"), hora_local.strftime("%H:%M:%S"))
                            hora_actual_dt = datetime.strptime(parsed_data['hora'], "%H:%M:%S")

                            turnos = obtener_chainpc_por_itinerario()
                            itinerario_activo = None
                            id_itin_activo = None

                            for id_itin, data_itin in sorted(turnos.items(), key=lambda x: datetime.strptime(x[1]['hora_despacho'], "%H:%M:%S"), reverse=True):
                                hora_despacho_dt = datetime.strptime(data_itin["hora_despacho"], "%H:%M:%S")
                                hora_fin_dt = datetime.strptime(data_itin["hora_fin"], "%H:%M:%S")

                                margen_inicio = timedelta(minutes=2)
                                margen_final = timedelta(minutes=8)
                                hora_despacho_margen = hora_despacho_dt - margen_inicio
                                hora_fin_margen = hora_fin_dt + margen_final

                                if hora_despacho_dt <= hora_fin_dt:
                                    activo = hora_despacho_margen <= hora_actual_dt <= hora_fin_margen
                                else:
                                    activo = hora_actual_dt >= hora_despacho_margen or hora_actual_dt <= hora_fin_margen

                                if activo:
                                    itinerario_activo = data_itin
                                    id_itin_activo = id_itin
                                    if ruta_activa_id != id_itin_activo:
                                        ruta_finalizada = False
                                        ruta_notificada = False

                            if itinerario_activo and ruta_finalizada==False:
                                nombre_recorrido = itinerario_activo.get("recorrido", "Recorrido sin nombre")
                                hora_inicio = itinerario_activo.get("hora_despacho", "--:--:--")
                                hora_fin = itinerario_activo.get("hora_fin", "--:--:--")

                                if ruta_activa_id != id_itin_activo and ruta_finalizada==False:
                                    print(f"🟢 Ruta INICIADA: {nombre_recorrido} | Inicio: {hora_inicio} | Fin: {hora_fin} (ID: {id_itin_activo})")
                                    ruta_activa_id = id_itin_activo
                                    esperando_ruta = False

                                shift_id = itinerario_activo.get("shift_id")
                                puntos = itinerario_activo.get("puntos", [])

                                if (not ruta_iniciada or ruta_anterior != id_itin_activo) and not ruta_finalizada:
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

                            elif itinerario_activo and ruta_finalizada==True:
                                if not esperando_ruta:
                                    if not ruta_notificada:
                                        print(f"🔴 Ruta FINALIZADA ultimo punto de control")
                                        ruta_notificada=True
                                    print("⏸ Esperando el inicio de la próxima ruta...")
                                    send_to_nextion("ESPERANDO PRÓXIMA RUTA", "g0")
                                    send_to_nextion("--:--:--", "t5")
                                    esperando_ruta = True
                             
                            elif itinerario_activo is None:

                                if (ruta_activa_id is not None or ruta_finalizada) and not ruta_notificada:
                                    print(f"🔴 Ruta FINALIZADA: {nombre_recorrido} | Inicio: {hora_inicio} | Fin: {hora_fin} (ID: {ruta_activa_id})")
                                    ruta_activa_id = None
                                    ruta_notificada = True
                                    ruta_finalizada = True
                              

                                if not esperando_ruta:
                                    print("⏸ Esperando el inicio de la próxima ruta...")
                                    esperando_ruta = True

                                send_to_nextion("ESPERANDO PRÓXIMA RUTA", "g0")
                                send_to_nextion("--:--:--", "t5")
                                ruta_iniciada = False
                                ruta_anterior = None
                                puntos = []

                            if ruta_finalizada:
                                continue
                            # Verificación de puntos de control
                            for punto in puntos:
                                name = punto.get("name", "Sin nombre")
                                lat = punto.get("lat")
                                lon = punto.get("long")
                                numero = punto.get("numero")
                                radius = punto.get("radius", 60)

                                if numero is None:
                                    continue

                                distancia = calcular_distancia(parsed_data['latitud'], parsed_data['longitud'], lat, lon)
                                if distancia <= radius:
                                    if name not in puntos_notificados:
                                        print(f"Punto de control alcanzado: {name}, Reproduciendo...")
                                        send_to_nextionPlay(0, int(numero) - 1)

                                        index_actual = next((i for i, p in enumerate(puntos) if p.get("numero") == numero), None)
                                        if index_actual is not None:
                                            # Si es el último punto de control
                                            if index_actual + 1 >= len(puntos):
                                                send_to_nextion("FIN", "g0")
                                                send_to_nextion("--:--:--", "t5")
                                                print(f"✅ Último punto de control marcado. Ruta FINALIZADA: {nombre_recorrido} | Inicio: {hora_inicio} | Fin: {hora_fin} (ID: {ruta_activa_id})")
                                                #ruta_activa_id = None
                                                ruta_iniciada = False
                                                esperando_ruta = False
                                                ruta_finalizada=True
                                                ruta_anterior = ruta_activa_id
                                                puntos_notificados.clear()
                                            else:
                                                siguiente_punto = puntos[index_actual + 1]
                                                siguiente_nombre = siguiente_punto.get("name", "Siguiente")
                                                siguiente_hora = siguiente_punto.get("hora", "--:--:--")
                                                send_to_nextion(siguiente_nombre, "g0")
                                                send_to_nextion(siguiente_hora, "t5")

                                        mensaje_mqtt = {
                                            "BusID": CLIENT_ID,
                                            "datetime": f"{parsed_data['fecha']} {parsed_data['hora']}",
                                            "punto_control_id": numero,
                                            "punto_controlname": name,
                                            "shift_id": shift_id,
                                            "latitud": parsed_data["latitud"],
                                            "longitud": parsed_data["longitud"],
                                            "velocidad_kmh": parsed_data["velocidad_kmh"]
                                        }

                                        publicar_mensaje(mqtt_connection, TOPIC, mensaje_mqtt)

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



