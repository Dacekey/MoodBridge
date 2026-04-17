from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.runtime.runtime_services import RuntimeServices
from app.state.conversation_state import ConversationState

logger = logging.getLogger(__name__)

SendJSON = Callable[[dict], Awaitable[None]]

# Runtime-level defensive guard
MIN_RUNTIME_TRANSCRIPT_CHARS = 5
MIN_RUNTIME_TRANSCRIPT_WORDS = 2


@dataclass
class RuntimeConfig:
    opening_cooldown_s: float = 10.0
    idle_timeout_s: float = 30.0
    idle_followup_cooldown_s: float = 15.0
    loop_sleep_s: float = 0.05


@dataclass
class RuntimeContext:
    session_id: str
    language: str
    state: ConversationState = ConversationState.READY
    conversation_active: bool = False
    last_opening_time: float = 0.0
    last_user_activity_time: float = field(default_factory=time.time)
    last_idle_followup_time: float = 0.0
    latest_emotion: str = "unknown"
    latest_emotion_confidence: float = 0.0
    latest_emotion_source: str = "uninitialized"
    is_running: bool = True

    # debug fields
    state_entered_at: float = field(default_factory=time.time)
    last_sent_event_type: str = "-"
    last_sent_event_at: float = 0.0
    last_user_transcript_preview: str = "-"


class ConversationRuntime:
    def __init__(
        self,
        websocket: WebSocket,
        language: str,
        services: RuntimeServices,
        config: Optional[RuntimeConfig] = None,
    ) -> None:
        self.websocket = websocket
        self.config = config or RuntimeConfig()
        self.services = services
        self.ctx = RuntimeContext(
            session_id=str(uuid.uuid4()),
            language=language if language in {"en", "vi"} else "en",
        )
        self._conversation_history: list = []

    async def send_event(self, event_type: str, payload: dict) -> None:
        if not self.ctx.is_running:
            logger.debug(
                "[Runtime] send_event skipped | session=%s | reason=not_running | event=%s",
                self.ctx.session_id,
                event_type,
            )
            return

        logger.info(
            "[Runtime] Sending event | session=%s | state=%s | active=%s | tts_busy=%s | event=%s",
            self.ctx.session_id,
            self.ctx.state.value,
            self.ctx.conversation_active,
            self.services.tts_service.is_busy(),
            event_type,
        )

        try:
            await self.websocket.send_json(
                {
                    "type": event_type,
                    "payload": payload,
                }
            )
            self.ctx.last_sent_event_type = event_type
            self.ctx.last_sent_event_at = time.time()

        except WebSocketDisconnect:
            logger.warning(
                "[Runtime] Client disconnected while sending event | session=%s | state=%s | event=%s | last_sent=%s",
                self.ctx.session_id,
                self.ctx.state.value,
                event_type,
                self.ctx.last_sent_event_type,
            )
            self.ctx.is_running = False

        except RuntimeError as exc:
            logger.warning(
                "[Runtime] send_event skipped, websocket closed | session=%s | state=%s | event=%s | error=%s | last_sent=%s",
                self.ctx.session_id,
                self.ctx.state.value,
                event_type,
                exc,
                self.ctx.last_sent_event_type,
            )
            self.ctx.is_running = False

        except Exception as exc:
            logger.exception(
                "[Runtime] Unexpected send_event error | session=%s | state=%s | event=%s | error=%s",
                self.ctx.session_id,
                self.ctx.state.value,
                event_type,
                exc,
            )
            self.ctx.is_running = False

    async def set_state(self, new_state: ConversationState) -> None:
        if not self.ctx.is_running:
            return

        if self.ctx.state != new_state:
            now = time.time()
            dt = now - self.ctx.state_entered_at

            logger.info(
                "[Runtime] State change | session=%s | %s -> %s | dt=%.3fs | active=%s | tts_busy=%s",
                self.ctx.session_id,
                self.ctx.state,
                new_state,
                dt,
                self.ctx.conversation_active,
                self.services.tts_service.is_busy(),
            )

            self.ctx.state = new_state
            self.ctx.state_entered_at = now
            await self.send_event("state_update", {"state": new_state.value})

    async def emit_status(self) -> None:
        await self.send_event(
            "status_update",
            {
                "backend_connected": True,
                "conversation_active": self.ctx.conversation_active,
                "tts_busy": self.services.tts_service.is_busy(),
                "state": self.ctx.state.value,
                "language": self.ctx.language,
            },
        )

    async def start(self) -> None:
        logger.info(
            "[Runtime] Session started | session=%s | language=%s",
            self.ctx.session_id,
            self.ctx.language,
        )

        await self.send_event(
            "session_started",
            {
                "session_id": self.ctx.session_id,
                "language": self.ctx.language,
            },
        )

        await self.set_state(ConversationState.READY)
        await self.emit_status()

    async def stop(self) -> None:
        if not self.ctx.is_running:
            return

        self.ctx.is_running = False
        self.ctx.conversation_active = False

        try:
            self.services.tts_service.shutdown()
        except Exception as exc:
            logger.exception("[Runtime] Failed to shutdown TTS service: %s", exc)

        try:
            await self.set_state(ConversationState.STOPPED)
            await self.send_event("session_stopped", {})
        except Exception:
            pass

        logger.info("[Runtime] Session stopped | session=%s", self.ctx.session_id)

    async def start_conversation(self) -> None:
        if not self.ctx.is_running:
            return

        if self.ctx.conversation_active:
            logger.info(
                "[Runtime] start_conversation ignored, already active | session=%s | state=%s",
                self.ctx.session_id,
                self.ctx.state.value,
            )
            return

        self.ctx.conversation_active = True
        await self.send_event("conversation_started", {})
        await self.emit_status()
        await self.run_opening_phase()

    async def pause_conversation(self) -> None:
        if not self.ctx.is_running:
            return

        self.ctx.conversation_active = False
        await self.set_state(ConversationState.PAUSED)
        await self.send_event("conversation_paused", {})
        await self.emit_status()

    async def arm_listening(self) -> None:
        if not self.ctx.is_running:
            return

        if not self.ctx.conversation_active:
            logger.info(
                "[Runtime] arm_listening redirected to PAUSED | session=%s",
                self.ctx.session_id,
            )
            await self.set_state(ConversationState.PAUSED)
            return

        await self.set_state(ConversationState.ARMED_LISTENING)
        await self.emit_status()

    async def mark_speech_started(self) -> None:
        if not self.ctx.is_running:
            return

        if not self.ctx.conversation_active:
            return

        # Only allow transition from ARMED_LISTENING
        if self.ctx.state != ConversationState.ARMED_LISTENING:
            logger.info(
                "[Runtime] mark_speech_started ignored | session=%s | current_state=%s",
                self.ctx.session_id,
                self.ctx.state.value,
            )
            return

        await self.set_state(ConversationState.CAPTURING_USER)

    async def mark_speech_ended(self) -> None:
        if not self.ctx.is_running:
            return

        if not self.ctx.conversation_active:
            return

        logger.info(
            "[Runtime] mark_speech_ended | session=%s | current_state=%s",
            self.ctx.session_id,
            self.ctx.state.value,
        )
        # Keep current state; actual commit path will move to THINKING

    async def run_opening_phase(self) -> None:
        if not self.ctx.is_running:
            return

        if not self._should_run_opening():
            await self.arm_listening()
            return

        await self.set_state(ConversationState.OPENING)

        emotion, confidence, source = self._get_latest_emotion_for_runtime()
        await self._emit_emotion_update(emotion, confidence, source)

        await self.set_state(ConversationState.THINKING)

        result = await asyncio.to_thread(
            self.services.conversation_service.generate_opening_message,
            emotion,
            self.ctx.language,
            self.services.tts_service.feed_token,
        )

        if not self.ctx.is_running:
            return

        await self.set_state(ConversationState.SPEAKING)

        await self.send_event("ai_response_chunk", {"text": result.response_text})
        await self.send_event("ai_response_done", {"text": result.response_text})

        self._conversation_history.append(self._build_turn("assistant", result.response_text))
        self._conversation_history = self._conversation_history[-10:]

        self.ctx.last_opening_time = time.time()

        await self._wait_until_tts_idle()
        await self.arm_listening()

    async def run_loop(self) -> None:
        while self.ctx.is_running:
            await asyncio.sleep(self.config.loop_sleep_s)

    def _is_transcript_meaningful_runtime(self, text: str) -> bool:
        cleaned = text.strip()

        if not cleaned:
            return False

        if len(cleaned) < MIN_RUNTIME_TRANSCRIPT_CHARS:
            return False

        word_count = len(cleaned.split())
        if word_count < MIN_RUNTIME_TRANSCRIPT_WORDS:
            return False

        return True

    async def on_user_transcript(self, text: str) -> None:
        if not self.ctx.is_running:
            return

        if not self.ctx.conversation_active:
            return

        cleaned = text.strip()

        if not cleaned:
            logger.info(
                "[Runtime] Empty transcript ignored | session=%s",
                self.ctx.session_id,
            )
            await self.arm_listening()
            return

        if not self._is_transcript_meaningful_runtime(cleaned):
            logger.info(
                "[Runtime] Transcript ignored by runtime min-length filter | session=%s | text_len=%d | preview=%r",
                self.ctx.session_id,
                len(cleaned),
                cleaned[:60].replace("\n", " "),
            )
            await self.arm_listening()
            return

        preview = cleaned[:60].replace("\n", " ")
        self.ctx.last_user_transcript_preview = preview

        logger.info(
            "[Runtime] User transcript received | session=%s | state=%s | text_len=%d | preview=%r",
            self.ctx.session_id,
            self.ctx.state.value,
            len(cleaned),
            preview,
        )

        self.ctx.last_user_activity_time = time.time()

        await self.send_event("user_transcript", {"text": cleaned})

        emotion, confidence, source = self._get_latest_emotion_for_runtime()
        await self._emit_emotion_update(emotion, confidence, source)

        await self.set_state(ConversationState.THINKING)

        result = await asyncio.to_thread(
            self.services.conversation_service.generate_response,
            cleaned,
            emotion,
            self.ctx.language,
            self._conversation_history,
            self.services.tts_service.feed_token,
        )

        if not self.ctx.is_running:
            return

        self._conversation_history.append(self._build_turn("user", cleaned))
        self._conversation_history.append(self._build_turn("assistant", result.response_text))
        self._conversation_history = self._conversation_history[-10:]

        await self.set_state(ConversationState.SPEAKING)

        await self.send_event("ai_response_chunk", {"text": result.response_text})
        await self.send_event("ai_response_done", {"text": result.response_text})

        await self._wait_until_tts_idle()
        await self.arm_listening()

    async def _emit_emotion_update(
        self,
        emotion: str,
        confidence: float,
        source: str,
    ) -> None:
        if not self.ctx.is_running:
            return

        self.ctx.latest_emotion = emotion
        self.ctx.latest_emotion_confidence = confidence
        self.ctx.latest_emotion_source = source

        await self.send_event(
            "emotion_update",
            {
                "emotion": emotion,
                "confidence": confidence,
                "source": source,
            },
        )

    def _get_latest_emotion_for_runtime(self) -> tuple[str, float, str]:
        if self.ctx.latest_emotion and self.ctx.latest_emotion != "unknown":
            return (
                self.ctx.latest_emotion,
                self.ctx.latest_emotion_confidence,
                self.ctx.latest_emotion_source,
            )
        return ("neutral", 0.0, "runtime_fallback")

    def _build_turn(self, role: str, content: str):
        from services.conversation_service import ConversationTurn
        return ConversationTurn(role=role, content=content)

    async def _wait_until_tts_idle(
        self,
        timeout_s: float = 30.0,
        poll_s: float = 0.05,
    ) -> None:
        logger.info(
            "[Runtime] Waiting for TTS idle | session=%s | state=%s | timeout=%.1fs",
            self.ctx.session_id,
            self.ctx.state.value,
            timeout_s,
        )

        start = time.time()
        while time.time() - start < timeout_s:
            if not self.ctx.is_running:
                return

            if not self.services.tts_service.is_busy():
                logger.info(
                    "[Runtime] TTS became idle | session=%s | waited=%.3fs",
                    self.ctx.session_id,
                    time.time() - start,
                )
                return

            await asyncio.sleep(poll_s)

        logger.warning(
            "[Runtime] TTS idle wait timeout | session=%s | state=%s | waited=%.3fs",
            self.ctx.session_id,
            self.ctx.state.value,
            time.time() - start,
        )

    def _should_run_opening(self) -> bool:
        return (
            time.time() - self.ctx.last_opening_time
            >= self.config.opening_cooldown_s
        )