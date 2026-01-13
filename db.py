import sqlite3
import json

def guardar_en_sqlite(fecha, itinerario_codigo, itinerarios):
    with sqlite3.connect('itinerarios.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS itinerarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                itinerario_codigo TEXT,
                recorrido TEXT,
                hora_despacho TEXT,
                hora_fin TEXT,
                chainpc TEXT,
                shift_id INTEGER
            )
        ''')
        # Elimina todos los registros con fecha distinta a la actual
        cursor.execute("DELETE FROM itinerarios WHERE fecha != ?", (fecha,))
        
        # También puedes eliminar los de la misma fecha, por si estás actualizando
        cursor.execute("DELETE FROM itinerarios WHERE fecha = ?", (fecha,))
        
        for item in itinerarios:
            chainpc = item.get("turno", {}).get("chainpc", [])
            
            # Asegurar que cada punto tenga 'numero'
            for idx, punto in enumerate(chainpc):
                if "numero" not in punto:
                    punto["numero"] = 100 + idx  # O cualquier valor único o representativo

            chainpc_json = json.dumps(chainpc, ensure_ascii=False)
            shift_id = item.get("turno", {}).get("shift_id")  # Aquí obtienes shift_id

            cursor.execute('''
                INSERT INTO itinerarios (fecha, itinerario_codigo, recorrido, hora_despacho, hora_fin, chainpc, shift_id)
                VALUES (?, ?, ?, ?, ?, ?,?)
            ''', (
                fecha,
                itinerario_codigo,
                item.get("recorrido", ""),
                item.get("hora_despacho", ""),
                item.get("hora_fin", ""),
                chainpc_json,
                shift_id
            ))
        conn.commit()


def cargar_desde_sqlite(fecha):
    import json
    conn = sqlite3.connect('itinerarios.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS itinerarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            itinerario_codigo TEXT,
            recorrido TEXT,
            hora_despacho TEXT,
            hora_fin TEXT,
            chainpc TEXT,
            shift_id INTEGER
        )
    ''')

    cursor.execute('''
        SELECT itinerario_codigo, recorrido, hora_despacho, hora_fin, chainpc, shift_id
        FROM itinerarios WHERE fecha = ?
    ''', (fecha,))
    filas = cursor.fetchall()
    conn.close()

    if not filas:
        return None, []

    codigo_itinerario = filas[0][0]
    itinerarios = []
    for f in filas:
        chainpc_json = f[4]
        try:
            chainpc = json.loads(chainpc_json)
        except Exception:
            chainpc = []
        itinerarios.append({
            "recorrido": f[1],
            "hora_despacho": f[2],
            "hora_fin": f[3],
            "chainpc": chainpc,
            "shift_id": f[5]  # Aquí incluyes shift_id
        })
    return codigo_itinerario, itinerarios

