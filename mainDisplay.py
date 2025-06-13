import threading
import time
from ComandosNextion import leer_serial
from despachos import escuchar_itinerario
from GpsDisplay import iniciar_gps_display

def main():
    evento_itinerario = threading.Event()

    hilo_serial = threading.Thread(target=leer_serial, args=(evento_itinerario,), daemon=True)
    hilo_itinerario = threading.Thread(target=escuchar_itinerario, args=(evento_itinerario,), daemon=True)
    hilo_gps = threading.Thread(target=iniciar_gps_display, daemon=True)

    hilo_serial.start()
    hilo_itinerario.start()
    hilo_gps.start()

    print("[Main] Sistema iniciado. Esperando comandos...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Saliendo...")

if __name__ == "__main__":
    main()
