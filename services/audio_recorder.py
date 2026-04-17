from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class AudioRecorderError(Exception):
    """Base exception for audio recorder errors."""


class MicrophoneUnavailableError(AudioRecorderError):
    """Raised when microphone/device cannot be opened or used."""


class NoSpeechDetectedError(AudioRecorderError):
    """Raised when no speech is detected within the timeout window."""


class RecordingTimeoutError(AudioRecorderError):
    """Raised when recording exceeds the allowed maximum duration."""


class AudioRecorder(ABC):
    @abstractmethod
    def record_until_silence(self) -> str:
        """
        Record microphone audio until speech ends, then save to a temporary WAV file.

        Returns:
            str: Path to the temporary WAV file.

        Raises:
            NoSpeechDetectedError: If no speech is detected.
            MicrophoneUnavailableError: If microphone access fails.
            RecordingTimeoutError: If recording exceeds max duration.
            AudioRecorderError: For other audio-related failures.
        """
        raise NotImplementedError