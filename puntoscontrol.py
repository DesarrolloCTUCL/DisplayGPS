import sqlite3
import json


def obtener_chainpc_por_itinerario():
    """
    Extrae cada itinerario individual con su recorrido, hora_despacho, hora_fin y sus puntos chainpc.
    Retorna un diccionario:
    {
        1: {
            "recorrido": "...",
            "hora_despacho": "...",
            "hora_fin": "...",
            "puntos": [ {name, lat, long, hora}, ... ]
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
            itinerarios[id_itinerario] = {
                "recorrido": recorrido,
                "hora_despacho": hora_despacho,
                "hora_fin": hora_fin,
                "puntos": puntos
            }
            id_itinerario += 1
        except json.JSONDecodeError:
            continue

    return itinerarios