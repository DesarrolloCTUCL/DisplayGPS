from gtts import gTTS
import os

tts = gTTS(
    text="Punto de control parque bolivar 07:50 am, proximo punto de control 8am",
    lang="es",
    slow=False
)
tts.save("inicio.mp3")

# Volumen digital máximo permitido por mpg123
os.system("mpg123 -f 49152 inicio.mp3")
