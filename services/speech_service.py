from __future__ import annotations

import os
from typing import Optional

import whisper

from services.audio_recorder import (
    AudioRecorder,
    AudioRecorderError,
    NoSpeechDetectedError,
    RecordingTimeoutError,
)


class SpeechServiceError(Exception):
    """Base exception for speech service errors."""


class SpeechService:
    """
    Speech input service that:
    1. records one utterance through AudioRecorder
    2. sends audio to Whisper
    3. returns transcription text
    """

    def __init__(
        self,
        recorder: AudioRecorder,
        model_name: str = "base",
        language: Optional[str] = None,
        debug: bool = True,
    ) -> None:
        self.recorder = recorder
        self.model_name = model_name
        self.language = language
        self.debug = debug

        self._model = whisper.load_model(self.model_name)

    def _log(self, message: str) -> None:
        if self.debug:
            print(message)

    def listen_and_transcribe(self) -> str:
        wav_path: Optional[str] = None

        try:
            wav_path = self.recorder.record_until_silence()

            self._log("Transcribing...")

            result = self._model.transcribe(
                wav_path,
                language=self.language,
                fp16=False,
            )

            text = result.get("text", "").strip()

            if not text:
                raise SpeechServiceError("Transcription is empty.")

            self._log("Transcription complete")
            return text

        except NoSpeechDetectedError:
            raise
        except RecordingTimeoutError:
            raise
        except AudioRecorderError:
            raise
        except Exception as exc:
            raise SpeechServiceError(f"Failed to transcribe audio: {exc}") from exc
        finally:
            if wav_path and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except OSError:
                    pass