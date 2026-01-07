import subprocess

TEXTO = (
    "Punto de control, Parque Bolivar. "
    "Siguiente punto de control, 9 y 13"
)

piper = subprocess.Popen(
    [
        "/home/admin/piper/piper/piper",
        "--model",
        "/home/admin/piper/voices/es_MX-claude-high.onnx",
        "--output_file", "-"
    ],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE
)

audio, _ = piper.communicate(TEXTO.encode("utf-8"))

aplay = subprocess.Popen(
    ["aplay", "-f", "S16_LE", "-r", "22050"],
    stdin=subprocess.PIPE
)

aplay.communicate(audio)
