import subprocess

PIPER_BIN = "/home/admin/piper/piper/piper"
MODEL = "/home/admin/piper/voices/es_MX-claude-high.onnx"
SAMPLE_RATE = "22050"

def hablar(texto: str):
    try:
        piper = subprocess.Popen(
            [
                PIPER_BIN,
                "--model",
                MODEL,
                "--output_file", "-"
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

        audio, _ = piper.communicate(texto.encode("utf-8"))

        aplay = subprocess.Popen(
            ["aplay", "-f", "S16_LE", "-r", SAMPLE_RATE],
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

        aplay.communicate(audio)

    except Exception as e:
        print(f"[TTS] Error: {e}")
