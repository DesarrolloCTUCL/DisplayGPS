import sqlite3
import json
from datetime import datetime

def obtener_chainpc_por_itinerario():
    """
    Extrae cada itinerario individual con su recorrido, hora_despacho, hora_fin y sus puntos chainpc,
    filtrando los puntos que estén entre hora_despacho y hora_fin.
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

            # Convertir horas a datetime para comparación
            fmt = "%H:%M:%S"  # o el formato que corresponda, ajustar según tu dato
            hora_despacho_dt = datetime.strptime(hora_despacho, fmt)
            hora_fin_dt = datetime.strptime(hora_fin, fmt)

            # Filtrar puntos con campo 'hora' entre hora_despacho y hora_fin
            puntos_filtrados = []
            for punto in puntos:
                if "hora" not in punto:
                    print(f"⚠️ Punto sin 'hora': {punto}, se omite")
                    continue

                try:
                    hora_punto_dt = datetime.strptime(punto['hora'], fmt)
                except Exception as e:
                    print(f"⚠️ Error al parsear hora del punto {punto['numero']}: {e}")
                    continue

                if hora_despacho_dt <= hora_punto_dt <= hora_fin_dt:
                    puntos_filtrados.append(punto)

            print(f"🧭 Itinerario {id_itinerario} con {len(puntos_filtrados)} puntos filtrados entre {hora_despacho} y {hora_fin}")

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
