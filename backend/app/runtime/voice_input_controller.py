from __future__ import annotations

import base64
import tempfile
import wave
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Deque, Optional

import numpy as np
import webrtcvad


@dataclass
class VoiceInputConfig:
    sample_rate: int = 16000
    frame_duration_ms: int = 20
    channels: int = 1
    vad_aggressiveness: int = 2

    pre_speech_frames: int = 10
    min_speech_frames: int = 5
    silence_threshold_frames: int = 75   # 75 * 20ms = 1.5s
    volume_threshold: float = 400.0

    # New anti-false-trigger guards
    warmup_frames: int = 25              # ~500ms after stream start
    post_utterance_cooldown_frames: int = 15   # ~300ms after utterance end
    min_utterance_frames: int = 20       # ~400ms minimum committed utterance


@dataclass
class VoiceInputEvents:
    on_speech_started: Optional[Callable[[], None]] = None
    on_speech_ended: Optional[Callable[[], None]] = None


@dataclass
class VoiceInputController:
    config: VoiceInputConfig = field(default_factory=VoiceInputConfig)
    events: VoiceInputEvents = field(default_factory=VoiceInputEvents)

    in_speech: bool = False
    speech_frames: int = 0
    silence_frames: int = 0
    utterance_frames: list[bytes] = field(default_factory=list)
    pre_buffer: Deque[bytes] = field(init=False)

    # New runtime counters
    warmup_remaining: int = 0
    cooldown_remaining: int = 0

    def __post_init__(self) -> None:
        self.vad = webrtcvad.Vad(self.config.vad_aggressiveness)
        self.pre_buffer = deque(maxlen=self.config.pre_speech_frames)
        self.warmup_remaining = self.config.warmup_frames
        self.cooldown_remaining = 0

    @property
    def frame_samples(self) -> int:
        return int(self.config.sample_rate * self.config.frame_duration_ms / 1000)

    @property
    def frame_bytes(self) -> int:
        return self.frame_samples * 2  # int16 mono

    def reset(self) -> None:
        self.in_speech = False
        self.speech_frames = 0
        self.silence_frames = 0
        self.utterance_frames.clear()
        self.pre_buffer.clear()

    def configure_stream(
        self,
        sample_rate: int,
        frame_duration_ms: int,
    ) -> None:
        self.config.sample_rate = sample_rate
        self.config.frame_duration_ms = frame_duration_ms
        self.reset()
        self.warmup_remaining = self.config.warmup_frames
        self.cooldown_remaining = 0

    def decode_base64_frame(self, samples_base64: str) -> bytes:
        frame_bytes = base64.b64decode(samples_base64)

        if len(frame_bytes) != self.frame_bytes:
            raise ValueError(
                f"Invalid PCM frame size. Expected {self.frame_bytes}, got {len(frame_bytes)}"
            )

        return frame_bytes

    def _frame_volume(self, frame_bytes: bytes) -> float:
        return float(np.abs(np.frombuffer(frame_bytes, dtype=np.int16)).mean())

    def _is_voiced(self, frame_bytes: bytes) -> bool:
        volume = self._frame_volume(frame_bytes)

        if volume < self.config.volume_threshold:
            return False

        return self.vad.is_speech(frame_bytes, self.config.sample_rate)

    def _enter_post_utterance_cooldown(self) -> None:
        self.cooldown_remaining = self.config.post_utterance_cooldown_frames

    def ingest_frame(self, frame_bytes: bytes) -> Optional[list[bytes]]:
        """
        Returns:
            None -> no utterance completed yet
            list[bytes] -> utterance completed and ready to commit
        """

        # Warmup guard: ignore initial frames after stream start
        if self.warmup_remaining > 0:
            self.warmup_remaining -= 1
            return None

        # Cooldown guard: ignore a short period right after an utterance ends
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            return None

        is_speech = self._is_voiced(frame_bytes)

        if not self.in_speech:
            self.pre_buffer.append(frame_bytes)

            if is_speech:
                self.speech_frames += 1
            else:
                self.speech_frames = 0

            if self.speech_frames >= self.config.min_speech_frames:
                self.in_speech = True
                self.silence_frames = 0
                self.utterance_frames.extend(list(self.pre_buffer))
                self.pre_buffer.clear()

                if self.events.on_speech_started:
                    self.events.on_speech_started()

            return None

        # In speech
        self.utterance_frames.append(frame_bytes)

        if is_speech:
            self.silence_frames = 0
            return None

        self.silence_frames += 1

        if self.silence_frames >= self.config.silence_threshold_frames:
            completed = list(self.utterance_frames)

            if self.events.on_speech_ended:
                self.events.on_speech_ended()

            self.reset()
            self._enter_post_utterance_cooldown()

            # Drop too-short utterances
            if len(completed) < self.config.min_utterance_frames:
                return None

            return completed

        return None

    def flush_if_needed(self) -> Optional[list[bytes]]:
        if not self.utterance_frames:
            self.reset()
            self._enter_post_utterance_cooldown()
            return None

        completed = list(self.utterance_frames)

        if self.events.on_speech_ended:
            self.events.on_speech_ended()

        self.reset()
        self._enter_post_utterance_cooldown()

        if len(completed) < self.config.min_utterance_frames:
            return None

        return completed

    def save_wav(self, pcm_frames: list[bytes]) -> Path:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            wav_path = Path(tmp.name)

        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(self.config.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.config.sample_rate)
            wf.writeframes(b"".join(pcm_frames))

        return wav_path