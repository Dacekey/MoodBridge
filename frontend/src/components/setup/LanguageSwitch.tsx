type LanguageSwitchProps = {
  value: "en" | "vi";
  disabled?: boolean;
  onChange: (next: "en" | "vi") => void;
};

export default function LanguageSwitch({
  value,
  disabled = false,
  onChange,
}: LanguageSwitchProps) {
  const isVi = value === "vi";

  return (
    <div className="flex items-center justify-between gap-4">
      <div className="text-sm font-medium text-slate-200 shrink-0">
        Language
      </div>

      <div
        className={`relative w-56 rounded-2xl border border-slate-700 bg-slate-900 p-1 ${
          disabled ? "opacity-60" : ""
        }`}
      >
        <div
          className={`absolute top-1 bottom-1 w-[calc(50%-4px)] rounded-xl bg-indigo-500 transition-transform duration-200 ${
            isVi ? "translate-x-full" : "translate-x-0"
          }`}
        />

        <div className="relative grid grid-cols-2">
          <button
            type="button"
            disabled={disabled}
            onClick={() => onChange("en")}
            className={`z-10 rounded-xl px-4 py-2 text-sm font-medium transition ${
              value === "en" ? "text-white" : "text-slate-300"
            } ${disabled ? "cursor-not-allowed" : ""}`}
          >
            English
          </button>

          <button
            type="button"
            disabled={disabled}
            onClick={() => onChange("vi")}
            className={`z-10 rounded-xl px-4 py-2 text-sm font-medium transition ${
              value === "vi" ? "text-white" : "text-slate-300"
            } ${disabled ? "cursor-not-allowed" : ""}`}
          >
            Tiếng Việt
          </button>
        </div>
      </div>
    </div>
  );
}