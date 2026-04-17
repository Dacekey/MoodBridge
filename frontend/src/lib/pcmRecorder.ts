// frontend/src/lib/pcmRecorder.ts
type PCMRecorderConfig = {
  targetSampleRate?: number;
  frameDurationMs?: number;
  deviceId?: string;
  onStart?: (meta: {
    inputSampleRate: number;
    targetSampleRate: number;
    frameDurationMs: number;
    frameSamples: number;
  }) => void;
  onFrame: (frameBase64: string) => void;
  onStop?: () => void;
};

function uint8ToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunkSize = 0x8000;

  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }

  return btoa(binary);
}

function downsampleFloat32ToInt16(
  input: Float32Array,
  inputSampleRate: number,
  targetSampleRate: number,
): Int16Array {
  if (targetSampleRate > inputSampleRate) {
    throw new Error("Target sample rate must be <= input sample rate");
  }

  if (targetSampleRate === inputSampleRate) {
    const out = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i]));
      out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return out;
  }

  const ratio = inputSampleRate / targetSampleRate;
  const newLength = Math.floor(input.length / ratio);
  const result = new Int16Array(newLength);

  let offsetResult = 0;
  let offsetBuffer = 0;

  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;

    for (let i = offsetBuffer; i < nextOffsetBuffer && i < input.length; i++) {
      accum += input[i];
      count++;
    }

    const sample = count > 0 ? accum / count : 0;
    const clamped = Math.max(-1, Math.min(1, sample));
    result[offsetResult] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;

    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }

  return result;
}

export class BrowserPCMRecorder {
  private targetSampleRate: number;
  private frameDurationMs: number;
  private deviceId?: string;
  private onStart?: PCMRecorderConfig["onStart"];
  private onFrame: PCMRecorderConfig["onFrame"];
  private onStop?: PCMRecorderConfig["onStop"];

  private stream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private processorNode: ScriptProcessorNode | null = null;

  private pendingSamples: number[] = [];
  private isRunning = false;

  constructor(config: PCMRecorderConfig) {
    this.targetSampleRate = config.targetSampleRate ?? 16000;
    this.frameDurationMs = config.frameDurationMs ?? 20;
    this.deviceId = config.deviceId;
    this.onStart = config.onStart;
    this.onFrame = config.onFrame;
    this.onStop = config.onStop;
  }

  get running(): boolean {
    return this.isRunning;
  }

  async start(): Promise<void> {
    if (this.isRunning) return;

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        deviceId: this.deviceId ? { exact: this.deviceId } : undefined,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    this.audioContext = new AudioContext();
    this.sourceNode = this.audioContext.createMediaStreamSource(this.stream);
    this.processorNode = this.audioContext.createScriptProcessor(4096, 1, 1);

    const inputSampleRate = this.audioContext.sampleRate;
    const frameSamples = Math.floor(
      (this.targetSampleRate * this.frameDurationMs) / 1000,
    );

    this.processorNode.onaudioprocess = (event) => {
      if (!this.isRunning) return;

      const input = event.inputBuffer.getChannelData(0);
      const int16 = downsampleFloat32ToInt16(
        input,
        inputSampleRate,
        this.targetSampleRate,
      );

      for (let i = 0; i < int16.length; i++) {
        this.pendingSamples.push(int16[i]);
      }

      while (this.pendingSamples.length >= frameSamples) {
        const frame = this.pendingSamples.splice(0, frameSamples);
        const frameInt16 = new Int16Array(frame);
        const frameBytes = new Uint8Array(frameInt16.buffer);
        const base64 = uint8ToBase64(frameBytes);
        this.onFrame(base64);
      }
    };

    this.sourceNode.connect(this.processorNode);

    // Không cần route recorder ra loa/tai nghe
    // this.processorNode.connect(this.audioContext.destination);

    this.isRunning = true;

    this.onStart?.({
      inputSampleRate,
      targetSampleRate: this.targetSampleRate,
      frameDurationMs: this.frameDurationMs,
      frameSamples,
    });
  }

  async stop(): Promise<void> {
    if (!this.isRunning) return;

    this.isRunning = false;
    this.pendingSamples = [];

    if (this.processorNode) {
      this.processorNode.disconnect();
      this.processorNode.onaudioprocess = null;
      this.processorNode = null;
    }

    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }

    if (this.audioContext) {
      await this.audioContext.close();
      this.audioContext = null;
    }

    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }

    this.onStop?.();
  }
}