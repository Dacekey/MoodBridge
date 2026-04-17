from __future__ import annotations

import time
from collections import Counter, deque
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = BASE_DIR / "models" / "yolov11s_v1.pt"
DATA_YAML_PATH = BASE_DIR / "models" / "data.yaml"


class EmotionService:
    """
    Emotion detection service for MoodBridge.

    Features:
    - load trained YOLO emotion model
    - predict emotion from a single frame
    - smooth emotion over recent history
    - fallback to last stable emotion when needed
    - aggregate multiple frames and vote for a more stable result
    """

    def __init__(
        self,
        smoothing_window: int = 10,
        conf_threshold: float = 0.5,
        fallback_unknown: str = "unknown",
    ) -> None:
        print("Loading emotion model...")

        self.model = YOLO(MODEL_PATH)

        print("Model loaded")

        self.classes = self.load_classes()

        self.history = deque(maxlen=smoothing_window)
        self.conf_threshold = conf_threshold
        self.fallback_unknown = fallback_unknown

        # Keep the latest valid stable result for fallback
        self.last_stable_emotion: Optional[str] = None
        self.last_stable_confidence: float = 0.0
        self.last_timestamp: Optional[float] = None

    def load_classes(self) -> List[str]:
        with open(DATA_YAML_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        names = data.get("classes", data.get("names"))
        if names is None:
            raise ValueError("data.yaml must contain 'classes' or 'names'")

        if isinstance(names, dict):
            return [names[i] for i in sorted(names.keys())]

        return names

    def smooth_emotion(self, emotion: str) -> str:
        self.history.append(emotion)
        stable = Counter(self.history).most_common(1)[0][0]
        return stable

    def _build_result(
        self,
        raw_emotion: Optional[str],
        stable_emotion: Optional[str],
        confidence: float,
        source: str,
    ) -> Dict[str, Any]:
        return {
            "emotion": stable_emotion or self.fallback_unknown,
            "raw_emotion": raw_emotion,
            "stable_emotion": stable_emotion,
            "confidence": confidence,
            "source": source,
            "timestamp": time.time(),
            "history_size": len(self.history),
        }

    def predict(self, frame) -> Optional[Dict[str, Any]]:
        """
        Predict emotion from a single frame.

        Returns:
            dict with fields:
            - emotion
            - raw_emotion
            - stable_emotion
            - confidence
            - source
            - timestamp
            - history_size

        Return behavior:
        - valid detection above threshold -> update history and return stable result
        - no detection / low confidence -> fallback to last stable if available
        - otherwise return None
        """
        results = self.model(frame, conf=self.conf_threshold, verbose=False)
        result = results[0]

        if result.boxes is None or len(result.boxes) == 0:
            if self.last_stable_emotion is not None:
                return self._build_result(
                    raw_emotion=None,
                    stable_emotion=self.last_stable_emotion,
                    confidence=self.last_stable_confidence,
                    source="fallback_no_detection",
                )
            return None

        confs = result.boxes.conf
        best_idx = int(confs.argmax().item())
        box = result.boxes[best_idx]

        class_id = int(box.cls.item())
        confidence = float(box.conf.item())

        if confidence < self.conf_threshold:
            if self.last_stable_emotion is not None:
                return self._build_result(
                    raw_emotion=None,
                    stable_emotion=self.last_stable_emotion,
                    confidence=self.last_stable_confidence,
                    source="fallback_low_confidence",
                )
            return None

        raw_emotion = self.classes[class_id]
        stable_emotion = self.smooth_emotion(raw_emotion)

        self.last_stable_emotion = stable_emotion
        self.last_stable_confidence = confidence
        self.last_timestamp = time.time()

        return self._build_result(
            raw_emotion=raw_emotion,
            stable_emotion=stable_emotion,
            confidence=confidence,
            source="model",
        )

    def predict_many_frames(
        self,
        frames: List[Any],
        min_valid_votes: int = 2,
    ) -> Dict[str, Any]:
        """
        Predict emotion from multiple frames, then vote.

        Args:
            frames: list of frames
            min_valid_votes: minimum number of valid model detections required
                             before trusting the voted result

        Returns:
            dict with:
            - emotion
            - confidence
            - vote_count
            - total_frames
            - source
            - emotions
            - raw_results
            - timestamp

        Behavior:
        - collect valid per-frame predictions
        - vote on stable_emotion across valid frames
        - average confidence for voted emotion
        - if too few valid detections, fallback to last stable emotion
        - else return unknown
        """
        raw_results: List[Dict[str, Any]] = []
        valid_emotions: List[str] = []
        voted_conf_candidates: List[float] = []

        for frame in frames:
            result = self.predict(frame)
            raw_results.append(result if result is not None else {"emotion": None})

            if result is None:
                continue

            # Only count direct model detections as valid votes
            if result["source"] == "model" and result["emotion"] is not None:
                valid_emotions.append(result["emotion"])

        if len(valid_emotions) >= min_valid_votes:
            voted_emotion, vote_count = Counter(valid_emotions).most_common(1)[0]

            for result in raw_results:
                if (
                    result is not None
                    and result.get("emotion") == voted_emotion
                    and result.get("confidence") is not None
                ):
                    voted_conf_candidates.append(float(result["confidence"]))

            avg_confidence = (
                sum(voted_conf_candidates) / len(voted_conf_candidates)
                if voted_conf_candidates
                else 0.0
            )

            self.last_stable_emotion = voted_emotion
            self.last_stable_confidence = avg_confidence
            self.last_timestamp = time.time()

            return {
                "emotion": voted_emotion,
                "confidence": avg_confidence,
                "vote_count": vote_count,
                "total_frames": len(frames),
                "source": "multi_frame_vote",
                "emotions": valid_emotions,
                "raw_results": raw_results,
                "timestamp": time.time(),
            }

        if self.last_stable_emotion is not None:
            return {
                "emotion": self.last_stable_emotion,
                "confidence": self.last_stable_confidence,
                "vote_count": 0,
                "total_frames": len(frames),
                "source": "fallback_last_stable",
                "emotions": valid_emotions,
                "raw_results": raw_results,
                "timestamp": time.time(),
            }

        return {
            "emotion": self.fallback_unknown,
            "confidence": 0.0,
            "vote_count": 0,
            "total_frames": len(frames),
            "source": "unknown",
            "emotions": valid_emotions,
            "raw_results": raw_results,
            "timestamp": time.time(),
        }

    def predict_from_capture(
        self,
        cap,
        num_frames: int = 5,
        min_valid_votes: int = 2,
    ) -> Dict[str, Any]:
        """
        Read multiple frames from an opened cv2.VideoCapture and vote emotion.
        Useful for demo_conversation.py

        Args:
            cap: cv2.VideoCapture already opened
            num_frames: number of frames to read
            min_valid_votes: minimum valid model detections before trusting vote
        """
        frames: List[Any] = []

        for _ in range(num_frames):
            ret, frame = cap.read()
            if not ret or frame is None:
                continue
            frames.append(frame)

        if not frames:
            if self.last_stable_emotion is not None:
                return {
                    "emotion": self.last_stable_emotion,
                    "confidence": self.last_stable_confidence,
                    "vote_count": 0,
                    "total_frames": 0,
                    "source": "fallback_capture_failed",
                    "emotions": [],
                    "raw_results": [],
                    "timestamp": time.time(),
                }

            return {
                "emotion": self.fallback_unknown,
                "confidence": 0.0,
                "vote_count": 0,
                "total_frames": 0,
                "source": "capture_failed",
                "emotions": [],
                "raw_results": [],
                "timestamp": time.time(),
            }

        return self.predict_many_frames(
            frames=frames,
            min_valid_votes=min_valid_votes,
        )