# backend/app/state/conversation_state.py
from __future__ import annotations

from enum import Enum


class ConversationState(str, Enum):
    STOPPED = "STOPPED"
    READY = "READY"
    OPENING = "OPENING"
    ARMED_LISTENING = "ARMED_LISTENING"
    CAPTURING_USER = "CAPTURING_USER"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"