# demos/demo_conversation.py

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List

import cv2

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.audio_recorder import (
    MicrophoneUnavailableError,
    NoSpeechDetectedError,
    RecordingTimeoutError,
)
from services.conversation_service import ConversationService, ConversationTurn
from services.emotion_service import EmotionService
from services.sounddevice_recorder import SoundDeviceRecorder
from services.speech_service import SpeechService, SpeechServiceError
from services.tts_service import TTSService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


class ConversationState(str, Enum):
    OPENING = "OPENING"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    IDLE = "IDLE"


@dataclass
class ConversationRuntime:
    state: ConversationState = ConversationState.OPENING
    last_opening_time: float = 0.0
    last_user_activity_time: float = field(default_factory=time.time)
    last_idle_followup_time: float = 0.0
    opening_cooldown_s: float = 10.0
    idle_timeout_s: float = 30.0
    idle_followup_cooldown_s: float = 15.0

    def set_state(self, new_state: ConversationState) -> None:
        if self.state != new_state:
            logger.info("[Runtime] State change: %s -> %s", self.state, new_state)
            self.state = new_state

    def should_run_opening(self) -> bool:
        return (time.time() - self.last_opening_time) >= self.opening_cooldown_s

    def mark_opening_done(self) -> None:
        self.last_opening_time = time.time()

    def mark_user_activity(self) -> None:
        self.last_user_activity_time = time.time()

    def should_trigger_idle(self) -> bool:
        return (time.time() - self.last_user_activity_time) >= self.idle_timeout_s

    def can_send_idle_followup(self) -> bool:
        return (time.time() - self.last_idle_followup_time) >= self.idle_followup_cooldown_s

    def mark_idle_followup_sent(self) -> None:
        self.last_idle_followup_time = time.time()


# -------------------------
# Global service setup
# -------------------------

emotion_service = EmotionService(
    smoothing_window=10,
    conf_threshold=0.5,
)

emotion_cap = cv2.VideoCapture(0)
if not emotion_cap.isOpened():
    raise RuntimeError("Cannot open webcam for emotion detection")

speech_language = os.getenv("MOODBRIDGE_LANG", "en")

speech_recorder = SoundDeviceRecorder(
    device=2,
    sample_rate=48000,
    frame_duration_ms=30,
    silence_duration_s=1.5,
    max_duration_s=12.0,
    no_speech_timeout_s=10.0,
    pre_speech_buffer_ms=500,
    vad_aggressiveness=3,
    min_speech_frames=3,
    resume_speech_frames=4,
    debug=True,
)

speech_service = SpeechService(
    recorder=speech_recorder,
    model_name="small",
    language=speech_language,
    debug=True,
)

tts_service = TTSService(
    voice="vi-VN-HoaiMyNeural" if speech_language == "vi" else "en-US-AnaNeural"
)


# -------------------------
# Adapters
# -------------------------

def get_latest_emotion() -> str:
    result = emotion_service.predict_from_capture(
        cap=emotion_cap,
        num_frames=5,
        min_valid_votes=2,
    )

    print(
        f"[Emotion Detection] emotion={result['emotion']}, "
        f"conf={result['confidence']:.3f}, "
        f"source={result['source']}, "
        f"votes={result['vote_count']}/{result['total_frames']}"
    )

    if result["source"] == "unknown":
        return "unknown"

    return result["emotion"]


def get_user_speech_text() -> str:
    if tts_service.is_speaking():
        print("[Speech] AI is speaking, skip listening.")
        return ""

    try:
        print("[Speech] Listening for one utterance...")

        start = time.perf_counter()
        text = speech_service.listen_and_transcribe()
        elapsed = time.perf_counter() - start

        text = text.strip()

        print(f"[Speech] Transcription done in {elapsed:.3f}s")
        print(f"[Speech] Recognized text: {text}")

        return text

    except NoSpeechDetectedError as exc:
        print(f"[Speech] No speech detected: {exc}")
        return ""

    except RecordingTimeoutError as exc:
        print(f"[Speech] Recording timeout: {exc}")
        return ""

    except MicrophoneUnavailableError as exc:
        print(f"[Speech] Microphone unavailable: {exc}")
        raise

    except SpeechServiceError as exc:
        print(f"[Speech] Speech service error: {exc}")
        return ""


def build_idle_followup(language: str = "en") -> str:
    if language == "vi":
        return "Mình vẫn ở đây. Nếu bạn muốn nói tiếp, mình đang lắng nghe."
    return "I'm still here with you. If you'd like to keep talking, I'm listening."


def speak_text_direct(text: str) -> None:
    try:
        # push full sentence into streaming TTS
        tts_service.feed_token(text)
        tts_service.flush()

    except Exception as exc:
        logger.exception("[TTS] Direct speak failed: %s", exc)


def print_header() -> None:
    print("=" * 60)
    print("MoodBridge - Demo Conversation")
    print("Type 'exit' or 'quit' to stop.")
    print("=" * 60)


# -------------------------
# Phases
# -------------------------

def run_opening_phase(
    service: ConversationService,
    runtime: ConversationRuntime,
    language: str,
    conversation_history: List[ConversationTurn],
) -> None:
    if not runtime.should_run_opening():
        logger.info("[Opening] Skipped due to cooldown")
        return

    runtime.set_state(ConversationState.OPENING)

    print("\n[Opening] Detecting initial emotion...")

    emotion_start = time.perf_counter()
    detected_emotion = get_latest_emotion()
    emotion_latency = time.perf_counter() - emotion_start

    print("[Opening] Generating opening message...")

    runtime.set_state(ConversationState.THINKING)

    llm_start = time.perf_counter()
    result = service.generate_opening_message(
        detected_emotion=detected_emotion,
        language=language,
        tts_callback=tts_service.feed_token,
    )
    llm_latency = time.perf_counter() - llm_start

    runtime.set_state(ConversationState.SPEAKING)

    print(f"\n[Opening Emotion] {detected_emotion}")
    print(f"AI: {result.response_text}\n")

    conversation_history.append(
        ConversationTurn(role="assistant", content=result.response_text)
    )
    conversation_history[:] = conversation_history[-10:]

    runtime.mark_opening_done()

    print("[Opening Latency]")
    print(f"  emotion: {emotion_latency:.3f}s")
    print(f"  llm    : {llm_latency:.3f}s")
    print("-" * 60)


def run_idle_followup(
    runtime: ConversationRuntime,
    language: str,
    conversation_history: List[ConversationTurn],
) -> None:
    if not runtime.should_trigger_idle():
        return

    if not runtime.can_send_idle_followup():
        return

    runtime.set_state(ConversationState.IDLE)

    idle_text = build_idle_followup(language)

    print(f"\n[Idle] AI follow-up: {idle_text}")

    speak_text_direct(idle_text)

    conversation_history.append(
        ConversationTurn(role="assistant", content=idle_text)
    )
    conversation_history[:] = conversation_history[-10:]

    runtime.mark_idle_followup_sent()


# -------------------------
# Main loop
# -------------------------

def main() -> None:
    service = ConversationService(
        mode=os.getenv("CONVERSATION_MODE", "mock"),
        model_name=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        timeout=30,
    )

    language = os.getenv("MOODBRIDGE_LANG", "en")
    conversation_history: List[ConversationTurn] = []
    runtime = ConversationRuntime()

    print_header()

    try:
        run_opening_phase(
            service=service,
            runtime=runtime,
            language=language,
            conversation_history=conversation_history,
        )

        while True:
            if tts_service.is_speaking():
                runtime.set_state(ConversationState.SPEAKING)
                time.sleep(0.05)
                continue

            run_idle_followup(
                runtime=runtime,
                language=language,
                conversation_history=conversation_history,
            )

            if runtime.state == ConversationState.IDLE:
                time.sleep(0.1)
                continue

            total_start = time.perf_counter()

            try:
                runtime.set_state(ConversationState.LISTENING)

                emotion_start = time.perf_counter()
                detected_emotion = get_latest_emotion()
                emotion_latency = time.perf_counter() - emotion_start

                speech_start = time.perf_counter()
                user_text = get_user_speech_text()
                speech_latency = time.perf_counter() - speech_start

                if not user_text:
                    time.sleep(0.1)
                    continue

                runtime.mark_user_activity()

                if user_text.lower() in {"exit", "quit"}:
                    print("Stopping conversation demo.")
                    break

                runtime.set_state(ConversationState.THINKING)

                llm_start = time.perf_counter()
                result = service.generate_response(
                    user_text=user_text,
                    detected_emotion=detected_emotion,
                    language=language,
                    conversation_history=conversation_history,
                    tts_callback=tts_service.feed_token,
                )
                llm_latency = time.perf_counter() - llm_start

                runtime.set_state(ConversationState.SPEAKING)

                total_latency = time.perf_counter() - total_start

                print(f"\n[State] {runtime.state}")
                print(f"[Emotion] {detected_emotion}")
                print(f"AI: {result.response_text}\n")

                conversation_history.append(
                    ConversationTurn(role="user", content=user_text)
                )
                conversation_history.append(
                    ConversationTurn(role="assistant", content=result.response_text)
                )
                conversation_history[:] = conversation_history[-10:]

                print("[Latency]")
                print(f"  emotion: {emotion_latency:.3f}s")
                print(f"  speech : {speech_latency:.3f}s")
                print(f"  llm    : {llm_latency:.3f}s")
                print(f"  total  : {total_latency:.3f}s")
                print("-" * 60)

            except Exception as exc:
                print(f"\n[ERROR] {exc}")
                print("Continuing loop...\n")
                time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopped by user.")

    finally:
        print("Releasing emotion camera...")

        if emotion_cap is not None and emotion_cap.isOpened():
            emotion_cap.release()

        tts_service.shutdown()


if __name__ == "__main__":
    main()