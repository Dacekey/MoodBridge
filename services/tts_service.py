from __future__ import annotations

import asyncio
import logging
import os
import queue
import tempfile
import threading
from typing import List, Optional

import edge_tts
from edge_tts.exceptions import NoAudioReceived
from pydub import AudioSegment
from pydub.playback import play

logger = logging.getLogger(__name__)


class TTSService:
    """
    Production-ready streaming TTS service.

    Features:
    - sentence buffering
    - spam token guard
    - retry logic
    - voice fallback
    - safe worker thread
    - graceful shutdown
    - speaking state tracking
    """

    def __init__(
        self,
        voice: str = "en-US-AnaNeural",
        fallback_voices: Optional[List[str]] = None,
        rate: str = "+0%",
        volume: str = "+0%",
        min_chunk_chars: int = 5,
        max_retries: int = 1,
    ) -> None:
        self.voice = voice

        self._worker_active = False

        self.fallback_voices = fallback_voices or [
            "en-US-JennyNeural",
            "en-US-GuyNeural",
        ]

        self.rate = rate
        self.volume = volume

        self.min_chunk_chars = min_chunk_chars
        self.max_retries = max_retries

        self._queue: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()

        self._sentence_buffer = ""

        self._last_token: Optional[str] = None
        self._repeat_token_count = 0

        self._is_speaking = False
        self._state_lock = threading.Lock()

        self._thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
        )
        self._thread.start()

        logger.info(
            "[TTS] Service started | voice=%s",
            self.voice,
        )

    # ------------------------------------------------
    # Public API
    # ------------------------------------------------

    def feed_token(self, token: str) -> None:
        if token is None:
            return

        if not token.strip():
            return

        if self._is_spam_token(token):
            logger.debug("[TTS] Ignored spam token: %r", token)
            return

        self._sentence_buffer += token

        if self._ends_sentence(self._sentence_buffer):
            self._enqueue_buffer()

    def flush(self) -> None:
        self._enqueue_buffer()

    def is_speaking(self) -> bool:
        with self._state_lock:
            return self._is_speaking

    def is_busy(self) -> bool:
        if self.is_speaking():
            return True

        if self._worker_active:
            return True

        if not self._queue.empty():
            return True

        if self._sentence_buffer.strip():
            return True

        return False

    def shutdown(self) -> None:
        logger.info("[TTS] Shutdown requested")

        try:
            self.flush()
        except Exception:
            pass

        self._stop_event.set()
        self._thread.join(timeout=3)

    # ------------------------------------------------
    # Worker
    # ------------------------------------------------

    def _worker_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.5)
                self._worker_active = True
                try:
                    loop.run_until_complete(self._synthesize_with_fallback(text))
                finally:
                    self._worker_active = False

            except queue.Empty:
                continue

            except Exception as exc:
                self._worker_active = False
                logger.exception("[TTS] Worker error: %s", exc)

    # ------------------------------------------------
    # Voice fallback logic
    # ------------------------------------------------

    async def _synthesize_with_fallback(
        self,
        text: str,
    ) -> None:
        voices = [self.voice] + self.fallback_voices

        for voice in voices:
            for attempt in range(self.max_retries + 1):
                success = await self._try_synthesize_once(
                    text=text,
                    voice=voice,
                    attempt=attempt,
                )

                if success:
                    return

        logger.warning("[TTS] All voices failed. Dropping chunk.")

    async def _try_synthesize_once(
        self,
        text: str,
        voice: str,
        attempt: int,
    ) -> bool:
        tmp_path = None

        try:
            logger.info(
                "[TTS] Synthesizing | voice=%s | attempt=%d",
                voice,
                attempt + 1,
            )

            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=self.rate,
                volume=self.volume,
            )

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".mp3",
            ) as tmp:
                tmp_path = tmp.name

            await communicate.save(tmp_path)

            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                raise RuntimeError("Empty audio file")

            audio = AudioSegment.from_file(
                tmp_path,
                format="mp3",
            )

            try:
                self._set_speaking(True)
                play(audio)
                logger.info("[TTS] Playback finished")
                return True
            finally:
                self._set_speaking(False)

        except NoAudioReceived:
            logger.warning(
                "[TTS] NoAudioReceived | voice=%s | attempt=%d",
                voice,
                attempt + 1,
            )

            await asyncio.sleep(0.3)
            return False

        except Exception as exc:
            logger.warning(
                "[TTS] Synthesis failed | voice=%s | attempt=%d | error=%s",
                voice,
                attempt + 1,
                exc,
            )

            await asyncio.sleep(0.3)
            return False

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # ------------------------------------------------
    # Queue helpers
    # ------------------------------------------------

    def _enqueue_buffer(self) -> None:
        cleaned = self._clean_text(self._sentence_buffer)
        self._sentence_buffer = ""

        if not cleaned:
            return

        if len(cleaned) < self.min_chunk_chars:
            logger.debug("[TTS] Skip too-short chunk: %r", cleaned)
            return

        try:
            self._queue.put_nowait(cleaned)
            logger.info("[TTS] Enqueued: %r", cleaned)

        except Exception as exc:
            logger.exception("[TTS] Failed to enqueue: %s", exc)

    def _set_speaking(self, value: bool) -> None:
        with self._state_lock:
            self._is_speaking = value

    # ------------------------------------------------
    # Utilities
    # ------------------------------------------------

    def _clean_text(
        self,
        text: str,
    ) -> str:
        if not text:
            return ""

        return " ".join(text.strip().split())

    def _ends_sentence(
        self,
        text: str,
    ) -> bool:
        stripped = text.rstrip()

        if not stripped:
            return False

        return stripped.endswith(
            (
                ".",
                "!",
                "?",
                "\n",
            )
        )

    def _is_spam_token(
        self,
        token: str,
    ) -> bool:
        if token == self._last_token:
            self._repeat_token_count += 1
        else:
            self._last_token = token
            self._repeat_token_count = 1

        return self._repeat_token_count > 3