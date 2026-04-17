from __future__ import annotations

import queue
import tempfile
import time
import wave
from collections import deque
from typing import Deque, List, Optional

import numpy as np
import sounddevice as sd
import webrtcvad

from services.audio_recorder import (
    AudioRecorder,
    AudioRecorderError,
    MicrophoneUnavailableError,
    NoSpeechDetectedError,
    RecordingTimeoutError,
)


class SoundDeviceRecorder(AudioRecorder):
    """
    Record speech from microphone using sounddevice + WebRTC VAD.

    Flow:
    - Open microphone input stream
    - Read small PCM frames continuously
    - Wait until speech starts
    - Keep recording while speech continues
    - Stop after sustained silence
    - Save the utterance to a temporary WAV file
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        dtype: str = "int16",
        frame_duration_ms: int = 30,
        silence_duration_s: float = 1.2,
        max_duration_s: float = 10.0,
        no_speech_timeout_s: float = 10.0,
        pre_speech_buffer_ms: int = 300,
        vad_aggressiveness: int = 2,
        min_speech_frames: int = 3,
        resume_speech_frames: int = 2,
        device: Optional[int | str] = None,
        debug: bool = True,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.frame_duration_ms = frame_duration_ms
        self.silence_duration_s = silence_duration_s
        self.max_duration_s = max_duration_s
        self.no_speech_timeout_s = no_speech_timeout_s
        self.pre_speech_buffer_ms = pre_speech_buffer_ms
        self.vad_aggressiveness = vad_aggressiveness
        self.min_speech_frames = min_speech_frames
        self.resume_speech_frames = resume_speech_frames
        self.device = device
        self.debug = debug

        self._validate_config()

        self.vad = webrtcvad.Vad(self.vad_aggressiveness)
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000)
        self.frame_bytes = self.frame_size * 2  # int16 mono => 2 bytes/sample

    def _validate_config(self) -> None:
        if self.sample_rate not in (8000, 16000, 32000, 48000):
            raise ValueError(
                "webrtcvad only supports sample rates: 8000, 16000, 32000, 48000."
            )
        if self.channels != 1:
            raise ValueError("Only mono audio is supported.")
        if self.dtype != "int16":
            raise ValueError("Only int16 PCM is supported.")
        if self.frame_duration_ms not in (10, 20, 30):
            raise ValueError("webrtcvad only supports frame durations of 10, 20, or 30 ms.")
        if self.silence_duration_s <= 0:
            raise ValueError("silence_duration_s must be > 0.")
        if self.max_duration_s <= 0:
            raise ValueError("max_duration_s must be > 0.")
        if self.no_speech_timeout_s <= 0:
            raise ValueError("no_speech_timeout_s must be > 0.")
        if not (0 <= self.vad_aggressiveness <= 3):
            raise ValueError("vad_aggressiveness must be in [0, 3].")
        if self.min_speech_frames <= 0:
            raise ValueError("min_speech_frames must be > 0.")
        if self.resume_speech_frames <= 0:
            raise ValueError("resume_speech_frames must be > 0.")

    def _log(self, message: str) -> None:
        if self.debug:
            print(message)

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        callback_time,
        status,
        audio_queue: queue.Queue[bytes],
    ) -> None:
        if status:
            self._log(f"[sounddevice status] {status}")

        try:
            if indata.ndim == 2:
                mono = indata[:, 0]
            else:
                mono = indata

            pcm_bytes = mono.astype(np.int16).tobytes()
            audio_queue.put_nowait(pcm_bytes)
        except queue.Full:
            self._log("[warning] Audio queue is full, dropping frame.")
        except Exception as exc:
            self._log(f"[callback error] {exc}")

    def _save_wav(self, pcm_frames: List[bytes]) -> str:
        if not pcm_frames:
            raise AudioRecorderError("No audio frames to save.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            wav_path = tmp_file.name

        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(self.sample_rate)
            wf.writeframes(b"".join(pcm_frames))

        return wav_path

    def record_until_silence(self) -> str:
        """
        Record one utterance from the microphone until sustained silence is detected.

        Returns:
            str: Temporary WAV path.
        """
        self._log("Listening...")

        audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=200)
        temp_buffer = bytearray()

        pre_speech_frames: Deque[bytes] = deque(
            maxlen=max(1, self.pre_speech_buffer_ms // self.frame_duration_ms)
        )
        recorded_frames: List[bytes] = []

        speech_started = False
        speech_start_time: Optional[float] = None
        listen_start_time = time.time()

        speech_frame_count = 0
        silence_frame_count = 0
        resume_speech_count = 0
        silence_phase_started = False

        required_silence_frames = max(
            1,
            int(round(self.silence_duration_s * 1000 / self.frame_duration_ms)),
        )

        blocksize = self.frame_size

        try:
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                blocksize=blocksize,
                device=self.device,
                callback=lambda indata, frames, callback_time, status: self._audio_callback(
                    indata, frames, callback_time, status, audio_queue
                ),
            )
        except Exception as exc:
            raise MicrophoneUnavailableError(f"Failed to open microphone stream: {exc}") from exc

        try:
            with stream:
                while True:
                    now = time.time()

                    if not speech_started and (now - listen_start_time) > self.no_speech_timeout_s:
                        raise NoSpeechDetectedError(
                            f"No speech detected within {self.no_speech_timeout_s:.1f} seconds."
                        )

                    try:
                        chunk = audio_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    temp_buffer.extend(chunk)

                    while len(temp_buffer) >= self.frame_bytes:
                        frame = bytes(temp_buffer[: self.frame_bytes])
                        del temp_buffer[: self.frame_bytes]

                        is_speech = self.vad.is_speech(frame, self.sample_rate)

                        # --- volume filter ---
                        volume = np.abs(np.frombuffer(frame, dtype=np.int16)).mean()

                        # debug (optional)
                        # self._log(f"Volume: {volume:.1f}")

                        if volume < 200:
                            is_speech = False

                        if not speech_started:
                            pre_speech_frames.append(frame)

                            if is_speech:
                                speech_frame_count += 1
                            else:
                                speech_frame_count = 0

                            if speech_frame_count >= self.min_speech_frames:
                                speech_started = True
                                speech_start_time = time.time()
                                silence_frame_count = 0
                                resume_speech_count = 0
                                silence_phase_started = False

                                self._log("Speech detected")

                                recorded_frames.extend(pre_speech_frames)
                                pre_speech_frames.clear()

                            continue

                        recorded_frames.append(frame)

                        elapsed_recording = time.time() - speech_start_time
                        if elapsed_recording > self.max_duration_s:
                            self._log("Maximum recording duration reached")

                            wav_path = self._save_wav(recorded_frames)

                            self._log(f"Saved temporary WAV before timeout: {wav_path}")

                            return wav_path

                        if is_speech:
                            resume_speech_count += 1

                            if silence_frame_count > 0 and resume_speech_count >= self.resume_speech_frames:
                                self._log("Speech resumed")
                                silence_frame_count = 0
                                resume_speech_count = 0
                                silence_phase_started = False
                        else:
                            resume_speech_count = 0

                            if not silence_phase_started:
                                self._log("Silence started")
                                silence_phase_started = True

                            silence_frame_count += 1
                            silence_elapsed = silence_frame_count * self.frame_duration_ms / 1000.0
                            self._log(f"Silence duration: {silence_elapsed:.2f}s")

                            if silence_frame_count >= required_silence_frames:
                                self._log("Silence threshold reached")
                                self._log("Recording stopped")

                                wav_path = self._save_wav(recorded_frames)
                                self._log(f"Saved temporary WAV: {wav_path}")
                                return wav_path

        except sd.PortAudioError as exc:
            raise MicrophoneUnavailableError(f"PortAudio error: {exc}") from exc
        except (NoSpeechDetectedError, RecordingTimeoutError):
            raise
        except Exception as exc:
            raise AudioRecorderError(f"Unexpected recording error: {exc}") from exc