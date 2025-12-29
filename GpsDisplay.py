import socket
import time
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
from ui_bus import ui_queue

import json
from ComandosNextion import  send_to_nextionPlay, nextion, last_sent_texts
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
        hora_local = datetime.now()

        ui_queue.put({
        "type": "hora",
        "hora": f"🕒 {hora_local.strftime('%H:%M:%S')}🟡"
        })

        ui_queue.put({
            "type": "fecha",
            "fecha": f"📅 {hora_local.strftime('%d/%m/%Y')}"
        })

        ui_queue.put({
            "type": "bus",
            "bus": f"🚌 BUS: RT{CLIENT_ID}"
        })


        verificar_itinerario_actual(
            hora_local.strftime("%d/%m/%Y"),
            hora_local.strftime("%H:%M:%S")
        )

        time.sleep(1)


def manejar_espera_proxima_ruta(ruta_anterior):
    print("⏸ Esperando el inicio de la próxima ruta")

    # Obtener turnos disponibles
    turnos = obtener_chainpc_por_itinerario()
    ids_ordenados = sorted(turnos.keys(), key=lambda x: int(x))
    print(f"🧩 Turnos disponibles: {ids_ordenados}")
    print(f"🧠 Ruta anterior: {ruta_anterior}")

    # Determinar la siguiente ruta
    if ruta_anterior is None:
        # Si no hay ruta anterior, tomar la primera del día
        siguiente_id = ids_ordenados[0] if ids_ordenados else None
    else:
        try:
            indice_actual = ids_ordenados.index(ruta_anterior)
            if indice_actual + 1 < len(ids_ordenados):
                siguiente_id = ids_ordenados[indice_actual + 1]
            else:
                siguiente_id = None
        except ValueError:
            siguiente_id = ids_ordenados[0] if ids_ordenados else None

    # Preparar mensaje para Nextion
    if siguiente_id:
        siguiente_ruta = turnos[siguiente_id]
        prox_nombre = siguiente_ruta.get("recorrido", "Ruta siguiente")
        prox_inicio = siguiente_ruta.get("hora_despacho", "--:--:--")
        prox_fin = siguiente_ruta.get("hora_fin", "--:--:--")

        print(f"Proxima ruta: {prox_inicio}")   
        ui_queue.put({
            "type": "hora_inicio",
            "hora_inicio": prox_inicio
        }) 
        
        ui_queue.put({
            "type": "hora_fin",
            "hora_fin": prox_fin
        }) 
    
        ui_queue.put({
            "type": "ruta",
            "ruta": f"Próxima ruta: {prox_inicio}"
        })

        
        ui_queue.put({
            "type": "punto",
            "punto": prox_nombre
        }) 
        
    else:
        print("✅ No hay más rutas programadas para hoy.")
        ui_queue.put({
            "type": "punto",
            "punto": "FIN DE ITINERARIOS"
        }) 


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
            ui_queue.put({
            "type": "ruta",
            "ruta": "Bienvenido, Espere"
        })  
            connect_future = mqtt_connection.connect()
            connect_future.result(timeout=10)
            print("✅ Conectado a AWS IoT Core")
            obtener_datos_itinerario()
            reenviar_pendientes(mqtt_connection, TOPIC)
            last_sent_texts.clear()
            break
        except Exception as e:
            print(f"❌ Error de conexión: {e}")
            ui_queue.put({
                "type": "punto",
                "punto": "NO SEÑAL"
        }) 
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
                        
                 
                            verificar_itinerario_actual(hora_local.strftime("%d/%m/%Y"), hora_local.strftime("%H:%M:%S"))
                            hora_actual_dt = datetime.strptime(parsed_data['hora'], "%H:%M:%S")

                            turnos = obtener_chainpc_por_itinerario()
                            itinerario_activo = None
                            id_itin_activo = None

                            for id_itin, data_itin in sorted(turnos.items(), key=lambda x: datetime.strptime(x[1]['hora_despacho'], "%H:%M:%S"), reverse=True):
                                hora_despacho_dt = datetime.strptime(data_itin["hora_despacho"], "%H:%M:%S")
                                hora_fin_dt = datetime.strptime(data_itin["hora_fin"], "%H:%M:%S")

                                margen_inicio = timedelta(minutes=2)  #Parametro de configuracion
                                margen_final = timedelta(minutes=8)  #Parametro de configuracion
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
                                        # ================= TKINTER =================
                                        ui_queue.put({
                                            "type": "punto",
                                            "punto": nombre
                                        })

                                        ui_queue.put({
                                            "type": "hora_pc",
                                            "hora_pc": hora_prog
                                        })

                                        ui_queue.put({
                                            "type": "hora_inicio",
                                            "hora_inicio": hora_inicio
                                        })

                                        ui_queue.put({
                                            "type": "hora_fin",
                                            "hora_fin": hora_fin
                                        })

                                        ui_queue.put({
                                            "type": "ruta",
                                            "ruta": nombre_recorrido
                                        })

                                        print(f"🟢 Mostrando primer punto de control al iniciar ruta: {nombre}")

                                    ruta_iniciada = True
                                    ruta_anterior = id_itin_activo


                            elif itinerario_activo and ruta_finalizada==True:
                                if not esperando_ruta:
                                    if not ruta_notificada:
                                        print(f"🔴 Ruta FINALIZADA ultimo punto de control")
                                        ruta_notificada=True
                                    manejar_espera_proxima_ruta(ruta_anterior)
                                    ui_queue.put({
                                            "type": "hora_pc",
                                            "hora_pc": "--:--:--"
                                        })

                                    esperando_ruta = True
                             
                            elif itinerario_activo is None:

                                if (ruta_activa_id is not None or ruta_finalizada) and not ruta_notificada:
                                    print(f"🔴 Ruta FINALIZADA: {nombre_recorrido} | Inicio: {hora_inicio} | Fin: {hora_fin} (ID: {ruta_activa_id})")
                                    ruta_activa_id = None
                                    ruta_notificada = True
                                    ruta_finalizada = True
                              
                                if not esperando_ruta:
                                    manejar_espera_proxima_ruta(ruta_anterior)
                                    esperando_ruta = True
                               
                               
                                ui_queue.put({
                                            "type": "hora_pc",
                                            "hora_pc": "--:--:--"
                                        })
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
                                             
                                                ui_queue.put({
                                                    "type": "punto",
                                                    "punto": "FIN"
                                                })
                                              
                                                ui_queue.put({
                                                    "type": "hora_pc",
                                                    "hora_pc": "--:--:--"
                                                })
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
                                                
                                                ui_queue.put({
                                                    "type": "punto",
                                                    "punto": siguiente_nombre
                                                })

                                                ui_queue.put({
                                                    "type": "hora_pc",
                                                    "hora_pc": siguiente_hora
                                                })
                                               

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
                            with gps_lock:
                                gps_activo = False

    except KeyboardInterrupt:
        print("\nCerrando servidor y conexión con Nextion")
        nextion.close()



