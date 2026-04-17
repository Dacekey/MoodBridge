import ToggleSwitch from "../ui/ToggleSwitch";
import LanguageSwitch from "./LanguageSwitch";

type AudioInputOption = {
  deviceId: string;
  label: string;
};

type VoiceSessionPanelProps = {
  backendEnabled: boolean;
  conversationEnabled: boolean;
  language: "en" | "vi";

  backendToggleDisabled?: boolean;
  conversationToggleDisabled?: boolean;
  languageDisabled?: boolean;
  microphoneSelectDisabled?: boolean;

  audioInputs?: AudioInputOption[];
  selectedMicId?: string;
  onChangeMicrophone?: (deviceId: string) => void;

  onToggleBackend: (next: boolean) => void;
  onToggleConversation: (next: boolean) => void;
  onChangeLanguage: (next: "en" | "vi") => void;
};

export default function VoiceSessionPanel({
  backendEnabled,
  conversationEnabled,
  language,
  backendToggleDisabled = false,
  conversationToggleDisabled = false,
  languageDisabled = false,
  microphoneSelectDisabled = false,
  audioInputs = [],
  selectedMicId = "",
  onChangeMicrophone,
  onToggleBackend,
  onToggleConversation,
  onChangeLanguage,
}: VoiceSessionPanelProps) {
  const hasMicrophones = audioInputs.length > 0;

  return (
    <div className="rounded-3xl border border-slate-700 bg-slate-950/70 p-4 space-y-4">
      <div>
        <div className="text-xl font-semibold text-white">Control Board</div>
        <div className="mt-1 text-sm text-slate-400">
          {/* Setup MoodBridge Here! */}
        </div>
      </div>

      <ToggleSwitch
        label="Backend"
        checked={backendEnabled}
        disabled={backendToggleDisabled}
        onChange={onToggleBackend}
      />

      <ToggleSwitch
        label="Conversation"
        checked={conversationEnabled}
        disabled={conversationToggleDisabled}
        onChange={onToggleConversation}
      />

      <div className="space-y-2">
        <div className="text-sm font-medium text-slate-200">Microphone</div>

        <select
          value={selectedMicId}
          disabled={microphoneSelectDisabled || !hasMicrophones}
          onChange={(e) => onChangeMicrophone?.(e.target.value)}
          className="w-full rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none transition focus:border-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {hasMicrophones ? (
            audioInputs.map((mic) => (
              <option key={mic.deviceId} value={mic.deviceId}>
                {mic.label}
              </option>
            ))
          ) : (
            <option value="">No microphone detected</option>
          )}
        </select>

        <div className="text-xs text-slate-400">
          {/* Select the microphone input you want MoodBridge to use. */}
        </div>
      </div>

      <LanguageSwitch
        value={language}
        disabled={languageDisabled}
        onChange={onChangeLanguage}
      />
    </div>
  );
}