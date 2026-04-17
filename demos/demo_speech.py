from services.sounddevice_recorder import SoundDeviceRecorder
from services.speech_service import SpeechService

def main():
    print("Starting speech demo...")

    recorder = SoundDeviceRecorder(
        device=2,
        sample_rate=48000,
        frame_duration_ms=30,
        silence_duration_s=1.5,
        max_duration_s=12.0,
        no_speech_timeout_s=10.0,
        pre_speech_buffer_ms=500,
        vad_aggressiveness=3,
        min_speech_frames=3,
        resume_speech_frames=4,
        debug=True,
    )

    speech_service = SpeechService(
        recorder=recorder,
        model_name="small",
        language="vi",
        debug=True,
    )

    try:
        text = speech_service.listen_and_transcribe()
        print()
        print("RESULT:")
        print(text)
    except Exception as e:
        print()
        print("ERROR:")
        print(e)

if __name__ == "__main__":
    main()