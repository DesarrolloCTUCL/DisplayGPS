import sqlite3
import json
from datetime import datetime

def obtener_chainpc_por_itinerario():
    """
    Extrae cada itinerario individual con su recorrido, hora_despacho, hora_fin y sus puntos chainpc,
    filtrando los puntos que estén entre hora_despacho y hora_fin (considerando cruces de medianoche).
    Retorna un diccionario:
    {
        1: {
            "recorrido": "...",
            "hora_despacho": "...",
            "hora_fin": "...",
            "puntos": [ {numero, name, lat, long, hora}, ... ]
        },
        ...
    }
    """
    conn = sqlite3.connect('itinerarios.db')
    cursor = conn.cursor()
    cursor.execute('SELECT recorrido, hora_despacho, hora_fin, chainpc FROM itinerarios')
    filas = cursor.fetchall()
    conn.close()

    itinerarios = {}
    id_itinerario = 1

    for recorrido, hora_despacho, hora_fin, chainpc_json in filas:
        if not chainpc_json:
            continue
        try:
            puntos = json.loads(chainpc_json)
            fmt = "%H:%M:%S"  # Ajusta según tu formato de hora
            try:
                hora_despacho_dt = datetime.strptime(hora_despacho, fmt)
                hora_fin_dt = datetime.strptime(hora_fin, fmt)
            except Exception as e:
                print(f"❌ Error al parsear hora_despacho o hora_fin del itinerario {id_itinerario}: {e}")
                continue

            puntos_filtrados = []
            print(f"🧭 Itinerario {id_itinerario} con rango horario {hora_despacho} - {hora_fin}")

            for punto in puntos:
                if "hora" not in punto:
                    print(f"⚠️ Punto sin 'hora': {punto}")
                    continue

                print(f"DEBUG - Punto {punto.get('numero')} tiene hora raw: '{punto['hora']}'")
                try:
                    hora_punto_dt = datetime.strptime(punto['hora'], fmt)
                except Exception as e:
                    print(f"⚠️ Error al parsear hora del punto {punto.get('numero')}: {e}")
                    continue

                print(f"DEBUG - Punto {punto.get('numero')} hora parseada: {hora_punto_dt.time()}")

                # Lógica para manejar cruce de medianoche
                if hora_despacho_dt <= hora_fin_dt:
                    dentro = hora_despacho_dt <= hora_punto_dt <= hora_fin_dt
                else:
                    # Cruce medianoche
                    dentro = hora_punto_dt >= hora_despacho_dt or hora_punto_dt <= hora_fin_dt

                print(f"Comparando punto {punto.get('numero')} hora {hora_punto_dt.time()} con rango {hora_despacho_dt.time()} - {hora_fin_dt.time()} -> {'Dentro' if dentro else 'Fuera'}")

                if dentro:
                    puntos_filtrados.append(punto)

            print(f"🧭 Itinerario {id_itinerario} tiene {len(puntos_filtrados)} puntos dentro del rango horario")

            for punto in puntos_filtrados:
                if "numero" not in punto:
                    print(f"⚠️ Punto sin 'numero': {punto}")
                else:
                    print(f"✅ Punto con 'numero': {punto['numero']} - {punto['name']}")

            itinerarios[id_itinerario] = {
                "recorrido": recorrido,
                "hora_despacho": hora_despacho,
                "hora_fin": hora_fin,
                "puntos": puntos_filtrados
            }
            id_itinerario += 1

        except json.JSONDecodeError as e:
            print(f"❌ Error al decodificar JSON: {e}")
            continue

    return itinerarios
