import cv2
from services.emotion_service import EmotionService


def main() -> None:
    service = EmotionService(
        smoothing_window=10,
        conf_threshold=0.5,
    )

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        raise RuntimeError("Cannot open webcam")

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("Failed to read frame from webcam")
                break

            result = service.predict(frame)

            if result is not None:
                text = (
                    f"{result['emotion']} | "
                    f"conf={result['confidence']:.2f} | "
                    f"source={result['source']}"
                )
                color = (0, 255, 0)
            else:
                text = "No emotion detected"
                color = (0, 0, 255)

            cv2.putText(
                frame,
                text,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                color,
                2,
            )

            cv2.imshow("MoodBridge - Emotion Demo", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()