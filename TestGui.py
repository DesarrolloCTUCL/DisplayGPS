import tkinter as tk
import platform

from datetime import datetime
from PIL import Image,ImageTk
from ui_bus import ui_queue

# ===== CONFIG =====
BG = "#0097b2"       # FONDO PRINCIPAL
BOX = "#0b5f73"      # cajas internas
LABEL = "#074a5a"    # etiquetas
FG = "#ffffff"

FONT_BIG = ("Arial", 22, "bold")
FONT_MED = ("Arial", 15, "bold")
FONT = ("Arial", 22)
FONT_SMALL = ("Arial", 18)


class TestGUI:
    def __init__(self, root):
        self.root = root

        self.is_pi = platform.system() == "Linux"

        self.root.configure(bg=BG)

        if self.is_pi:
            # PRODUCCIÓN (Raspberry)
            self.root.overrideredirect(True)
            self.root.attributes("-fullscreen", True)

            w = root.winfo_screenwidth()
            h = root.winfo_screenheight()
            self.root.geometry(f"{w}x{h}+0+0")
        else:
            # DESARROLLO (Windows / PyCharm)
            self.root.geometry("1200x700")
            self.root.title("Display – Modo Desarrollo")

        # ===== VARIABLES =====
        self.hora = tk.StringVar(value="00:00:00")
        self.fecha = tk.StringVar(value="00/00/0000")
        self.bus = tk.StringVar(value="SN")

        self.hora_inicio = tk.StringVar(value="00:00:00")
        self.hora_fin = tk.StringVar(value="00:00:00")
        self.hora_pc = tk.StringVar(value="--:--:--")

        self.punto = tk.StringVar(value="SIN DATOS")
        self.ruta = tk.StringVar(value="DESPACHO NO CARGADO")

        # ===== LOGO =====
        max_size = (120, 120)  # tamaño máximo
        max_size_icon = (80, 80)  # tamaño máximo

        img = Image.open("logo.png")
        img.thumbnail(max_size, Image.LANCZOS)  # 🔥 mantiene proporción

        imgicono = Image.open("iconoplay.png")
        imgicono.thumbnail(max_size_icon, Image.LANCZOS)  # 🔥 mantiene proporción

        self.iconoimg = ImageTk.PhotoImage(imgicono)
        self.logo_img = ImageTk.PhotoImage(img)  # ⚠️a guardar referencia

        self.build_ui()
        self.ui_queue = ui_queue
        self.root.after(100, self.procesar_eventos_ui)

    # ================= UI =================
    def build_ui(self):
        cont = tk.Frame(self.root, bg=BG)
        cont.pack(fill="both", expand=True)

        # ---------- FILA 1 ----------
        fila1 = self.row(cont)
        self.box(fila1, self.hora, FONT, expand=True)
        self.box(fila1, self.fecha, FONT, expand=True)
        self.box(fila1, self.bus, FONT, expand=True)

        # ---------- FILA 2 ----------
        fila2 = self.row(cont)
        self.tag(fila2, "Hora de inicio", FONT_MED, width=250)
        self.box(fila2, self.hora_inicio, FONT, expand=False, width=180)
        self.spacer(fila2, width=100)
        self.logo(fila2)

        # ---------- FILA 3 ----------
        fila3 = self.row(cont)
        self.tag(fila3, "Hora finalización",FONT_MED, width=250)
        self.box(fila3, self.hora_fin, FONT, expand=False, width=180)
        self.tag(fila3, "Sig punto",FONT_MED ,width= 150)
        self.box(fila3, self.hora_pc, FONT, expand=True)

        # ---------- FILA 4 ----------
        fila4 = self.row(cont)
        self.tag(fila4, "Siguiente punto  ",FONT_MED, width=250)
        self.box(fila4, self.punto, FONT, expand=True)

        # ---------- FILA 5 ----------
        fila5 = self.row(cont)
        self.box(fila5, self.ruta, FONT_BIG, expand=True)
        self.icono(fila5)
    # ================= COMPONENTES =================
    def row(self, parent):
        f = tk.Frame(parent, bg=BG, height=80)
        f.pack(fill="x", expand=True, pady=8, padx=10)
        f.pack_propagate(False)  # 🔒 NO dejar que hijos cambien altura
        return f

    def tag(self, parent, text, font, width=200):
        frame = tk.Frame(parent, bg=BG, width=width)
        frame.pack(side="left", padx=6, fill="y")
        frame.pack_propagate(False)  # 🔒 fuerza el ancho

        lbl = tk.Label(
            frame,
            text=text.upper(),
            font=font,
            bg="#D3D3D3",
            fg="#000000",
            anchor="center",
            relief="solid",
            bd=1
        )
        lbl.pack(fill="both", expand=True)

        return frame

    def box(self, parent, variable, font, width=250, expand=False):
        frame = tk.Frame(parent, bg=BG, width=width)
        frame.pack(
            side="left",
            padx=6,
            fill="y" if not expand else "both",
            expand=expand
        )
        frame.pack_propagate(False)

        upper_var = tk.StringVar()

        def to_upper(*_):
            upper_var.set(variable.get().upper())

        variable.trace_add("write", to_upper)
        to_upper()

        lbl = tk.Label(
            frame,
            textvariable=upper_var,
            font=font,
            bg="#ffffff",
            fg="#000000",
            anchor="center",
            relief="solid",
            bd=1
        )
        lbl.pack(fill="both", expand=True)

        return frame

    def logo(self, parent):
        lbl = tk.Label(
            parent,
            image=self.logo_img,
            bg=BG
        )
        lbl.pack(
            side="left",
            padx=10,
            fill="y"
        )
        return lbl

    def icono(self, parent):
        lbl = tk.Label(
            parent,
            image=self.iconoimg,
            bg=BG
        )
        lbl.pack(
            side="left",
            padx=10,
            fill="y"
        )
        return lbl

    def spacer(self, parent, width=None, expand=False):
        s = tk.Frame(parent, bg=BG, width=width)
        s.pack(
            side="left",
            fill="x" if expand else "none",
            expand=expand
        )
        return s


    def procesar_eventos_ui(self):
        try:
            while not self.ui_queue.empty():
                evento = self.ui_queue.get_nowait()

                tipo = evento.get("type")

                if tipo == "hora":
                    self.hora.set(evento["hora"])

                elif tipo == "fecha":
                    self.fecha.set(evento["fecha"])

                elif tipo == "ruta":
                    self.ruta.set(evento["ruta"])

                elif tipo == "punto":
                    self.punto.set(evento["punto"])

                elif tipo == "hora_inicio":
                    self.hora_inicio.set(evento["hora_inicio"])

                elif tipo == "hora_fin":
                    self.hora_fin.set(evento["hora_fin"])

                elif tipo == "bus":
                    self.bus.set(evento["bus"])
                    
                elif tipo == "hora_pc":
                    self.hora_pc.set(evento["hora_pc"])


        except Exception as e:
            print("Error UI:", e)

        self.root.after(100, self.procesar_eventos_ui)




# ================= MAIN =================
if __name__ == "__main__":
    root = tk.Tk()
    app = TestGUI(root)
    root.mainloop()
