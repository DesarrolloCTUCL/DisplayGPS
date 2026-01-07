import threading
import tkinter as tk

from despachos import escuchar_itinerario
from GpsDisplay import iniciar_gps_display
from TestGui import TestGUI
from tts import hablar   # 👈 TTS

def anunciar_inicio():
    hablar("Sistema iniciado,Bienvenido")

def main():
    # ===== Tkinter SIEMPRE en el hilo principal =====
    root = tk.Tk()
    app = TestGUI(root)

    # ===== Eventos compartidos =====
    evento_itinerario = threading.Event()

    # ===== Threads de lógica =====
    hilo_itinerario = threading.Thread(
        target=escuchar_itinerario,
        args=(evento_itinerario,),
        daemon=True
    )

    hilo_gps = threading.Thread(
        target=iniciar_gps_display,
        daemon=True
    )

    hilo_audio_inicio = threading.Thread(
        target=anunciar_inicio,
        daemon=True
    )

    hilo_itinerario.start()
    hilo_gps.start()
    hilo_audio_inicio.start()   # 🔊 "Sistema iniciado"

    print("[Main] Sistema iniciado con interfaz Tkinter")

    # ===== Loop gráfico (BLOQUEANTE) =====
    root.mainloop()

if __name__ == "__main__":
    main()
