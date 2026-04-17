import type { ChatMessage } from "../../types/ws";

type ConversationStreamProps = {
  messages: ChatMessage[];
  assistantDraft: string;
  emotion: string;
  confidence: number;
  source: string;
  onClear?: () => void;
};

function roleColor(role: ChatMessage["role"]) {
  switch (role) {
    case "assistant":
      return "text-fuchsia-300";
    case "user":
      return "text-emerald-300";
    case "system":
    default:
      return "text-slate-400";
  }
}

function roleLabel(role: ChatMessage["role"]) {
  switch (role) {
    case "assistant":
      return "moodbridge";
    case "user":
      return "user";
    case "system":
    default:
      return "system";
  }
}

export default function ConversationStream({
  messages,
  assistantDraft,
  emotion,
  confidence,
  source,
  onClear,
}: ConversationStreamProps) {
  return (
    <div className="rounded-3xl border border-slate-700 bg-slate-950/70 p-5 h-full min-h-[720px]">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <div className="text-2xl font-semibold text-white">Conversation</div>
          <div className="mt-2 text-sm text-slate-400">
            emotion: {emotion} &nbsp; confidence: {confidence.toFixed(2)} &nbsp; source: {source}
          </div>
        </div>

        <button
          type="button"
          onClick={onClear}
          className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 transition hover:bg-slate-800"
        >
          Clear
        </button>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-[#091225] px-3 py-3 font-mono text-sm overflow-y-auto max-h-[620px]">
        <div className="space-y-2">
          {messages.length === 0 && !assistantDraft ? (
            <div className="text-slate-500">No conversation yet.</div>
          ) : null}

          {messages.map((msg, idx) => (
            <div
              key={`${msg.role}-${idx}`}
              className="flex gap-3 border-b border-slate-800/80 pb-2 last:border-b-0"
            >
              <span className={`min-w-[78px] uppercase text-xs tracking-wide ${roleColor(msg.role)}`}>
                {roleLabel(msg.role)}
              </span>
              <span className="text-slate-200 leading-relaxed break-words">
                {msg.text}
              </span>
            </div>
          ))}

          {assistantDraft && (
            <div className="flex gap-3 border-b border-slate-800/80 pb-2 last:border-b-0">
              <span className="min-w-[78px] uppercase text-xs tracking-wide text-fuchsia-300">
                moodbridge
              </span>
              <span className="text-slate-200 leading-relaxed break-words">
                {assistantDraft}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}