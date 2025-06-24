import sqlite3
import json
from datetime import datetime

def obtener_chainpc_por_itinerario():
    """
    Extrae cada itinerario con su recorrido, hora_despacho, hora_fin y los puntos chainpc filtrados
    por su horario. Retorna un diccionario estructurado por id_itinerario.
    """
    conn = sqlite3.connect('itinerarios.db')
    cursor = conn.cursor()
    cursor.execute('SELECT recorrido, hora_despacho, hora_fin, chainpc FROM itinerarios')
    filas = cursor.fetchall()
    conn.close()

    itinerarios = {}
    id_itinerario = 1
    fmt = "%H:%M:%S"

    for recorrido, hora_despacho, hora_fin, chainpc_json in filas:
        if not chainpc_json:
            continue
        try:
            puntos = json.loads(chainpc_json)
            try:
                hora_despacho_dt = datetime.strptime(hora_despacho, fmt)
                hora_fin_dt = datetime.strptime(hora_fin, fmt)
            except:
                continue

            puntos_filtrados = []

            for punto in puntos:
                if "hora" not in punto:
                    continue
                try:
                    hora_punto_dt = datetime.strptime(punto['hora'], fmt)
                except:
                    continue

                if hora_despacho_dt <= hora_fin_dt:
                    dentro = hora_despacho_dt <= hora_punto_dt <= hora_fin_dt
                else:
                    dentro = hora_punto_dt >= hora_despacho_dt or hora_punto_dt <= hora_fin_dt

                if dentro:
                    puntos_filtrados.append(punto)

            itinerarios[id_itinerario] = {
                "recorrido": recorrido,
                "hora_despacho": hora_despacho,
                "hora_fin": hora_fin,
                "puntos": puntos_filtrados
            }
            id_itinerario += 1

        except json.JSONDecodeError:
            continue

    return itinerarios
