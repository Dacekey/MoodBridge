import { useEffect, useRef, useState } from "react";
import VoiceOrb from "../components/orb/VoiceOrb";
import ConversationStream from "../components/conversation/ConversationStream";
import VoiceSessionPanel from "../components/setup/VoiceSessionPanel";
import StatusPanel from "../components/setup/StatusPanel";
import SystemPanel from "../components/setup/SystemPanel";
import CameraPreviewCard from "../components/camera/CameraPreviewCard";
import { BrowserPCMRecorder } from "../lib/pcmRecorder";
import type {
  WSMessage,
  ConversationState,
  ChatMessage,
  ConnectionState,
} from "../types/ws";

const WS_URL = "ws://127.0.0.1:8000/ws/conversation";

const QUIET_OUTBOUND_TYPES = new Set(["audio_pcm_frame", "ping"]);
const QUIET_INBOUND_TYPES = new Set(["pong", "status_update"]);
const QUIET_LABELS = new Set([
  "PCM ensure skipped",
  "PCM stopIfRunning skipped",
  "PCM stop skipped",
  "sendWS skipped",
  "ping skipped",
  "Emotion frame capture skipped",
]);

const EMOTION_DETECTION_SECONDS = 5;
const EMOTION_CAPTURE_INTERVAL_MS = 1000;

type LiveSnapshot = {
  connection: ConnectionState;
  state: ConversationState;
  backendConnected: boolean;
  backendToggleOn: boolean;
  conversationToggleOn: boolean;
};

type AudioInputOption = {
  deviceId: string;
  label: string;
};

export default function ConversationPage() {
  const wsRef = useRef<WebSocket | null>(null);
  const pcmRecorderRef = useRef<BrowserPCMRecorder | null>(null);
  const pingIntervalRef = useRef<number | null>(null);

  const traceIdRef = useRef<string>(crypto.randomUUID());
  const wsSeqRef = useRef(0);
  const lastSentTypeRef = useRef<string>("-");
  const lastReceivedTypeRef = useRef<string>("-");
  const pcmFrameSentCountRef = useRef(0);

  const activeRecorderIdRef = useRef(0);
  const pcmStopInFlightRef = useRef(false);

  const cameraVideoRef = useRef<HTMLVideoElement | null>(null);
  const emotionDetectionInFlightRef = useRef(false);
  const pendingStartConversationRef = useRef(false);
  const conversationBootstrappingRef = useRef(false);

  const liveSnapshotRef = useRef<LiveSnapshot>({
    connection: "disconnected",
    state: "STOPPED",
    backendConnected: false,
    backendToggleOn: false,
    conversationToggleOn: false,
  });

  const [connection, setConnection] = useState<ConnectionState>("disconnected");
  const [state, setState] = useState<ConversationState>("STOPPED");

  const [language, setLanguage] = useState<"en" | "vi">("en");

  const [backendConnected, setBackendConnected] = useState(false);
  const [backendToggleOn, setBackendToggleOn] = useState(false);
  const [conversationToggleOn, setConversationToggleOn] = useState(false);

  const [microphonePermission, setMicrophonePermission] = useState<
    "unknown" | "granted" | "denied"
  >("unknown");
  const [cameraPermission, setCameraPermission] = useState<
    "unknown" | "granted" | "denied"
  >("unknown");

  const [emotion, setEmotion] = useState("unknown");
  const [confidence, setConfidence] = useState(0);
  const [emotionSource, setEmotionSource] = useState("-");

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [assistantDraft, setAssistantDraft] = useState("");
  const [systemMessage, setSystemMessage] = useState("System idle");

  const [audioInputs, setAudioInputs] = useState<AudioInputOption[]>([]);
  const [selectedMicId, setSelectedMicId] = useState<string>("");

  useEffect(() => {
    liveSnapshotRef.current = {
      connection,
      state,
      backendConnected,
      backendToggleOn,
      conversationToggleOn,
    };
  }, [connection, state, backendConnected, backendToggleOn, conversationToggleOn]);

  const appendMessage = (msg: ChatMessage) => {
    setMessages((prev) => [...prev, msg]);
  };

  const setLatestSystemMessage = (text: string) => {
    setSystemMessage(text);
  };

  const debugLog = (
    label: string,
    extra?: Record<string, unknown>,
    options?: { quiet?: boolean },
  ) => {
    if (options?.quiet) return;
    if (QUIET_LABELS.has(label)) return;

    const snapshot = liveSnapshotRef.current;

    console.log(`[ConversationPage][${traceIdRef.current}] ${label}`, {
      ...snapshot,
      pcmRunning: !!pcmRecorderRef.current?.running,
      lastSentType: lastSentTypeRef.current,
      lastReceivedType: lastReceivedTypeRef.current,
      activeRecorderId: activeRecorderIdRef.current,
      pcmStopInFlight: pcmStopInFlightRef.current,
      emotionDetectionInFlight: emotionDetectionInFlightRef.current,
      pendingStartConversation: pendingStartConversationRef.current,
      conversationBootstrapping: conversationBootstrappingRef.current,
      ...extra,
    });
  };

  const sendWS = (type: string, payload: Record<string, unknown> = {}) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      debugLog("sendWS skipped", {
        reason: "socket_not_open",
        type,
        readyState: ws?.readyState,
      });
      return false;
    }

    lastSentTypeRef.current = type;
    wsSeqRef.current += 1;

    if (type === "audio_pcm_frame") {
      pcmFrameSentCountRef.current += 1;
    }

    if (!QUIET_OUTBOUND_TYPES.has(type)) {
      debugLog("sendWS", {
        seq: wsSeqRef.current,
        type,
        payload,
      });
    }

    ws.send(JSON.stringify({ type, payload }));
    return true;
  };

  const clearPingInterval = () => {
    if (pingIntervalRef.current !== null) {
      debugLog("clearPingInterval", { intervalId: pingIntervalRef.current });
      window.clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  };

  const startPingInterval = () => {
    clearPingInterval();

    debugLog("startPingInterval");

    pingIntervalRef.current = window.setInterval(() => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        return;
      }

      lastSentTypeRef.current = "ping";
      wsSeqRef.current += 1;

      ws.send(
        JSON.stringify({
          type: "ping",
          payload: {},
        }),
      );
    }, 15000);
  };

  const loadAudioInputDevices = async (): Promise<AudioInputOption[]> => {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();

      const inputs = devices
        .filter((d) => d.kind === "audioinput")
        .map((d, index) => ({
          deviceId: d.deviceId,
          label: d.label || `Microphone ${index + 1}`,
        }));

      setAudioInputs(inputs);

      setSelectedMicId((prev) => {
        if (prev && inputs.some((d) => d.deviceId === prev)) {
          return prev;
        }

        const next = inputs[0]?.deviceId ?? "";

        debugLog("auto selected microphone", {
          deviceId: next,
          label: inputs.find((d) => d.deviceId === next)?.label,
        });

        return next;
      });

      debugLog("audio input devices loaded", {
        count: inputs.length,
        devices: inputs.map((d) => d.label),
      });

      return inputs;
    } catch (err) {
      debugLog("loadAudioInputDevices failed", {
        error: err instanceof Error ? err.message : String(err),
      });
      return [];
    }
  };

  const startPCMStreaming = async (reason: string) => {
    if (pcmStopInFlightRef.current) {
      debugLog("PCM start skipped", {
        reason,
        why: "stop_in_flight",
      });
      return;
    }

    if (pcmRecorderRef.current?.running) {
      debugLog("PCM start skipped", {
        reason,
        why: "already_running",
      });
      return;
    }

    try {
      debugLog("PCM start requested", { reason });

      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        debugLog("PCM start skipped", {
          reason,
          why: "socket_not_open",
          readyState: ws?.readyState,
        });
        return;
      }

      if (!selectedMicId) {
        debugLog("PCM start skipped", {
          reason,
          why: "selected_mic_not_ready",
          availableMicCount: audioInputs.length,
          availableMicLabels: audioInputs.map((d) => d.label),
        });

        setLatestSystemMessage(
          audioInputs.length > 0
            ? "Please select a microphone before speaking."
            : "Microphone list is not ready yet.",
        );
        return;
      }

      pcmFrameSentCountRef.current = 0;

      const recorderId = activeRecorderIdRef.current + 1;
      activeRecorderIdRef.current = recorderId;

      const selectedMicLabel =
        audioInputs.find((d) => d.deviceId === selectedMicId)?.label ??
        "(not found)";

      debugLog("PCM creating recorder", {
        reason,
        recorderId,
        selectedMicId,
        selectedMicLabel,
        availableMicCount: audioInputs.length,
        availableMicLabels: audioInputs.map((d) => d.label),
      });

      const recorder = new BrowserPCMRecorder({
        targetSampleRate: 16000,
        frameDurationMs: 20,
        deviceId: selectedMicId,
        onStart: ({ targetSampleRate, frameDurationMs }) => {
          if (activeRecorderIdRef.current !== recorderId) {
            debugLog("PCM onStart ignored", {
              reason,
              recorderId,
              why: "stale_recorder",
            });
            return;
          }

          setMicrophonePermission("granted");

          debugLog("PCM onStart", {
            reason,
            recorderId,
            targetSampleRate,
            frameDurationMs,
            selectedMicId,
            selectedMicLabel,
          });

          sendWS("audio_pcm_start", {
            sample_rate: targetSampleRate,
            frame_duration_ms: frameDurationMs,
          });
        },
        onFrame: (frameBase64) => {
          if (activeRecorderIdRef.current !== recorderId) {
            return;
          }

          sendWS("audio_pcm_frame", {
            samples_base64: frameBase64,
          });
        },
        onStop: () => {
          if (activeRecorderIdRef.current !== recorderId) {
            debugLog("PCM onStop ignored", {
              reason,
              recorderId,
              why: "stale_recorder",
              totalFramesSent: pcmFrameSentCountRef.current,
            });
            return;
          }

          debugLog("PCM onStop", {
            reason,
            recorderId,
            totalFramesSent: pcmFrameSentCountRef.current,
          });

          sendWS("audio_pcm_end", {});
        },
      });

      pcmRecorderRef.current = recorder;
      await recorder.start();

      if (activeRecorderIdRef.current !== recorderId) {
        debugLog("PCM started but recorder already stale", {
          reason,
          recorderId,
        });
        return;
      }

      debugLog("PCM started", {
        reason,
        recorderId,
        selectedMicId,
        selectedMicLabel,
      });
    } catch (err) {
      debugLog("PCM start failed", {
        reason,
        error: err instanceof Error ? err.message : String(err),
        selectedMicId,
        selectedMicLabel:
          audioInputs.find((d) => d.deviceId === selectedMicId)?.label ??
          "(not found)",
      });

      console.error(err);
      setMicrophonePermission("denied");
      setLatestSystemMessage("Microphone permission denied or unavailable");
    }
  };

  const stopPCMStreaming = async (reason: string) => {
    const recorder = pcmRecorderRef.current;

    if (!recorder) {
      return;
    }

    if (pcmStopInFlightRef.current) {
      debugLog("PCM stop skipped", {
        reason,
        why: "stop_in_flight",
      });
      return;
    }

    pcmStopInFlightRef.current = true;

    const recorderId = activeRecorderIdRef.current;

    debugLog("PCM stop requested", {
      reason,
      recorderId,
      totalFramesSent: pcmFrameSentCountRef.current,
    });

    pcmRecorderRef.current = null;
    activeRecorderIdRef.current += 1;

    try {
      await recorder.stop();

      debugLog("PCM stopped", {
        reason,
        recorderId,
        totalFramesSent: pcmFrameSentCountRef.current,
      });
    } catch (err) {
      debugLog("PCM stop failed", {
        reason,
        recorderId,
        error: err instanceof Error ? err.message : String(err),
      });
      console.error(err);
    } finally {
      pcmStopInFlightRef.current = false;
    }
  };

  const ensurePCMStreaming = async (reason: string) => {
    if (pcmStopInFlightRef.current) {
      debugLog("PCM ensure skipped", {
        reason,
        why: "stop_in_flight",
      });
      return;
    }

    if (pcmRecorderRef.current?.running) {
      debugLog("PCM ensure skipped", {
        reason,
        why: "already_running",
      });
      return;
    }

    await startPCMStreaming(reason);
  };

  const stopPCMIfRunning = async (reason: string) => {
    if (!pcmRecorderRef.current) {
      debugLog("PCM stopIfRunning skipped", {
        reason,
        why: "not_running",
      });
      return;
    }

    await stopPCMStreaming(reason);
  };

  const captureCameraFrameBase64 = (): string | null => {
    const video = cameraVideoRef.current;

    if (!video) {
      debugLog("Emotion frame capture skipped", { reason: "video_ref_missing" }, { quiet: true });
      return null;
    }

    if (video.readyState < 2) {
      debugLog("Emotion frame capture skipped", { reason: "video_not_ready" }, { quiet: true });
      return null;
    }

    const width = video.videoWidth;
    const height = video.videoHeight;

    if (!width || !height) {
      debugLog("Emotion frame capture skipped", { reason: "video_dimensions_unavailable" }, { quiet: true });
      return null;
    }

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return null;
    }

    ctx.drawImage(video, 0, 0, width, height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    return dataUrl;
  };

  const sleep = (ms: number) =>
    new Promise<void>((resolve) => {
      window.setTimeout(resolve, ms);
    });

  const runEmotionDetectionPhase = async (): Promise<boolean> => {
    if (!backendConnected) {
      debugLog("runEmotionDetectionPhase skipped", {
        reason: "backend_not_connected",
      });
      return false;
    }

    if (cameraPermission === "denied") {
      debugLog("runEmotionDetectionPhase skipped", {
        reason: "camera_permission_denied",
      });
      setLatestSystemMessage("Camera permission denied");
      return false;
    }

    if (emotionDetectionInFlightRef.current) {
      debugLog("runEmotionDetectionPhase skipped", {
        reason: "already_in_flight",
      });
      return false;
    }

    emotionDetectionInFlightRef.current = true;
    setLatestSystemMessage("Detecting emotion...");

    try {
      const started = sendWS("emotion_detection_start", {});
      if (!started) {
        return false;
      }

      for (let i = 0; i < EMOTION_DETECTION_SECONDS; i += 1) {
        const frameBase64 = captureCameraFrameBase64();

        if (frameBase64) {
          sendWS("video_frame", {
            image_base64: frameBase64,
            frame_index: i,
          });

          debugLog("Emotion frame sent", {
            frameIndex: i,
            totalPlanned: EMOTION_DETECTION_SECONDS,
          });
        } else {
          debugLog("Emotion frame missing", {
            frameIndex: i,
          });
        }

        if (i < EMOTION_DETECTION_SECONDS - 1) {
          await sleep(EMOTION_CAPTURE_INTERVAL_MS);
        }
      }

      sendWS("emotion_detection_end", {});
      setLatestSystemMessage("Emotion detection sent, waiting for result...");
      return true;
    } catch (err) {
      debugLog("runEmotionDetectionPhase failed", {
        error: err instanceof Error ? err.message : String(err),
      });
      setLatestSystemMessage("Emotion detection failed");
      return false;
    } finally {
      emotionDetectionInFlightRef.current = false;
    }
  };

  const connectBackend = () => {
    if (connection === "connected" || connection === "connecting") {
      debugLog("connectBackend skipped", {
        reason: "already_connecting_or_connected",
      });
      return;
    }

    debugLog("connectBackend called");

    setConnection("connecting");
    setLatestSystemMessage("Connecting to server...");

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    debugLog("WebSocket created", { url: WS_URL });

    ws.onopen = () => {
      debugLog("WebSocket open");

      setConnection("connected");
      setBackendConnected(true);
      setBackendToggleOn(true);
      setLatestSystemMessage("Server connected");

      startPingInterval();
      sendWS("start_session", { language });
    };

    ws.onmessage = async (event) => {
      try {
        const data: WSMessage = JSON.parse(event.data);

        lastReceivedTypeRef.current = data.type;

        if (!QUIET_INBOUND_TYPES.has(data.type)) {
          debugLog("WebSocket message", {
            type: data.type,
            payload: data.payload,
          });
        }

        switch (data.type) {
          case "session_started": {
            setLatestSystemMessage("Session started");

            loadAudioInputDevices().catch((err) => {
              console.error(err);
              debugLog("session_started loadAudioInputDevices error", {
                error: err instanceof Error ? err.message : String(err),
              });
            });

            break;
          }

          case "session_stopped": {
            pendingStartConversationRef.current = false;
            conversationBootstrappingRef.current = false;
            setState("STOPPED");
            setBackendConnected(false);
            setConversationToggleOn(false);
            await stopPCMIfRunning("session_stopped");
            setLatestSystemMessage("Session stopped");
            break;
          }

          case "conversation_started": {
            conversationBootstrappingRef.current = false;
            setLatestSystemMessage("Conversation started");
            break;
          }

          case "conversation_paused": {
            pendingStartConversationRef.current = false;
            conversationBootstrappingRef.current = false;
            setLatestSystemMessage("Conversation paused");
            await stopPCMIfRunning("conversation_paused");
            break;
          }

          case "state_update": {
            const payload = data.payload ?? {};
            const nextState = payload.state ?? "STOPPED";

            debugLog("state_update received", {
              nextState,
            });

            setState(nextState);

            if (
              nextState === "SPEAKING" ||
              nextState === "OPENING" ||
              nextState === "THINKING" ||
              nextState === "PAUSED" ||
              nextState === "STOPPED" ||
              nextState === "READY" ||
              nextState === "ERROR"
            ) {
              await stopPCMIfRunning(`state_update:${nextState}`);
            } else if (nextState === "ARMED_LISTENING") {
              setLatestSystemMessage("Listening for user input");

              const micReady = await ensureMicrophoneReady();
              if (!micReady) {
                setLatestSystemMessage("No usable microphone found.");
                return;
              }

              setTimeout(() => {
                ensurePCMStreaming("state_update:armed_listening_direct").catch((err) => {
                  console.error(err);
                  debugLog("state_update armed_listening direct start error", {
                    error: err instanceof Error ? err.message : String(err),
                  });
                });
              }, 0);
            }

            if (nextState === "STOPPED" || nextState === "ERROR") {
              pendingStartConversationRef.current = false;
              conversationBootstrappingRef.current = false;
            }

            break;
          }

          case "status_update": {
            const payload = data.payload ?? {};

            if (typeof payload.backend_connected === "boolean") {
              setBackendConnected(payload.backend_connected);
            }
            if (typeof payload.conversation_active === "boolean") {
              setConversationToggleOn(payload.conversation_active);
            }
            if (payload.language === "en" || payload.language === "vi") {
              setLanguage(payload.language);
            }
            if (payload.state) {
              setState(payload.state);
            }

            break;
          }

          case "emotion_update": {
            const payload = data.payload ?? {};

            setEmotion(payload.emotion ?? "unknown");
            setConfidence(Number(payload.confidence ?? 0));
            setEmotionSource(payload.source ?? "-");
            break;
          }

          case "emotion_detection_ready": {
            setLatestSystemMessage("Emotion detection started");
            break;
          }

          case "emotion_detection_result": {
            const payload = data.payload ?? {};

            setEmotion(payload.emotion ?? "unknown");
            setConfidence(Number(payload.confidence ?? 0));
            setEmotionSource(payload.source ?? "-");

            setLatestSystemMessage(
              `Emotion detected: ${payload.emotion ?? "unknown"}`,
            );

            if (pendingStartConversationRef.current) {
              pendingStartConversationRef.current = false;
              sendWS("start_conversation", {});
            }
            break;
          }

          case "user_transcript": {
            const payload = data.payload ?? {};

            appendMessage({
              role: "user",
              text: payload.text ?? "",
            });
            break;
          }

          case "ai_response_chunk": {
            const payload = data.payload ?? {};

            setAssistantDraft((prev) => prev + (payload.text ?? ""));
            break;
          }

          case "ai_response_done": {
            const payload = data.payload ?? {};

            appendMessage({
              role: "assistant",
              text: payload.text ?? "",
            });
            setAssistantDraft("");
            break;
          }

          case "audio_pcm_started": {
            setLatestSystemMessage("Microphone stream ready");
            break;
          }

          case "speech_started": {
            setLatestSystemMessage("Speech detected");
            break;
          }

          case "speech_ended": {
            setLatestSystemMessage("Speech ended");
            break;
          }

          case "pong": {
            break;
          }

          case "ping": {
            break;
          }

          case "error": {
            const payload = data.payload ?? {};
            pendingStartConversationRef.current = false;
            conversationBootstrappingRef.current = false;
            setLatestSystemMessage(`Error: ${payload.message ?? "Unknown error"}`);
            break;
          }

          default: {
            debugLog("Unhandled WebSocket message type", {
              type: lastReceivedTypeRef.current,
            });
            break;
          }
        }
      } catch (err) {
        console.error("WS parse error:", err);
        debugLog("WS parse error", {
          error: err instanceof Error ? err.message : String(err),
        });
      }
    };

    ws.onclose = async (event) => {
      debugLog("WebSocket close", {
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean,
      });

      pendingStartConversationRef.current = false;
      emotionDetectionInFlightRef.current = false;
      conversationBootstrappingRef.current = false;

      clearPingInterval();

      setConnection("disconnected");
      setBackendConnected(false);
      setBackendToggleOn(false);
      setConversationToggleOn(false);
      setState("STOPPED");
      setLatestSystemMessage(
        event.code ? `Server disconnected (${event.code})` : "Server disconnected",
      );

      await stopPCMIfRunning("ws.onclose");
      wsRef.current = null;
    };

    ws.onerror = () => {
      debugLog("WebSocket error");

      pendingStartConversationRef.current = false;
      emotionDetectionInFlightRef.current = false;
      conversationBootstrappingRef.current = false;

      setConnection("disconnected");
      setBackendConnected(false);
      setBackendToggleOn(false);
      setLatestSystemMessage("WebSocket connection error");
    };
  };

  const disconnectBackend = async () => {
    debugLog("disconnectBackend called");

    pendingStartConversationRef.current = false;
    emotionDetectionInFlightRef.current = false;
    conversationBootstrappingRef.current = false;

    try {
      sendWS("stop_session", {});
      await stopPCMIfRunning("disconnectBackend");
      clearPingInterval();
      wsRef.current?.close();
      wsRef.current = null;
    } catch (err) {
      console.error(err);
      debugLog("disconnectBackend error", {
        error: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setConnection("disconnected");
      setBackendConnected(false);
      setBackendToggleOn(false);
      setConversationToggleOn(false);
      setState("STOPPED");
      setLatestSystemMessage("Server disconnected");
    }
  };

  const startConversation = async () => {
    if (!backendConnected) {
      debugLog("startConversation skipped", {
        reason: "backend_not_connected",
      });
      return;
    }

    if (conversationToggleOn) {
      debugLog("startConversation skipped", {
        reason: "already_active",
      });
      return;
    }

    if (emotionDetectionInFlightRef.current) {
      debugLog("startConversation skipped", {
        reason: "emotion_detection_in_flight",
      });
      return;
    }

    if (conversationBootstrappingRef.current) {
      debugLog("startConversation skipped", {
        reason: "bootstrap_in_flight",
      });
      return;
    }

    conversationBootstrappingRef.current = true;

    debugLog("startConversation called");

    pendingStartConversationRef.current = true;
    const detectionStarted = await runEmotionDetectionPhase();

    if (!detectionStarted) {
      pendingStartConversationRef.current = false;
      conversationBootstrappingRef.current = false;
      setLatestSystemMessage("Could not start emotion detection");
    }
  };

  const pauseConversation = async () => {
    debugLog("pauseConversation called");
    pendingStartConversationRef.current = false;
    emotionDetectionInFlightRef.current = false;
    conversationBootstrappingRef.current = false;
    sendWS("pause_conversation", {});
    await stopPCMIfRunning("pauseConversation");
    setConversationToggleOn(false);
    setLatestSystemMessage("Conversation paused");
  };

  const handleToggleBackend = async (next: boolean) => {
    debugLog("handleToggleBackend", { next });

    if (next) {
      connectBackend();
    } else {
      await disconnectBackend();
    }
  };

  const handleToggleConversation = async (next: boolean) => {
    debugLog("handleToggleConversation", { next });

    if (next) {
      const micReady = await ensureMicrophoneReady();
      if (!micReady) {
        setLatestSystemMessage("No usable microphone found.");
        return;
      }

      await startConversation();
    } else {
      await pauseConversation();
    }
  };

  const handleLanguageChange = (next: "en" | "vi") => {
    debugLog("handleLanguageChange", { next });

    setLanguage(next);
    sendWS("set_language", { language: next });
    setLatestSystemMessage(`Language set to ${next.toUpperCase()}`);
  };

  const clearConversation = () => {
    debugLog("clearConversation");

    setMessages([]);
    setAssistantDraft("");
    setLatestSystemMessage("Conversation cleared");
  };

  const ensureMicrophoneReady = async (): Promise<boolean> => {
    try {
      debugLog("ensureMicrophoneReady called");

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: false,
      });

      stream.getTracks().forEach((t) => t.stop());

      setMicrophonePermission("granted");

      const inputs = await loadAudioInputDevices();

      const nextMicId = selectedMicId || inputs[0]?.deviceId || "";

      debugLog("ensureMicrophoneReady done", {
        selectedMicId,
        nextMicId,
        devices: inputs.map((d) => ({
          deviceId: d.deviceId,
          label: d.label,
        })),
      });

      return Boolean(nextMicId);
    } catch (err) {
      debugLog("ensureMicrophoneReady failed", {
        error: err instanceof Error ? err.message : String(err),
      });

      setMicrophonePermission("denied");
      setLatestSystemMessage("Microphone permission denied or unavailable");
      return false;
    }
  };

  const handleVideoRefReady = (videoEl: HTMLVideoElement | null) => {
    cameraVideoRef.current = videoEl;
  };

  useEffect(() => {
    if (!backendConnected) return;

    loadAudioInputDevices().catch((err) => {
      console.error(err);
      debugLog("backendConnected loadAudioInputDevices error", {
        error: err instanceof Error ? err.message : String(err),
      });
    });
  }, [backendConnected]);

  useEffect(() => {
    const handleDeviceChange = () => {
      loadAudioInputDevices().catch((err) => {
        console.error(err);
        debugLog("devicechange reload failed", {
          error: err instanceof Error ? err.message : String(err),
        });
      });
    };

    navigator.mediaDevices?.addEventListener?.("devicechange", handleDeviceChange);

    return () => {
      navigator.mediaDevices?.removeEventListener?.("devicechange", handleDeviceChange);
    };
  }, []);

  useEffect(() => {
    if (microphonePermission !== "granted") {
      return;
    }

    loadAudioInputDevices().catch((err) => {
      console.error(err);
      debugLog("effect loadAudioInputDevices error", {
        error: err instanceof Error ? err.message : String(err),
      });
    });
  }, [microphonePermission]);

  useEffect(() => {
    if (
      state === "ARMED_LISTENING" &&
      selectedMicId &&
      !pcmRecorderRef.current?.running &&
      !pcmStopInFlightRef.current
    ) {
      debugLog("Retry PCM start after mic ready", {
        selectedMicId,
        selectedMicLabel:
          audioInputs.find((d) => d.deviceId === selectedMicId)?.label ??
          "(not found)",
      });

      startPCMStreaming("effect:mic_ready_retry").catch((err) => {
        console.error(err);
        debugLog("effect mic_ready_retry error", {
          error: err instanceof Error ? err.message : String(err),
        });
      });
    }
  }, [selectedMicId, state, audioInputs]);

  useEffect(() => {
    if (conversationToggleOn && backendConnected && state === "ARMED_LISTENING") {
      ensurePCMStreaming("effect:armed_listening").catch((err) => {
        console.error(err);
        debugLog("effect ensurePCMStreaming error", {
          error: err instanceof Error ? err.message : String(err),
        });
      });
    }
  }, [conversationToggleOn, backendConnected, state]);

  useEffect(() => {
    if (
      state === "SPEAKING" ||
      state === "THINKING" ||
      state === "OPENING" ||
      state === "PAUSED" ||
      state === "STOPPED" ||
      state === "READY" ||
      state === "ERROR"
    ) {
      stopPCMIfRunning(`effect:state:${state}`).catch((err) => {
        console.error(err);
        debugLog("effect stopPCMIfRunning error", {
          state,
          error: err instanceof Error ? err.message : String(err),
        });
      });
    }
  }, [state]);

  useEffect(() => {
    const onVisibilityChange = () => {
      debugLog("document visibility changed", {
        visibilityState: document.visibilityState,
      });
    };

    const onOnline = () => debugLog("window online");
    const onOffline = () => debugLog("window offline");

    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);

    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  useEffect(() => {
    return () => {
      debugLog("component unmount cleanup");
      pendingStartConversationRef.current = false;
      emotionDetectionInFlightRef.current = false;
      conversationBootstrappingRef.current = false;
      clearPingInterval();
      stopPCMIfRunning("component_unmount").catch((err) => {
        console.error(err);
        debugLog("component_unmount stopPCMIfRunning error", {
          error: err instanceof Error ? err.message : String(err),
        });
      });
      wsRef.current?.close();
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl p-6 h-[calc(100vh-48px)] grid gap-6 items-stretch lg:grid-cols-[1.05fr_1.1fr_1.6fr]">
        <div className="h-full flex flex-col gap-6">
          <div className="flex-1 rounded-3xl border border-slate-700 bg-slate-950/70 p-6 flex items-center justify-center min-h-0">
            <VoiceOrb state={state} />
          </div>

          <div className="flex-1 min-h-0">
            <VoiceSessionPanel
              backendEnabled={backendToggleOn}
              conversationEnabled={conversationToggleOn}
              language={language}
              backendToggleDisabled={connection === "connecting"}
              conversationToggleDisabled={!backendConnected}
              languageDisabled={false}
              microphoneSelectDisabled={!backendConnected}
              audioInputs={audioInputs}
              selectedMicId={selectedMicId}
              onChangeMicrophone={setSelectedMicId}
              onToggleBackend={handleToggleBackend}
              onToggleConversation={handleToggleConversation}
              onChangeLanguage={handleLanguageChange}
            />
          </div>
        </div>

        <div className="h-full flex flex-col">
          <div className="flex-[1.2] min-h-0 pb-4">
            <CameraPreviewCard
              enabled={backendToggleOn}
              onPermissionChange={setCameraPermission}
              onVideoRefReady={handleVideoRefReady}
            />
          </div>

          <div className="flex-[1.19] min-h-0 py-2">
            <StatusPanel
              microphonePermission={microphonePermission}
              cameraPermission={cameraPermission}
              serverConnected={backendConnected}
              conversationActive={conversationToggleOn}
              state={state}
            />
          </div>

          <div className="flex-[0.55] min-h-0 pt-4">
            <SystemPanel message={systemMessage} />
          </div>
        </div>

        <div className="h-full min-h-0">
          <ConversationStream
            messages={messages}
            assistantDraft={assistantDraft}
            emotion={emotion}
            confidence={confidence}
            source={emotionSource}
            onClear={clearConversation}
          />
        </div>
      </div>
    </div>
  );
}