import threading
import time
import tkinter as tk

from ComandosNextion import leer_serial
from despachos import escuchar_itinerario
from GpsDisplay import iniciar_gps_display
from TestGui import TestGUI   # 👈 tu interfaz Tkinter


def main():
    # ===== Tkinter SIEMPRE en el hilo principal =====
    root = tk.Tk()
    app = TestGUI(root)

    # ===== Eventos compartidos =====
    evento_itinerario = threading.Event()

    # ===== Threads de lógica =====
    hilo_serial = threading.Thread(
        target=leer_serial,
        args=(evento_itinerario,),
        daemon=True
    )

    hilo_itinerario = threading.Thread(
        target=escuchar_itinerario,
        args=(evento_itinerario,),
        daemon=True
    )

    hilo_gps = threading.Thread(
        target=iniciar_gps_display,
        daemon=True
    )

    hilo_serial.start()
    hilo_itinerario.start()
    hilo_gps.start()

    print("[Main] Sistema iniciado con interfaz Tkinter")

    # ===== Loop gráfico (BLOQUEANTE) =====
    root.mainloop()


if __name__ == "__main__":
    main()
