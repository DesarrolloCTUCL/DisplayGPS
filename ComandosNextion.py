import serial
import threading
import queue
import time


# Configuración de la pantalla Nextion


nextion = serial.Serial('/dev/serial0', 9600, timeout=1)
#nextion = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
# Función para leer el puerto y meter datos en la cola
def leer_serial(evento_itinerario):
   
    while True:
        try:
            dato_bytes = nextion.read()
            dato = dato_bytes.decode('utf-8').strip()
        except UnicodeDecodeError:
            # Ignorar bytes que no se pueden decodificar
            continue
        print(f"Datos recibidos: {dato_bytes} -> {dato}")  # Antes del if dato
        if dato:
            if dato == "7":
                evento_itinerario.set()
            elif dato == "8":
                evento_itinerario.clear()
        time.sleep(0.1)

# Enviar texto al Nextion
last_sent_texts = {}
def send_to_nextion(text, text_id):
    global last_sent_texts
    if nextion.is_open:
        if last_sent_texts.get(text_id) != text:
            command = f'{text_id}.txt="{text}"'
            nextion.write(command.encode('utf-8'))
            nextion.write(b'\xFF\xFF\xFF')
            last_sent_texts[text_id] = text

# Enviar comando de reproducción de audio al Nextion
def send_to_nextionPlay(audio_index, va1_val):
    if nextion.is_open:
        command = f'play {audio_index},{va1_val},0'
        print(f"Enviando comando al Nextion: {command}")
        nextion.write(command.encode('utf-8') + b"\xFF\xFF\xFF")


dato_nextion = nextion.readline().decode('utf-8').strip()  # Leer datos de Nextion