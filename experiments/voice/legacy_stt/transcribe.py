from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")

def transcribe_audio(filename="input.wav"):
    segments, _ = model.transcribe(filename, language="ko")
    text = " ".join([seg.text for seg in segments])
    return text