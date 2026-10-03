from pathlib import Path

import sounddevice as sd
from faster_whisper import WhisperModel
from scipy.io.wavfile import write

from nlu import StructureBNLUPredictor

SAMPLE_RATE = 16000
DURATION = 5
AUDIO_FILE = Path("input.wav")
NLU_MODEL_DIR = Path("nlu/saved_models/structure_b_item_query_decoder")
INITIAL_PROMPT = (
    "카페 주문 문장입니다. 메뉴는 아메리카노, 카페라떼, 바닐라라떼, "
    "딸기스무디, 레몬에이드입니다. 아아는 아이스 아메리카노입니다."
)

_whisper_model = None
_nlu_model = None


def get_whisper_model() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel(
            "small",
            device="cuda",
            compute_type="int8",
        )
    return _whisper_model


def get_nlu_model() -> StructureBNLUPredictor:
    global _nlu_model
    if _nlu_model is None:
        _nlu_model = StructureBNLUPredictor(NLU_MODEL_DIR)
    return _nlu_model


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
    print("녹음 완료. 텍스트 변환 중...")
    return AUDIO_FILE


def transcribe_audio(audio_path: Path) -> str:
    segments, _ = get_whisper_model().transcribe(
        str(audio_path),
        language="ko",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
        initial_prompt=INITIAL_PROMPT,
        temperature=0.0,
    )
    return " ".join(segment.text for segment in segments).strip()


def main() -> None:
    text = transcribe_audio(record_audio())
    print("STT 결과:", text)
    if not text:
        print("음성이 인식되지 않았습니다. 다시 말씀해주세요.")
        return

    result = get_nlu_model().predict(text)
    print("NLU 분석 결과:", result)


if __name__ == "__main__":
    main()
