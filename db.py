
import sqlite3

def guardar_en_sqlite(fecha, itinerario_codigo, itinerarios):
    conn = sqlite3.connect('itinerarios.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS itinerarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            itinerario_codigo TEXT,
            recorrido TEXT,
            hora_despacho TEXT,
            hora_fin TEXT
        )
    ''')


    cursor.execute("DELETE FROM itinerarios WHERE fecha = ?", (fecha,))

    for item in itinerarios:
        cursor.execute('''
            INSERT INTO itinerarios (fecha, itinerario_codigo, recorrido, hora_despacho, hora_fin)
            VALUES (?, ?, ?, ?, ?)
        ''', (fecha, itinerario_codigo, item.get("recorrido", ""), item.get("hora_despacho", ""), item.get("hora_fin", "")))

    conn.commit()
    conn.close()



def cargar_desde_sqlite(fecha):
    conn = sqlite3.connect('itinerarios.db')
    cursor = conn.cursor()

    # Crear la tabla si no existe
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS itinerarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            itinerario_codigo TEXT,
            recorrido TEXT,
            hora_despacho TEXT,
            hora_fin TEXT
        )
    ''')

    # Buscar datos con la fecha actual
    cursor.execute('''
        SELECT itinerario_codigo, recorrido, hora_despacho, hora_fin
        FROM itinerarios WHERE fecha = ?
    ''', (fecha,))
    filas = cursor.fetchall()
    conn.close()

    if not filas:
        return None, []

    codigo_itinerario = filas[0][0]
    itinerarios = [{"recorrido": f[1], "hora_despacho": f[2], "hora_fin": f[3]} for f in filas]
    return codigo_itinerario, itinerarios

def itinerarios_diferentes(locales, servidor):
    if len(locales) != len(servidor):
        return True
    for i in range(len(locales)):
        if (
            locales[i].get("recorrido", "") != servidor[i].get("recorrido", "") or
            locales[i].get("hora_despacho", "") != servidor[i].get("hora_despacho", "") or
            locales[i].get("hora_fin", "") != servidor[i].get("hora_fin", "")
        ):
            return True
    return False
