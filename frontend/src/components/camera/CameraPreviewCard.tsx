import { useEffect, useRef, useState } from "react";

type CameraPreviewCardProps = {
  enabled: boolean;
  onPermissionChange?: (status: "unknown" | "granted" | "denied") => void;
  onVideoRefReady?: (video: HTMLVideoElement | null) => void;
};

export default function CameraPreviewCard({
  enabled,
  onPermissionChange,
  onVideoRefReady,
}: CameraPreviewCardProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const onPermissionChangeRef = useRef(onPermissionChange);
  const onVideoRefReadyRef = useRef(onVideoRefReady);

  const [localEnabled, setLocalEnabled] = useState(false);

  useEffect(() => {
    onPermissionChangeRef.current = onPermissionChange;
  }, [onPermissionChange]);

  useEffect(() => {
    onVideoRefReadyRef.current = onVideoRefReady;
  }, [onVideoRefReady]);

  useEffect(() => {
    let cancelled = false;

    async function startCamera() {
      try {
        onPermissionChangeRef.current?.("unknown");

        const stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        });

        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        streamRef.current = stream;

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          onVideoRefReadyRef.current?.(videoRef.current);
        }

        setLocalEnabled(true);
        onPermissionChangeRef.current?.("granted");
      } catch {
        setLocalEnabled(false);
        onPermissionChangeRef.current?.("denied");
        onVideoRefReadyRef.current?.(null);
      }
    }

    function stopCamera() {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }

      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }

      onVideoRefReadyRef.current?.(null);
      setLocalEnabled(false);
    }

    if (enabled) {
      startCamera();
    } else {
      stopCamera();
    }

    return () => {
      cancelled = true;
      stopCamera();
    };
  }, [enabled]);

  return (
    <div className="rounded-3xl border border-slate-700 bg-slate-950/70 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-base font-semibold text-white">Camera Preview</div>
          <div className="text-sm text-slate-400">
            Preview source for YOLO emotion detection
          </div>
        </div>

        <span
          className={`rounded-full px-3 py-1 text-xs ${
            localEnabled
              ? "bg-emerald-500/20 text-emerald-300"
              : "bg-slate-800 text-slate-300"
          }`}
        >
          {localEnabled ? "camera on" : "camera off"}
        </span>
      </div>

      <div className="relative aspect-video overflow-hidden rounded-3xl border border-slate-800 bg-slate-900">
        {enabled ? (
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-sm text-slate-500">
            Camera preview disabled
          </div>
        )}

        <div className="pointer-events-none absolute inset-0 border-2 border-dashed border-indigo-400/20" />

        <div className="absolute left-3 top-3 rounded-xl bg-slate-950/70 px-3 py-2 text-xs text-slate-200">
          YOLO: camera ready
        </div>

        <div className="absolute right-3 bottom-3 rounded-xl bg-slate-950/70 px-3 py-2 text-xs text-slate-200">
          Frames available for backend detection
        </div>
      </div>
    </div>
  );
}