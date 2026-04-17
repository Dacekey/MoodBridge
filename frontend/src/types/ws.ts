// frontend/src/types/ws.ts

export type ConversationState =
  | "STOPPED"
  | "READY"
  | "OPENING"
  | "ARMED_LISTENING"
  | "CAPTURING_USER"
  | "THINKING"
  | "SPEAKING"
  | "PAUSED"
  | "ERROR";

export type ConnectionState =
  | "disconnected"
  | "connecting"
  | "connected";

export type ChatRole = "system" | "user" | "assistant";

export type ChatMessage = {
  role: ChatRole;
  text: string;
};

export type StatusPayload = {
  backend_connected?: boolean;
  conversation_active?: boolean;
  tts_busy?: boolean;
  state?: ConversationState;
  language?: "en" | "vi";
};

/**
 * Emotion detection result payload
 */
export type EmotionDetectionResultPayload = {
  emotion?: string;
  confidence?: number;
  source?: string;

  vote_count?: number;
  total_frames?: number;

  emotions?: string[];
};

/**
 * Common payload fallback
 */
export type AnyPayload = Record<string, unknown>;

/**
 * WebSocket message union
 */
export type WSMessage =
  /**
   * Session lifecycle
   */

  | { type: "session_started"; payload?: AnyPayload }
  | { type: "session_stopped"; payload?: AnyPayload }

  /**
   * Conversation lifecycle
   */

  | { type: "conversation_started"; payload?: AnyPayload }
  | { type: "conversation_paused"; payload?: AnyPayload }

  /**
   * State
   */

  | {
      type: "state_update";
      payload?: {
        state?: ConversationState;
      };
    }

  | {
      type: "status_update";
      payload?: StatusPayload;
    }

  /**
   * Emotion updates (continuous / runtime)
   */

  | {
      type: "emotion_update";
      payload?: {
        emotion?: string;
        confidence?: number;
        source?: string;
      };
    }

  /**
   * Emotion detection phase
   */

  | {
      type: "emotion_detection_ready";
      payload?: AnyPayload;
    }

  | {
      type: "emotion_detection_result";
      payload?: EmotionDetectionResultPayload;
    }

  /**
   * Conversation content
   */

  | {
      type: "user_transcript";
      payload?: {
        text?: string;
      };
    }

  | {
      type: "ai_response_chunk";
      payload?: {
        text?: string;
      };
    }

  | {
      type: "ai_response_done";
      payload?: {
        text?: string;
      };
    }

  /**
   * Audio streaming
   */

  | {
      type: "audio_pcm_started";
      payload?: AnyPayload;
    }

  | {
      type: "speech_started";
      payload?: AnyPayload;
    }

  | {
      type: "speech_ended";
      payload?: AnyPayload;
    }

  /**
   * Heartbeat / keepalive
   */

  | {
      type: "ping";
      payload?: AnyPayload;
    }

  | {
      type: "pong";
      payload?: AnyPayload;
    }

  /**
   * Error
   */

  | {
      type: "error";
      payload?: {
        message?: string;
      };
    };