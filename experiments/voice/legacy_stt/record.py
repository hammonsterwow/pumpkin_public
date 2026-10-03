import sounddevice as sd
from scipy.io.wavfile import write

def record_audio(filename="input.wav", duration=5, samplerate=16000):
    print("녹음 시작...")
    audio = sd.rec(int(duration * samplerate),
                   samplerate=samplerate,
                   channels=1,
                   dtype="int16")
    sd.wait()
    write(filename, samplerate, audio)
    print("녹음 완료")