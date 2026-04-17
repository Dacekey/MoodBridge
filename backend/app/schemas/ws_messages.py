from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


# ---------- Generic envelopes ----------

class WSMessage(BaseModel):
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)


# ---------- Frontend -> Backend ----------

class StartSessionPayload(BaseModel):
    language: Literal["en", "vi"]


class StartSessionMessage(BaseModel):
    type: Literal["start_session"] = "start_session"
    payload: StartSessionPayload


class StopSessionMessage(BaseModel):
    type: Literal["stop_session"] = "stop_session"
    payload: Dict[str, Any] = Field(default_factory=dict)


class PingMessage(BaseModel):
    type: Literal["ping"] = "ping"
    payload: Dict[str, Any] = Field(default_factory=dict)


# ---------- Backend -> Frontend ----------

class SessionStartedPayload(BaseModel):
    session_id: str
    language: Literal["en", "vi"]


class SessionStartedMessage(BaseModel):
    type: Literal["session_started"] = "session_started"
    payload: SessionStartedPayload


class StateUpdatePayload(BaseModel):
    state: str


class StateUpdateMessage(BaseModel):
    type: Literal["state_update"] = "state_update"
    payload: StateUpdatePayload


class EmotionUpdatePayload(BaseModel):
    emotion: str
    confidence: float
    source: str


class EmotionUpdateMessage(BaseModel):
    type: Literal["emotion_update"] = "emotion_update"
    payload: EmotionUpdatePayload


class UserTranscriptPayload(BaseModel):
    text: str


class UserTranscriptMessage(BaseModel):
    type: Literal["user_transcript"] = "user_transcript"
    payload: UserTranscriptPayload


class AIResponseChunkPayload(BaseModel):
    text: str


class AIResponseChunkMessage(BaseModel):
    type: Literal["ai_response_chunk"] = "ai_response_chunk"
    payload: AIResponseChunkPayload


class AIResponseDonePayload(BaseModel):
    text: str


class AIResponseDoneMessage(BaseModel):
    type: Literal["ai_response_done"] = "ai_response_done"
    payload: AIResponseDonePayload


class ErrorPayload(BaseModel):
    message: str


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    payload: ErrorPayload


class SessionStoppedMessage(BaseModel):
    type: Literal["session_stopped"] = "session_stopped"
    payload: Dict[str, Any] = Field(default_factory=dict)


class PongMessage(BaseModel):
    type: Literal["pong"] = "pong"
    payload: Dict[str, Any] = Field(default_factory=dict)