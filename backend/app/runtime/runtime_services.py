from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------
# Ensure project root is importable
# backend/app/runtime/runtime_services.py
# -> need access to top-level `services/`
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------

from services.conversation_service import ConversationService
from services.emotion_service import EmotionService
from services.tts_service import TTSService

logger = logging.getLogger(__name__)


# =====================================================================
# Upload Audio STT Service
# =====================================================================

class UploadAudioSTTService:
    """
    Minimal STT service for uploaded audio files from the frontend.

    This is separate from the local microphone SpeechService because:
    - SpeechService.listen_and_transcribe() is designed around AudioRecorder
    - frontend audio upload already gives us a completed audio file
    - here we only need: transcribe(audio_path) -> text
    """

    def __init__(
        self,
        model_name: str = "small",
        language: Optional[str] = None,
    ) -> None:
        import whisper

        self.model_name = model_name
        self.language = language
        self._model = whisper.load_model(model_name)

        logger.info(
            "[RuntimeServices] UploadAudioSTTService initialized | model=%s | language=%s",
            self.model_name,
            self.language or "auto",
        )

    def transcribe(self, audio_path: str) -> str:
        logger.info("[STT] Transcribing uploaded audio | path=%s", audio_path)

        result = self._model.transcribe(
            audio_path,
            language=self.language,
            fp16=False,
        )

        text = result.get("text", "").strip()

        logger.info("[STT] Uploaded audio transcription complete | text_len=%d", len(text))
        return text


# =====================================================================
# Runtime Services Container
# =====================================================================

@dataclass
class RuntimeServices:
    emotion_service: EmotionService
    conversation_service: ConversationService
    tts_service: TTSService
    stt_service: UploadAudioSTTService


# =====================================================================
# Builder
# =====================================================================

def build_runtime_services(language: str) -> RuntimeServices:
    """
    Build real service instances for one websocket session.

    This version is configured for:
    - Ollama / OpenAI-compatible LLM
    - local TTS
    - Emotion service
    - uploaded-audio STT for browser microphone recordings

    Environment variables supported:

        CONVERSATION_MODE
        LLM_API_KEY
        LLM_MODEL
        LLM_BASE_URL
        LLM_TIMEOUT
        STT_MODEL
    """

    # -----------------------------------------------------------------
    # Language normalization
    # -----------------------------------------------------------------

    safe_language = language if language in {"en", "vi"} else "en"

    # -----------------------------------------------------------------
    # Read environment variables
    # -----------------------------------------------------------------

    mode = os.getenv("CONVERSATION_MODE", "mock")

    model_name = os.getenv(
        "LLM_MODEL",
        "llama3",
    )

    api_key = os.getenv(
        "LLM_API_KEY",
        "dummy",
    )

    base_url = os.getenv(
        "LLM_BASE_URL",
        "http://localhost:11434/v1/chat/completions",
    )

    timeout = int(
        os.getenv(
            "LLM_TIMEOUT",
            "30",
        )
    )

    stt_model = os.getenv("STT_MODEL", "small")

    # -----------------------------------------------------------------
    # Log configuration
    # -----------------------------------------------------------------

    logger.info(
        "[RuntimeServices] Building services | mode=%s | model=%s | base_url=%s | stt_model=%s",
        mode,
        model_name,
        base_url,
        stt_model,
    )

    # -----------------------------------------------------------------
    # Emotion Service
    # -----------------------------------------------------------------

    emotion_service = EmotionService(
        smoothing_window=10,
        conf_threshold=0.5,
    )

    logger.info("[RuntimeServices] EmotionService initialized")

    # -----------------------------------------------------------------
    # Conversation Service (LLM)
    # -----------------------------------------------------------------

    conversation_service = ConversationService(
        mode=mode,
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
    )

    logger.info("[RuntimeServices] ConversationService ready")

    # -----------------------------------------------------------------
    # TTS Service
    # -----------------------------------------------------------------

    if safe_language == "vi":
        voice = "vi-VN-HoaiMyNeural"
    else:
        voice = "en-US-AnaNeural"

    tts_service = TTSService(
        voice=voice
    )

    logger.info(
        "[RuntimeServices] TTSService initialized | voice=%s",
        voice,
    )

    # -----------------------------------------------------------------
    # STT Service for uploaded browser audio
    # -----------------------------------------------------------------

    stt_service = UploadAudioSTTService(
        model_name=stt_model,
        language=safe_language,
    )

    logger.info("[RuntimeServices] STT service ready")

    # -----------------------------------------------------------------
    # Final container
    # -----------------------------------------------------------------

    return RuntimeServices(
        emotion_service=emotion_service,
        conversation_service=conversation_service,
        tts_service=tts_service,
        stt_service=stt_service,
    )