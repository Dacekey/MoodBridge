type SystemPanelProps = {
  message: string;
};

export default function SystemPanel({ message }: SystemPanelProps) {
  return (
    <div className="rounded-2xl border border-slate-700 bg-slate-950/70 p-4">
      <div className="mb-3 text-base font-semibold text-white">System</div>

      <div className="rounded-xl border border-slate-800 bg-[#091225] px-4 py-4 font-mono text-sm min-h-[60px] flex items-center">
        <span className="text-slate-200 break-words">
          {message || "System idle"}
        </span>
      </div>
    </div>
  );
}