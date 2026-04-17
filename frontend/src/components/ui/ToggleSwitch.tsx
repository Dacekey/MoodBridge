// frontend/src/components/ui/ToggleSwitch.tsx
type ToggleSwitchProps = {
  label: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
};

export default function ToggleSwitch({
  label,
  checked,
  disabled = false,
  onChange,
}: ToggleSwitchProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={`w-full flex items-center justify-between rounded-2xl border px-4 py-3 transition ${
        disabled
          ? "opacity-50 cursor-not-allowed border-slate-700 bg-slate-900"
          : "border-slate-700 bg-slate-900 hover:bg-slate-800"
      }`}
    >
      <span className="text-sm font-medium text-slate-200">{label}</span>

      <span
        className={`relative inline-flex h-7 w-12 items-center rounded-full transition ${
          checked ? "bg-emerald-500" : "bg-slate-700"
        }`}
      >
        <span
          className={`inline-block h-5 w-5 transform rounded-full bg-white transition ${
            checked ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </span>
    </button>
  );
}