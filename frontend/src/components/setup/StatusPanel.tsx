import type { ConversationState } from "../../types/ws";

type StatusPanelProps = {
  microphonePermission: "unknown" | "granted" | "denied";
  cameraPermission: "unknown" | "granted" | "denied";
  serverConnected: boolean;
  conversationActive: boolean;
  state: ConversationState;
};

function dotClass(kind: "green" | "red" | "gray") {
  switch (kind) {
    case "green":
      return "bg-emerald-500";
    case "red":
      return "bg-rose-500";
    case "gray":
    default:
      return "bg-slate-500";
  }
}

function StatusRow({
  label,
  value,
  kind,
}: {
  label: string;
  value: string;
  kind: "green" | "red" | "gray";
}) {
  return (
    <div className="flex items-center justify-between rounded-xl bg-slate-900 px-3 py-2">
      <span className="text-sm text-slate-300">{label}</span>
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${dotClass(kind)}`} />
        <span className="text-sm text-slate-100">{value}</span>
      </div>
    </div>
  );
}

export default function StatusPanel({
  microphonePermission,
  cameraPermission,
  serverConnected,
  conversationActive,
  state,
}: StatusPanelProps) {
  const microphoneKind =
    microphonePermission === "granted"
      ? "green"
      : microphonePermission === "denied"
        ? "red"
        : "gray";

  const cameraKind =
    cameraPermission === "granted"
      ? "green"
      : cameraPermission === "denied"
        ? "red"
        : "gray";

  return (
    <div className="rounded-2xl border border-slate-700 bg-slate-950/70 p-4">
      <div className="mb-3 text-base font-semibold text-white">Status</div>

      <div className="space-y-2">
        <StatusRow
          label="Microphone"
          value={microphonePermission}
          kind={microphoneKind}
        />

        <StatusRow
          label="Camera"
          value={cameraPermission}
          kind={cameraKind}
        />

        <StatusRow
          label="Server"
          value={serverConnected ? "connected" : "disconnected"}
          kind={serverConnected ? "green" : "red"}
        />

        <StatusRow
          label="Conversation"
          value={conversationActive ? "active" : "paused"}
          kind={conversationActive ? "green" : "red"}
        />

        <StatusRow
          label="State"
          value={state}
          kind={state === "STOPPED" || state === "ERROR" ? "red" : "green"}
        />
      </div>
    </div>
  );
}