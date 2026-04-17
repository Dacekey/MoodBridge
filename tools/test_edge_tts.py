import asyncio
import edge_tts

TEXT = "Xin chào, tôi đang kiểm tra text to speech."
VOICE = "vi-VN-HoaiMyNeural"

async def main():
    communicate = edge_tts.Communicate(TEXT, voice=VOICE)
    await communicate.save("test_tts.mp3")
    print("Saved test_tts.mp3")

if __name__ == "__main__":
    asyncio.run(main())