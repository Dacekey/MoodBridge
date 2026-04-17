from __future__ import annotations

import asyncio
import base64
import json
import logging
from contextlib import suppress
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.runtime.conversation_runtime import ConversationRuntime
from app.runtime.runtime_services import build_runtime_services
from app.runtime.voice_input_controller import VoiceInputController
from app.state.conversation_state import ConversationState

logger = logging.getLogger(__name__)
router = APIRouter()


LOGGABLE_MESSAGE_TYPES = {
    "start_session",
    "stop_session",
    "start_conversation",
    "pause_conversation",
    "set_language",
    "audio_pcm_start",
    "audio_pcm_end",
    "emotion_detection_start",
    "emotion_detection_end",
}

# Minimum transcript guard
MIN_TRANSCRIPT_CHARS = 5
MIN_TRANSCRIPT_WORDS = 2

# Emotion detection defaults
EMOTION_MIN_VALID_VOTES = 2
EMOTION_UNKNOWN_FALLBACK = "neutral"


async def safe_send(websocket: WebSocket, message: dict) -> None:
    try:
        await websocket.send_json(message)
    except Exception as exc:
        logger.warning(
            "[WebSocket] safe_send failed | type=%s | error=%s",
            message.get("type"),
            exc,
        )


async def _transcribe_uploaded_audio(
    runtime: ConversationRuntime,
    audio_path: str,
) -> str:
    services = runtime.services
    stt_service = getattr(services, "stt_service", None)

    if stt_service is None:
        raise RuntimeError("No STT service available")

    if hasattr(stt_service, "transcribe"):
        result = stt_service.transcribe(audio_path)
        return (result or "").strip()

    raise RuntimeError("STT service incompatible")


def _is_transcript_meaningful(text: str) -> bool:
    cleaned = text.strip()

    if not cleaned:
        return False

    if len(cleaned) < MIN_TRANSCRIPT_CHARS:
        return False

    word_count = len(cleaned.split())
    if word_count < MIN_TRANSCRIPT_WORDS:
        return False

    return True


def _decode_video_frame_from_base64(image_base64: str):
    """
    Accept either:
    - raw base64 string
    - data URL like: data:image/jpeg;base64,...
    """
    if not image_base64:
        raise ValueError("Empty image_base64")

    raw = image_base64.strip()

    if "," in raw and raw.startswith("data:"):
        raw = raw.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(raw)
    except Exception as exc:
        raise ValueError(f"Invalid base64 image payload: {exc}") from exc

    np_buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)

    if frame is None:
        raise ValueError("Failed to decode image into frame")

    return frame


def _normalize_emotion_result(result: dict) -> dict:
    """
    Keep demo behavior stable:
    if model returns unknown, fallback to neutral for opening.
    """
    emotion = result.get("emotion", "unknown")
    confidence = float(result.get("confidence", 0.0))
    source = str(result.get("source", "unknown"))

    if emotion == "unknown":
        return {
            **result,
            "emotion": EMOTION_UNKNOWN_FALLBACK,
            "confidence": confidence,
            "source": f"{source}_fallback_to_{EMOTION_UNKNOWN_FALLBACK}",
        }

    return result


async def _publish_emotion_result(
    runtime: ConversationRuntime,
    result: dict,
) -> None:
    normalized = _normalize_emotion_result(result)

    emotion = normalized.get("emotion", EMOTION_UNKNOWN_FALLBACK)
    confidence = float(normalized.get("confidence", 0.0))
    source = str(normalized.get("source", "unknown"))

    runtime.ctx.latest_emotion = emotion
    runtime.ctx.latest_emotion_confidence = confidence
    runtime.ctx.latest_emotion_source = source

    await runtime.send_event(
        "emotion_update",
        {
            "emotion": emotion,
            "confidence": confidence,
            "source": source,
        },
    )

    await runtime.send_event(
        "emotion_detection_result",
        {
            "emotion": emotion,
            "confidence": confidence,
            "source": source,
            "vote_count": int(normalized.get("vote_count", 0)),
            "total_frames": int(normalized.get("total_frames", 0)),
            "emotions": normalized.get("emotions", []),
        },
    )


@router.websocket("/ws/conversation")
async def conversation_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("[WebSocket] Accepted connection")

    runtime: ConversationRuntime | None = None
    runtime_task: asyncio.Task | None = None
    voice_controller: VoiceInputController | None = None

    message_seq = 0
    last_msg_type = "-"
    last_msg_at: float | None = None
    pcm_frame_count = 0

    # Emotion detection session buffer
    emotion_frames: list = []
    emotion_detection_active = False

    try:
        while True:
            raw = await websocket.receive_text()
            message_seq += 1
            last_msg_at = asyncio.get_running_loop().time()

            try:
                message = json.loads(raw)

            except json.JSONDecodeError:
                logger.warning(
                    "[WebSocket] Invalid JSON received | seq=%d | raw_preview=%r",
                    message_seq,
                    raw[:120],
                )
                await safe_send(
                    websocket,
                    {
                        "type": "error",
                        "payload": {
                            "message": "Invalid JSON message",
                        },
                    },
                )
                continue

            msg_type = message.get("type")
            payload = message.get("payload", {})
            last_msg_type = msg_type or "-"

            if msg_type in LOGGABLE_MESSAGE_TYPES:
                logger.info(
                    "[WebSocket] Message received | seq=%d | type=%s | runtime_session=%s | runtime_state=%s | runtime_running=%s",
                    message_seq,
                    msg_type,
                    runtime.ctx.session_id if runtime is not None else "-",
                    runtime.ctx.state.value if runtime is not None else "-",
                    runtime.ctx.is_running if runtime is not None else "-",
                )

            if runtime is not None and not runtime.ctx.is_running:
                logger.info(
                    "[WebSocket] Runtime stopped, exiting handler loop | runtime_session=%s | last_msg_type=%s",
                    runtime.ctx.session_id,
                    last_msg_type,
                )
                break

            # =============================
            # PING
            # =============================

            if msg_type == "ping":
                await safe_send(
                    websocket,
                    {
                        "type": "pong",
                        "payload": {},
                    },
                )
                continue

            # =============================
            # START SESSION
            # =============================

            if msg_type == "start_session":
                language = payload.get("language", "en")

                if runtime is not None:
                    logger.warning(
                        "[WebSocket] start_session ignored, already started | runtime_session=%s",
                        runtime.ctx.session_id,
                    )
                    await safe_send(
                        websocket,
                        {
                            "type": "error",
                            "payload": {
                                "message": "Session already started",
                            },
                        },
                    )
                    continue

                services = build_runtime_services(language=language)

                runtime = ConversationRuntime(
                    websocket=websocket,
                    language=language,
                    services=services,
                )

                voice_controller = VoiceInputController()
                emotion_frames.clear()
                emotion_detection_active = False

                logger.info(
                    "[WebSocket] Session initialized | runtime_session=%s | language=%s",
                    runtime.ctx.session_id,
                    runtime.ctx.language,
                )

                await runtime.start()
                runtime_task = asyncio.create_task(runtime.run_loop())

                logger.info(
                    "[WebSocket] Runtime loop task started | runtime_session=%s",
                    runtime.ctx.session_id,
                )
                continue

            # =============================
            # STOP SESSION
            # =============================

            if msg_type == "stop_session":
                logger.info(
                    "[WebSocket] stop_session requested | runtime_session=%s | state=%s",
                    runtime.ctx.session_id if runtime else "-",
                    runtime.ctx.state.value if runtime else "-",
                )

                if runtime is not None:
                    await runtime.stop()

                if runtime_task is not None:
                    runtime_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await runtime_task

                runtime = None
                runtime_task = None
                voice_controller = None
                emotion_frames.clear()
                emotion_detection_active = False

                logger.info("[WebSocket] Session resources cleared after stop_session")
                continue

            # =============================
            # SESSION NOT STARTED
            # =============================

            if runtime is None:
                logger.warning(
                    "[WebSocket] Message rejected, session not started | seq=%d | type=%s",
                    message_seq,
                    msg_type,
                )
                await safe_send(
                    websocket,
                    {
                        "type": "error",
                        "payload": {
                            "message": "Session not started",
                        },
                    },
                )
                continue

            # =============================
            # EMOTION DETECTION START
            # =============================

            if msg_type == "emotion_detection_start":
                emotion_frames.clear()
                emotion_detection_active = True

                logger.info(
                    "[Emotion] Detection started | runtime_session=%s | state=%s",
                    runtime.ctx.session_id,
                    runtime.ctx.state.value,
                )

                await safe_send(
                    websocket,
                    {
                        "type": "emotion_detection_ready",
                        "payload": {},
                    },
                )
                continue

            # =============================
            # VIDEO FRAME
            # =============================

            if msg_type == "video_frame":
                if not emotion_detection_active:
                    logger.debug(
                        "[Emotion] video_frame ignored because detection is not active | runtime_session=%s",
                        runtime.ctx.session_id,
                    )
                    continue

                image_base64 = (
                    payload.get("image_base64")
                    or payload.get("image")
                    or payload.get("data_url")
                    or ""
                )

                if not image_base64:
                    logger.debug(
                        "[Emotion] Empty video_frame payload ignored | runtime_session=%s",
                        runtime.ctx.session_id,
                    )
                    continue

                try:
                    frame = _decode_video_frame_from_base64(image_base64)
                    emotion_frames.append(frame)

                    logger.info(
                        "[Emotion] Frame received | runtime_session=%s | total_frames=%d | shape=%s",
                        runtime.ctx.session_id,
                        len(emotion_frames),
                        getattr(frame, "shape", None),
                    )
                except Exception as exc:
                    logger.warning(
                        "[Emotion] Failed to decode video frame | runtime_session=%s | error=%s",
                        runtime.ctx.session_id,
                        exc,
                    )

                continue

            # =============================
            # EMOTION DETECTION END
            # =============================

            if msg_type == "emotion_detection_end":
                if not emotion_detection_active:
                    logger.info(
                        "[Emotion] emotion_detection_end ignored because detection is not active | runtime_session=%s",
                        runtime.ctx.session_id,
                    )
                    await safe_send(
                        websocket,
                        {
                            "type": "emotion_detection_result",
                            "payload": {
                                "emotion": runtime.ctx.latest_emotion or EMOTION_UNKNOWN_FALLBACK,
                                "confidence": runtime.ctx.latest_emotion_confidence,
                                "source": "ignored_not_active",
                                "vote_count": 0,
                                "total_frames": 0,
                                "emotions": [],
                            },
                        },
                    )
                    continue

                emotion_detection_active = False

                logger.info(
                    "[Emotion] Detection ending | runtime_session=%s | collected_frames=%d",
                    runtime.ctx.session_id,
                    len(emotion_frames),
                )

                try:
                    emotion_service = runtime.services.emotion_service

                    result = await asyncio.to_thread(
                        emotion_service.predict_many_frames,
                        emotion_frames.copy(),
                        EMOTION_MIN_VALID_VOTES,
                    )

                    logger.info(
                        "[Emotion] Detection result | runtime_session=%s | emotion=%s | confidence=%.3f | source=%s | vote_count=%s | total_frames=%s",
                        runtime.ctx.session_id,
                        result.get("emotion"),
                        float(result.get("confidence", 0.0)),
                        result.get("source"),
                        result.get("vote_count"),
                        result.get("total_frames"),
                    )

                    await _publish_emotion_result(runtime, result)

                except Exception as exc:
                    logger.exception(
                        "[Emotion] Detection failed | runtime_session=%s | error=%s",
                        runtime.ctx.session_id,
                        exc,
                    )

                    fallback_result = {
                        "emotion": runtime.ctx.latest_emotion or EMOTION_UNKNOWN_FALLBACK,
                        "confidence": runtime.ctx.latest_emotion_confidence,
                        "source": "emotion_detection_error",
                        "vote_count": 0,
                        "total_frames": len(emotion_frames),
                        "emotions": [],
                    }
                    await _publish_emotion_result(runtime, fallback_result)

                finally:
                    emotion_frames.clear()

                continue

            # =============================
            # CONVERSATION CONTROL
            # =============================

            if msg_type == "start_conversation":
                logger.info(
                    "[WebSocket] start_conversation requested | runtime_session=%s | state=%s | latest_emotion=%s | emotion_conf=%.3f | emotion_source=%s",
                    runtime.ctx.session_id,
                    runtime.ctx.state.value,
                    runtime.ctx.latest_emotion,
                    runtime.ctx.latest_emotion_confidence,
                    runtime.ctx.latest_emotion_source,
                )
                await runtime.start_conversation()
                continue

            if msg_type == "pause_conversation":
                logger.info(
                    "[WebSocket] pause_conversation requested | runtime_session=%s | state=%s",
                    runtime.ctx.session_id,
                    runtime.ctx.state.value,
                )
                await runtime.pause_conversation()
                continue

            # =============================
            # LANGUAGE
            # =============================

            if msg_type == "set_language":
                language = payload.get("language", "en")

                if language in {"en", "vi"}:
                    old_language = runtime.ctx.language
                    runtime.ctx.language = language

                    logger.info(
                        "[WebSocket] Language updated | runtime_session=%s | %s -> %s",
                        runtime.ctx.session_id,
                        old_language,
                        runtime.ctx.language,
                    )

                    await runtime.emit_status()
                else:
                    logger.warning(
                        "[WebSocket] Invalid language ignored | runtime_session=%s | language=%r",
                        runtime.ctx.session_id,
                        language,
                    )

                continue

            # =============================
            # PCM START
            # =============================

            if msg_type == "audio_pcm_start":
                if voice_controller is None:
                    logger.warning(
                        "[PCM] audio_pcm_start ignored, voice controller not ready | runtime_session=%s",
                        runtime.ctx.session_id if runtime else "-",
                    )
                    await safe_send(
                        websocket,
                        {
                            "type": "error",
                            "payload": {
                                "message": "Voice controller not ready",
                            },
                        },
                    )
                    continue

                sample_rate = int(payload.get("sample_rate", 16000))
                frame_duration_ms = int(payload.get("frame_duration_ms", 20))

                voice_controller.configure_stream(
                    sample_rate=sample_rate,
                    frame_duration_ms=frame_duration_ms,
                )

                pcm_frame_count = 0

                logger.info(
                    "[PCM] Stream started | runtime_session=%s | state=%s | sample_rate=%d | frame_duration_ms=%d",
                    runtime.ctx.session_id,
                    runtime.ctx.state.value,
                    sample_rate,
                    frame_duration_ms,
                )

                await safe_send(
                    websocket,
                    {
                        "type": "audio_pcm_started",
                        "payload": {
                            "sample_rate": sample_rate,
                            "frame_duration_ms": frame_duration_ms,
                        },
                    },
                )
                continue

            # =============================
            # PCM FRAME
            # =============================

            if msg_type == "audio_pcm_frame":
                if voice_controller is None:
                    continue

                if runtime.ctx.state not in {
                    ConversationState.ARMED_LISTENING,
                    ConversationState.CAPTURING_USER,
                }:
                    continue

                samples_base64 = payload.get("samples_base64", "")
                if not samples_base64:
                    continue

                try:
                    frame_bytes = voice_controller.decode_base64_frame(samples_base64)
                except Exception as exc:
                    logger.warning(
                        "[PCM] Failed to decode frame | runtime_session=%s | error=%s",
                        runtime.ctx.session_id,
                        exc,
                    )
                    continue

                pcm_frame_count += 1

                was_in_speech = voice_controller.in_speech
                completed_frames = voice_controller.ingest_frame(frame_bytes)

                if not was_in_speech and voice_controller.in_speech:
                    logger.info(
                        "[PCM] Speech started | runtime_session=%s | state=%s | frame_count=%d",
                        runtime.ctx.session_id,
                        runtime.ctx.state.value,
                        pcm_frame_count,
                    )

                    await runtime.mark_speech_started()

                    await safe_send(
                        websocket,
                        {
                            "type": "speech_started",
                            "payload": {},
                        },
                    )

                if completed_frames is not None:
                    logger.info(
                        "[PCM] Speech completed | runtime_session=%s | state=%s | frames=%d | total_pcm_frames=%d",
                        runtime.ctx.session_id,
                        runtime.ctx.state.value,
                        len(completed_frames),
                        pcm_frame_count,
                    )

                    await runtime.mark_speech_ended()

                    await safe_send(
                        websocket,
                        {
                            "type": "speech_ended",
                            "payload": {},
                        },
                    )

                    temp_path: Path | None = None

                    try:
                        temp_path = voice_controller.save_wav(completed_frames)

                        logger.info(
                            "[PCM] WAV saved for STT | runtime_session=%s | path=%s",
                            runtime.ctx.session_id,
                            temp_path,
                        )

                        transcript = await _transcribe_uploaded_audio(
                            runtime,
                            str(temp_path),
                        )

                        logger.info(
                            "[PCM] Transcript ready | runtime_session=%s | text_len=%d | preview=%r",
                            runtime.ctx.session_id,
                            len(transcript),
                            transcript[:60].replace("\n", " "),
                        )

                        if _is_transcript_meaningful(transcript):
                            await runtime.on_user_transcript(transcript)
                        else:
                            logger.info(
                                "[PCM] Transcript ignored by min-length filter | runtime_session=%s | text_len=%d | preview=%r",
                                runtime.ctx.session_id,
                                len(transcript),
                                transcript[:60].replace("\n", " "),
                            )
                            await runtime.arm_listening()

                    except Exception as exc:
                        logger.warning(
                            "[PCM] Utterance ignored | runtime_session=%s | error=%s",
                            runtime.ctx.session_id,
                            exc,
                        )
                        await runtime.arm_listening()

                    finally:
                        if temp_path is not None:
                            with suppress(Exception):
                                temp_path.unlink()

                continue

            # =============================
            # PCM END
            # =============================

            if msg_type == "audio_pcm_end":
                if voice_controller is None:
                    continue

                completed_frames = voice_controller.flush_if_needed()

                if completed_frames:
                    logger.info(
                        "[PCM] Flush produced completed frames | runtime_session=%s | frames=%d | total_pcm_frames=%d",
                        runtime.ctx.session_id,
                        len(completed_frames),
                        pcm_frame_count,
                    )

                    await runtime.mark_speech_ended()

                    temp_path: Path | None = None

                    try:
                        temp_path = voice_controller.save_wav(completed_frames)

                        transcript = await _transcribe_uploaded_audio(
                            runtime,
                            str(temp_path),
                        )

                        logger.info(
                            "[PCM] Flush transcript ready | runtime_session=%s | text_len=%d | preview=%r",
                            runtime.ctx.session_id,
                            len(transcript),
                            transcript[:60].replace("\n", " "),
                        )

                        if _is_transcript_meaningful(transcript):
                            await runtime.on_user_transcript(transcript)
                        else:
                            logger.info(
                                "[PCM] Flush transcript ignored by min-length filter | runtime_session=%s | text_len=%d | preview=%r",
                                runtime.ctx.session_id,
                                len(transcript),
                                transcript[:60].replace("\n", " "),
                            )
                            await runtime.arm_listening()

                    except Exception as exc:
                        logger.warning(
                            "[PCM] Flush utterance ignored | runtime_session=%s | error=%s",
                            runtime.ctx.session_id,
                            exc,
                        )
                        await runtime.arm_listening()

                    finally:
                        if temp_path is not None:
                            with suppress(Exception):
                                temp_path.unlink()

                logger.info(
                    "[PCM] Stream ended | runtime_session=%s | state=%s | flushed=%s | total_pcm_frames=%d",
                    runtime.ctx.session_id if runtime else "-",
                    runtime.ctx.state.value if runtime else "-",
                    bool(completed_frames),
                    pcm_frame_count,
                )
                continue

            # =============================
            # UNKNOWN EVENT
            # =============================

            logger.warning(
                "[WebSocket] Unsupported event received | runtime_session=%s | type=%s",
                runtime.ctx.session_id if runtime else "-",
                msg_type,
            )

            await safe_send(
                websocket,
                {
                    "type": "error",
                    "payload": {
                        "message": f"Unsupported event: {msg_type}",
                    },
                },
            )

    except WebSocketDisconnect:
        logger.info(
            "[WebSocket] Client disconnected | last_msg_type=%s | last_msg_at=%s | runtime_session=%s | runtime_state=%s | runtime_running=%s",
            last_msg_type,
            last_msg_at,
            runtime.ctx.session_id if runtime else "-",
            runtime.ctx.state.value if runtime else "-",
            runtime.ctx.is_running if runtime else "-",
        )

    except RuntimeError as exc:
        logger.warning(
            "[WebSocket] RuntimeError in handler | error=%s | last_msg_type=%s | runtime_session=%s | runtime_state=%s",
            exc,
            last_msg_type,
            runtime.ctx.session_id if runtime else "-",
            runtime.ctx.state.value if runtime else "-",
        )

    except Exception as exc:
        logger.exception(
            "[WebSocket] Unexpected error | error=%s | last_msg_type=%s | runtime_session=%s | runtime_state=%s",
            exc,
            last_msg_type,
            runtime.ctx.session_id if runtime else "-",
            runtime.ctx.state.value if runtime else "-",
        )

    finally:
        logger.info(
            "[WebSocket] Cleaning up session | last_msg_type=%s | runtime_session=%s | runtime_state=%s",
            last_msg_type,
            runtime.ctx.session_id if runtime else "-",
            runtime.ctx.state.value if runtime else "-",
        )

        emotion_frames.clear()
        emotion_detection_active = False

        if runtime is not None:
            with suppress(Exception):
                await runtime.stop()

        if runtime_task is not None:
            runtime_task.cancel()
            with suppress(asyncio.CancelledError):
                await runtime_task