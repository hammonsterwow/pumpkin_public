from pathlib import Path
from time import perf_counter

import sounddevice as sd
from faster_whisper import WhisperModel
from scipy.io.wavfile import write

SAMPLE_RATE = 16000
DURATION = 5
AUDIO_FILE = Path("stt_test.wav")
MODEL_NAME = "small"
DEVICE = "cuda"
COMPUTE_TYPE = "int8"


def record_audio() -> Path:
    print(f"{DURATION}초 동안 말씀해주세요...")
    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    write(str(AUDIO_FILE), SAMPLE_RATE, audio)
    print(f"녹음 완료: {AUDIO_FILE}")
    return AUDIO_FILE


def main() -> None:
    audio_path = record_audio()

    print(
        f"모델 로드 중: {MODEL_NAME} "
        f"(device={DEVICE}, compute_type={COMPUTE_TYPE})"
    )
    load_started = perf_counter()
    model = WhisperModel(
        MODEL_NAME,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
    )
    print(f"모델 로드 시간: {perf_counter() - load_started:.2f}초")

    transcribe_started = perf_counter()
    segments, info = model.transcribe(
        str(audio_path),
        language="ko",
        vad_filter=True,
        beam_size=5,
    )
    text = " ".join(segment.text.strip() for segment in segments).strip()
    elapsed = perf_counter() - transcribe_started

    print(f"감지 언어: {info.language}")
    print(f"STT 처리 시간: {elapsed:.2f}초")
    print(f"STT 결과: {text or '[인식 결과 없음]'}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n테스트가 중단되었습니다.")
    except Exception as error:
        print(f"STT 테스트 실패: {type(error).__name__}: {error}")
        raise
