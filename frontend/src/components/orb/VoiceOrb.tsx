import type { ConversationState } from "../../types/ws";

type VoiceOrbProps = {
  state: ConversationState;
};

type OrbTheme = {
  coreGradient: string;
  ringGradient: string;
  outerGlow: string;
  aura: string;
  pulseScale: number;
  pulseDuration: string;
  spinDurationA: string;
  spinDurationB: string;
  blurStrength: string;
};

function getOrbTheme(state: ConversationState): OrbTheme {
  switch (state) {
    case "READY":
      return {
        coreGradient:
          "radial-gradient(circle at 35% 30%, rgba(125,211,252,0.35), rgba(30,41,59,0.92) 55%, rgba(2,6,23,1) 100%)",
        ringGradient:
          "conic-gradient(from 0deg, rgba(56,189,248,0.0), rgba(56,189,248,0.95), rgba(99,102,241,0.15), rgba(34,211,238,0.95), rgba(56,189,248,0.0))",
        outerGlow: "rgba(56,189,248,0.22)",
        aura: "rgba(34,211,238,0.12)",
        pulseScale: 1.02,
        pulseDuration: "5.5s",
        spinDurationA: "18s",
        spinDurationB: "12s",
        blurStrength: "18px",
      };

    case "ARMED_LISTENING":
      return {
        coreGradient:
          "radial-gradient(circle at 35% 30%, rgba(103,232,249,0.5), rgba(15,23,42,0.92) 52%, rgba(2,6,23,1) 100%)",
        ringGradient:
          "conic-gradient(from 0deg, rgba(34,211,238,0.0), rgba(34,211,238,1), rgba(59,130,246,0.18), rgba(125,211,252,1), rgba(34,211,238,0.0))",
        outerGlow: "rgba(34,211,238,0.26)",
        aura: "rgba(59,130,246,0.14)",
        pulseScale: 1.05,
        pulseDuration: "4.8s",
        spinDurationA: "14s",
        spinDurationB: "9s",
        blurStrength: "20px",
      };

    case "CAPTURING_USER":
      return {
        coreGradient:
          "radial-gradient(circle at 35% 30%, rgba(45,212,191,0.55), rgba(15,23,42,0.9) 50%, rgba(2,6,23,1) 100%)",
        ringGradient:
          "conic-gradient(from 0deg, rgba(16,185,129,0.0), rgba(45,212,191,1), rgba(99,102,241,0.16), rgba(34,197,94,1), rgba(16,185,129,0.0))",
        outerGlow: "rgba(45,212,191,0.28)",
        aura: "rgba(16,185,129,0.16)",
        pulseScale: 1.08,
        pulseDuration: "3.2s",
        spinDurationA: "10s",
        spinDurationB: "7s",
        blurStrength: "22px",
      };

    case "THINKING":
      return {
        coreGradient:
          "radial-gradient(circle at 35% 30%, rgba(168,85,247,0.45), rgba(15,23,42,0.92) 52%, rgba(2,6,23,1) 100%)",
        ringGradient:
          "conic-gradient(from 0deg, rgba(168,85,247,0.0), rgba(168,85,247,1), rgba(34,211,238,0.16), rgba(99,102,241,1), rgba(168,85,247,0.0))",
        outerGlow: "rgba(168,85,247,0.22)",
        aura: "rgba(99,102,241,0.16)",
        pulseScale: 1.06,
        pulseDuration: "2.8s",
        spinDurationA: "6s",
        spinDurationB: "4.5s",
        blurStrength: "22px",
      };

    case "SPEAKING":
      return {
        coreGradient:
          "radial-gradient(circle at 35% 30%, rgba(244,114,182,0.45), rgba(15,23,42,0.9) 48%, rgba(2,6,23,1) 100%)",
        ringGradient:
          "conic-gradient(from 0deg, rgba(244,114,182,0.0), rgba(251,146,60,1), rgba(236,72,153,0.25), rgba(34,211,238,1), rgba(244,114,182,0.0))",
        outerGlow: "rgba(251,146,60,0.24)",
        aura: "rgba(236,72,153,0.18)",
        pulseScale: 1.12,
        pulseDuration: "1.9s",
        spinDurationA: "4.8s",
        spinDurationB: "3.3s",
        blurStrength: "24px",
      };

    case "PAUSED":
      return {
        coreGradient:
          "radial-gradient(circle at 35% 30%, rgba(148,163,184,0.3), rgba(15,23,42,0.94) 55%, rgba(2,6,23,1) 100%)",
        ringGradient:
          "conic-gradient(from 0deg, rgba(148,163,184,0.0), rgba(100,116,139,0.8), rgba(51,65,85,0.16), rgba(148,163,184,0.7), rgba(148,163,184,0.0))",
        outerGlow: "rgba(148,163,184,0.16)",
        aura: "rgba(100,116,139,0.08)",
        pulseScale: 1.01,
        pulseDuration: "6s",
        spinDurationA: "20s",
        spinDurationB: "16s",
        blurStrength: "16px",
      };

    case "ERROR":
      return {
        coreGradient:
          "radial-gradient(circle at 35% 30%, rgba(248,113,113,0.5), rgba(15,23,42,0.92) 50%, rgba(2,6,23,1) 100%)",
        ringGradient:
          "conic-gradient(from 0deg, rgba(248,113,113,0.0), rgba(248,113,113,1), rgba(239,68,68,0.22), rgba(251,146,60,0.95), rgba(248,113,113,0.0))",
        outerGlow: "rgba(248,113,113,0.28)",
        aura: "rgba(239,68,68,0.16)",
        pulseScale: 1.08,
        pulseDuration: "1.2s",
        spinDurationA: "3.8s",
        spinDurationB: "2.6s",
        blurStrength: "24px",
      };

    case "STOPPED":
    default:
      return {
        coreGradient:
          "radial-gradient(circle at 35% 30%, rgba(100,116,139,0.28), rgba(15,23,42,0.94) 55%, rgba(2,6,23,1) 100%)",
        ringGradient:
          "conic-gradient(from 0deg, rgba(71,85,105,0.0), rgba(71,85,105,0.65), rgba(51,65,85,0.14), rgba(100,116,139,0.55), rgba(71,85,105,0.0))",
        outerGlow: "rgba(71,85,105,0.14)",
        aura: "rgba(71,85,105,0.06)",
        pulseScale: 1.01,
        pulseDuration: "7s",
        spinDurationA: "24s",
        spinDurationB: "18s",
        blurStrength: "14px",
      };
  }
}

export default function VoiceOrb({ state }: VoiceOrbProps) {
  const theme = getOrbTheme(state);

  return (
    <div className="flex flex-col items-center justify-center">
      <div className="relative flex items-center justify-center w-[300px] h-[300px]">
        {/* outer aura */}
        <div
          className="absolute inset-0 rounded-full blur-3xl"
          style={{
            background: `radial-gradient(circle, ${theme.aura} 0%, transparent 70%)`,
            animation: `orbBreath ${theme.pulseDuration} ease-in-out infinite`,
          }}
        />

        {/* outer rotating mist */}
        <div
          className="absolute rounded-full opacity-80"
          style={{
            width: 280,
            height: 280,
            background: theme.ringGradient,
            filter: `blur(${theme.blurStrength})`,
            animation: `orbSpinA ${theme.spinDurationA} linear infinite`,
            mixBlendMode: "screen",
          }}
        />

        {/* secondary rotating ring */}
        <div
          className="absolute rounded-full opacity-70"
          style={{
            width: 245,
            height: 245,
            background:
              "conic-gradient(from 180deg, rgba(255,255,255,0.0), rgba(255,255,255,0.6), rgba(255,255,255,0.0), rgba(255,255,255,0.35), rgba(255,255,255,0.0))",
            filter: "blur(10px)",
            animation: `orbSpinB ${theme.spinDurationB} linear infinite reverse`,
            mixBlendMode: "screen",
          }}
        />

        {/* energetic distort ring */}
        <div
          className="absolute rounded-full"
          style={{
            width: 230,
            height: 230,
            background:
              "radial-gradient(circle, transparent 52%, rgba(255,255,255,0.12) 58%, transparent 66%)",
            boxShadow: `0 0 40px ${theme.outerGlow}, inset 0 0 30px rgba(255,255,255,0.08)`,
            animation: `orbBreath ${theme.pulseDuration} ease-in-out infinite`,
          }}
        />

        {/* core */}
        <div
          className="absolute rounded-full"
          style={{
            width: 210,
            height: 210,
            background: theme.coreGradient,
            boxShadow: `
              inset 0 0 40px rgba(255,255,255,0.06),
              0 0 40px ${theme.outerGlow},
              0 0 90px ${theme.outerGlow}
            `,
            animation: `orbCorePulse ${theme.pulseDuration} ease-in-out infinite`,
          }}
        />

        {/* inner highlight */}
        <div
          className="absolute rounded-full opacity-70"
          style={{
            width: 145,
            height: 145,
            background:
              "radial-gradient(circle at 35% 30%, rgba(255,255,255,0.18), rgba(255,255,255,0.04) 35%, transparent 65%)",
            filter: "blur(6px)",
            animation: `orbFloat ${theme.pulseDuration} ease-in-out infinite`,
          }}
        />

        {/* subtle moving arcs */}
        <div
          className="absolute rounded-full"
          style={{
            width: 295,
            height: 295,
            borderRadius: "9999px",
            background:
              "conic-gradient(from 90deg, transparent 0deg, rgba(255,255,255,0.16) 50deg, transparent 95deg, transparent 180deg, rgba(255,255,255,0.08) 235deg, transparent 280deg, transparent 360deg)",
            filter: "blur(8px)",
            animation: `orbSpinA ${theme.spinDurationA} linear infinite`,
            mixBlendMode: "screen",
            opacity: 0.7,
          }}
        />
      </div>

      <div className="mt-5 text-sm text-slate-300">
        State: {state}
      </div>

      <style>
        {`
          @keyframes orbSpinA {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }

          @keyframes orbSpinB {
            from { transform: rotate(0deg) scale(0.98); }
            50% { transform: rotate(180deg) scale(1.02); }
            to { transform: rotate(360deg) scale(0.98); }
          }

          @keyframes orbBreath {
            0% {
              transform: scale(0.95);
              opacity: 0.72;
            }
            50% {
              transform: scale(${theme.pulseScale});
              opacity: 1;
            }
            100% {
              transform: scale(0.95);
              opacity: 0.72;
            }
          }

          @keyframes orbCorePulse {
            0% {
              transform: scale(0.97);
              filter: saturate(0.95) brightness(0.92);
            }
            50% {
              transform: scale(${Math.max(1.01, theme.pulseScale - 0.02)});
              filter: saturate(1.18) brightness(1.08);
            }
            100% {
              transform: scale(0.97);
              filter: saturate(0.95) brightness(0.92);
            }
          }

          @keyframes orbFloat {
            0% {
              transform: translateY(0px) scale(0.98);
              opacity: 0.55;
            }
            50% {
              transform: translateY(-4px) scale(1.03);
              opacity: 0.9;
            }
            100% {
              transform: translateY(0px) scale(0.98);
              opacity: 0.55;
            }
          }
        `}
      </style>
    </div>
  );
}