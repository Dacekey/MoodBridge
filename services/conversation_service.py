# services/conversation_service.py

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


@dataclass
class ConversationTurn:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class ConversationResult:
    response_text: str
    prompt_used: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationService:
    """
    Conversation service for MoodBridge.

    Responsibilities:
    - receive emotion + user text + language
    - build prompt
    - optionally call an LLM
    - return response text

    Supported modes:
    - mock: local fallback, no external API
    - openai_compatible: call an OpenAI-compatible chat endpoint
    """

    SUPPORTED_LANGUAGES = {"en", "vi"}

    def __init__(
        self,
        mode: str = "mock",
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        self.mode = mode
        self.model_name = model_name or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv(
            "LLM_BASE_URL",
            "https://api.openai.com/v1/chat/completions",
        )
        self.timeout = timeout

    def generate_opening_message(
        self,
        detected_emotion: Optional[str] = None,
        language: str = "en",
        tts_callback: Optional[Callable[[str], None]] = None,
    ) -> ConversationResult:
        """
        Generate an opening message so the AI can start the conversation first.
        """
        safe_language = language if language in self.SUPPORTED_LANGUAGES else "en"

        logger.info(
            "[Conversation] generate_opening_message called | language=%s | emotion=%s",
            safe_language,
            detected_emotion or "unknown",
        )

        prompt = self.build_opening_prompt(
            detected_emotion=detected_emotion,
            language=safe_language,
        )

        if self.mode == "openai_compatible":
            response_text = self._call_openai_compatible_opening(
                detected_emotion=detected_emotion,
                language=safe_language,
                tts_callback=tts_callback,
            )
        else:
            logger.info("[Conversation] Using mock opening mode")
            response_text = self._mock_opening_message(
                detected_emotion=detected_emotion,
                language=safe_language,
            )

            if tts_callback is not None:
                try:
                    tts_callback(response_text)
                    self._try_flush_tts_callback(tts_callback)
                except Exception as exc:
                    logger.exception("[TTS] Opening callback failed in mock mode: %s", exc)

        logger.info(
            "[Conversation] Opening generated | mode=%s | response_len=%d",
            self.mode,
            len(response_text),
        )

        return ConversationResult(
            response_text=response_text,
            prompt_used=prompt,
            metadata={
                "mode": self.mode,
                "language": safe_language,
                "emotion": detected_emotion,
                "type": "opening_message",
            },
        )

    def generate_response(
        self,
        user_text: str,
        detected_emotion: Optional[str] = None,
        language: str = "en",
        conversation_history: Optional[List[ConversationTurn]] = None,
        tts_callback: Optional[Callable[[str], None]] = None,
    ) -> ConversationResult:
        """
        Main entry point for normal turns.

        Args:
            user_text: transcription from speech service
            detected_emotion: latest emotion label from emotion service
            language: "en" or "vi"
            conversation_history: short memory of previous turns
            tts_callback: optional callback for streaming TTS tokens/chunks

        Returns:
            ConversationResult
        """
        cleaned_text = (user_text or "").strip()
        safe_language = language if language in self.SUPPORTED_LANGUAGES else "en"
        history = conversation_history or []

        logger.info(
            "[Conversation] generate_response called | language=%s | emotion=%s | text_len=%d | history_len=%d",
            safe_language,
            detected_emotion or "unknown",
            len(cleaned_text),
            len(history),
        )

        prompt = self.build_prompt(
            user_text=cleaned_text,
            detected_emotion=detected_emotion,
            language=safe_language,
            conversation_history=history,
        )

        if not cleaned_text:
            logger.warning("[Conversation] Empty user_text received")
            fallback = self._empty_input_fallback(safe_language)
            return ConversationResult(
                response_text=fallback,
                prompt_used=prompt,
                metadata={
                    "mode": self.mode,
                    "reason": "empty_user_text",
                    "language": safe_language,
                },
            )

        if self.mode == "openai_compatible":
            response_text = self._call_openai_compatible(
                user_text=cleaned_text,
                detected_emotion=detected_emotion,
                language=safe_language,
                conversation_history=history,
                tts_callback=tts_callback,
            )
        else:
            logger.info("[Conversation] Using mock response mode")
            response_text = self._mock_response(
                user_text=cleaned_text,
                detected_emotion=detected_emotion,
                language=safe_language,
            )

            if tts_callback is not None:
                try:
                    tts_callback(response_text)
                    self._try_flush_tts_callback(tts_callback)
                except Exception as exc:
                    logger.exception("[TTS] Callback failed in mock mode: %s", exc)

        logger.info(
            "[Conversation] Response generated | mode=%s | response_len=%d",
            self.mode,
            len(response_text),
        )

        return ConversationResult(
            response_text=response_text,
            prompt_used=prompt,
            metadata={
                "mode": self.mode,
                "language": safe_language,
                "emotion": detected_emotion,
                "history_len": len(history),
                "type": "normal_response",
            },
        )

    def build_opening_prompt(
        self,
        detected_emotion: Optional[str],
        language: str,
    ) -> str:
        emotion_text = detected_emotion if detected_emotion else "unknown"

        if language == "vi":
            return (
                "Bạn là một AI assistant thân thiện và đồng cảm.\n"
                "Hãy chủ động mở đầu cuộc trò chuyện bằng 1-2 câu ngắn.\n"
                "Dựa nhẹ vào tín hiệu cảm xúc, nhưng không được khẳng định chắc chắn.\n"
                "Không đưa ra chẩn đoán tâm lý hay y tế.\n"
                "Kết thúc bằng một câu gợi mở để người dùng trả lời.\n"
                "Giữ câu trả lời dưới 50 từ.\n\n"
                f"Tín hiệu cảm xúc phát hiện được: {emotion_text}\n"
            )

        return (
            "You are a friendly and empathetic AI assistant.\n"
            "Start the conversation proactively in 1-2 short sentences.\n"
            "Use the emotion signal gently, without stating it as certain fact.\n"
            "Do not make medical or psychological claims.\n"
            "End with an inviting question so the user can reply.\n"
            "Keep the response under 50 words.\n\n"
            f"Detected emotion signal: {emotion_text}\n"
        )

    def build_prompt(
        self,
        user_text: str,
        detected_emotion: Optional[str],
        language: str,
        conversation_history: Optional[List[ConversationTurn]] = None,
    ) -> str:
        """
        Build a readable prompt string for logging/debugging.
        """
        history = conversation_history or []
        emotion_text = detected_emotion if detected_emotion else "unknown"

        if language == "vi":
            header = (
                "Bạn là một AI assistant thân thiện, tự nhiên và đồng cảm.\n"
                "Hãy trả lời ngắn gọn, hội thoại, không quá trang trọng.\n"
                "Không được khẳng định chắc chắn cảm xúc của người dùng.\n"
                "Không đưa ra chẩn đoán tâm lý hay y tế.\n"
                "Nếu có dùng cảm xúc, hãy diễn đạt theo hướng gợi ý nhẹ nhàng.\n"
                "Chỉ trả lời trong 1-2 câu.\n"
                "Giữ câu trả lời dưới 50 từ.\n"
            )
        else:
            header = (
                "You are a friendly, natural, empathetic AI assistant.\n"
                "Keep responses short, conversational, and not overly formal.\n"
                "Do not state the user's emotion as certain fact.\n"
                "Do not make mental health or medical claims.\n"
                "If using emotion context, phrase it gently and tentatively.\n"
                "Respond in 1-2 sentences only.\n"
                "Keep responses under 50 words.\n"
            )

        history_block = ""
        if history:
            history_lines = ["Conversation history:"]
            for turn in history[-6:]:
                history_lines.append(f"{turn.role}: {turn.content}")
            history_block = "\n".join(history_lines) + "\n"

        prompt = (
            f"{header}\n"
            f"Detected emotion (uncertain signal): {emotion_text}\n"
            f"Preferred language: {language}\n\n"
            f"{history_block}"
            f"User said:\n{user_text}\n\n"
            f"Respond naturally and empathetically."
        )
        return prompt

    def build_opening_messages(
        self,
        detected_emotion: Optional[str],
        language: str,
    ) -> List[Dict[str, str]]:
        emotion_text = detected_emotion or "unknown"

        if language == "vi":
            system_prompt = (
                "Bạn là một AI assistant thân thiện và đồng cảm.\n"
                "Hãy chủ động bắt đầu cuộc trò chuyện.\n"
                "Trả lời trong 1-2 câu ngắn, tự nhiên.\n"
                "Dựa nhẹ vào tín hiệu cảm xúc, nhưng không được khẳng định chắc chắn.\n"
                "Không đưa ra chẩn đoán y khoa hay tâm lý.\n"
                "Kết thúc bằng một câu gợi mở.\n"
                "Giữ câu trả lời dưới 50 từ.\n"
            )
            user_prompt = (
                f"Tín hiệu cảm xúc phát hiện được (không chắc chắn): {emotion_text}\n"
                "Hãy tạo một câu mở đầu cuộc trò chuyện bằng tiếng Việt."
            )
        else:
            system_prompt = (
                "You are a friendly and empathetic AI assistant.\n"
                "Start the conversation proactively.\n"
                "Reply in 1-2 short, natural sentences.\n"
                "Use the emotion signal gently, without stating it as certain.\n"
                "Do not make medical or psychological diagnoses.\n"
                "End with an inviting question.\n"
                "Keep the response under 50 words.\n"
            )
            user_prompt = (
                f"Detected emotion signal (uncertain): {emotion_text}\n"
                "Create a conversation opening in English."
            )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def build_messages(
        self,
        user_text: str,
        detected_emotion: Optional[str],
        language: str,
        conversation_history: Optional[List[ConversationTurn]] = None,
    ) -> List[Dict[str, str]]:
        """
        Build chat messages for an OpenAI-compatible API.
        """
        history = conversation_history or []

        if language == "vi":
            system_prompt = (
                "Bạn là một AI assistant thân thiện và đồng cảm.\n"
                "Trả lời ngắn gọn, tự nhiên, giống hội thoại thật.\n"
                "Không khẳng định chắc chắn cảm xúc người dùng.\n"
                "Không đưa ra chẩn đoán y khoa hay tâm lý.\n"
                "Chỉ trả lời trong 1-2 câu.\n"
                "Giữ câu trả lời dưới 50 từ.\n"
            )
            user_prompt = (
                f"Tín hiệu cảm xúc phát hiện được (không chắc chắn): "
                f"{detected_emotion or 'unknown'}\n"
                f"Người dùng nói: {user_text}\n"
                "Hãy trả lời tự nhiên và đồng cảm bằng tiếng Việt."
            )
        else:
            system_prompt = (
                "You are a friendly and empathetic AI assistant.\n"
                "Reply briefly and naturally, like real conversation.\n"
                "Do not state the user's emotion as certain.\n"
                "Do not make medical or psychological diagnoses.\n"
                "Respond in 1-2 sentences only.\n"
                "Keep responses under 50 words.\n"
            )
            user_prompt = (
                f"Detected emotion signal (uncertain): "
                f"{detected_emotion or 'unknown'}\n"
                f"User said: {user_text}\n"
                "Respond naturally and empathetically in English."
            )

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

        for turn in history[-6:]:
            if turn.role in {"user", "assistant"}:
                messages.append({"role": turn.role, "content": turn.content})

        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _call_openai_compatible_opening(
        self,
        detected_emotion: Optional[str],
        language: str,
        tts_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        if requests is None:
            raise RuntimeError(
                "The 'requests' package is required for openai_compatible mode."
            )

        if not self.api_key:
            raise RuntimeError(
                "Missing API key. Set LLM_API_KEY or pass api_key explicitly."
            )

        messages = self.build_opening_messages(
            detected_emotion=detected_emotion,
            language=language,
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 60,
            "stream": True,
        }

        request_start = time.perf_counter()

        logger.info("[LLM Opening] Calling API...")
        logger.info("[LLM Opening] model=%s", self.model_name)
        logger.info("[LLM Opening] base_url=%s", self.base_url)

        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            elapsed = time.perf_counter() - request_start
            logger.exception("[LLM Opening] Request failed after %.3fs", elapsed)
            raise RuntimeError(f"LLM opening request failed: {exc}") from exc

        logger.info("[LLM Opening] Response headers received. Streaming started.")

        content = ""
        stream_start = time.perf_counter()
        first_token_time: Optional[float] = None
        token_count = 0

        for line in response.iter_lines():
            if not line:
                continue

            decoded = line.decode("utf-8")

            if decoded.startswith("data: "):
                decoded = decoded[6:]

            if decoded.strip() == "[DONE]":
                break

            try:
                chunk = json.loads(decoded)
                delta = chunk["choices"][0]["delta"]

                if "content" in delta:
                    token = delta["content"]

                    if first_token_time is None:
                        first_token_time = time.perf_counter()
                        logger.info(
                            "[LLM Opening] First token received after %.3fs",
                            first_token_time - request_start,
                        )

                    content += token
                    token_count += 1

                    print(token, end="", flush=True)

                    if tts_callback is not None and token.strip():
                        try:
                            tts_callback(token)
                        except Exception as exc:
                            logger.exception("[TTS] Opening token callback failed: %s", exc)

            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                logger.debug("[LLM Opening] Skipping unparsable stream chunk: %s", decoded)
                continue

        print()

        self._try_flush_tts_callback(tts_callback)

        total_elapsed = time.perf_counter() - request_start
        stream_elapsed = time.perf_counter() - stream_start

        logger.info(
            "[LLM Opening] Streaming finished | total_time=%.3fs | stream_time=%.3fs | token_chunks=%d | response_len=%d",
            total_elapsed,
            stream_elapsed,
            token_count,
            len(content),
        )

        if not content:
            logger.warning("[LLM Opening] Empty content returned, using fallback")
            return self._mock_opening_message(
                detected_emotion=detected_emotion,
                language=language,
            )

        logger.info("[LLM Opening] Response received successfully.")
        return content

    def _call_openai_compatible(
        self,
        user_text: str,
        detected_emotion: Optional[str],
        language: str,
        conversation_history: Optional[List[ConversationTurn]] = None,
        tts_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Call an OpenAI-compatible chat completion endpoint.
        """
        if requests is None:
            raise RuntimeError(
                "The 'requests' package is required for openai_compatible mode."
            )

        if not self.api_key:
            raise RuntimeError(
                "Missing API key. Set LLM_API_KEY or pass api_key explicitly."
            )

        messages = self.build_messages(
            user_text=user_text,
            detected_emotion=detected_emotion,
            language=language,
            conversation_history=conversation_history,
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 60,
            "stream": True,
        }

        request_start = time.perf_counter()

        logger.info("[LLM] Calling API...")
        logger.info("[LLM] model=%s", self.model_name)
        logger.info("[LLM] base_url=%s", self.base_url)

        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            elapsed = time.perf_counter() - request_start
            logger.exception("[LLM] Request failed after %.3fs", elapsed)
            raise RuntimeError(f"LLM request failed: {exc}") from exc

        logger.info("[LLM] Response headers received. Streaming started.")

        content = ""
        stream_start = time.perf_counter()
        first_token_time: Optional[float] = None
        token_count = 0

        for line in response.iter_lines():
            if not line:
                continue

            decoded = line.decode("utf-8")

            if decoded.startswith("data: "):
                decoded = decoded[6:]

            if decoded.strip() == "[DONE]":
                break

            try:
                chunk = json.loads(decoded)
                delta = chunk["choices"][0]["delta"]

                if "content" in delta:
                    token = delta["content"]

                    if first_token_time is None:
                        first_token_time = time.perf_counter()
                        logger.info(
                            "[LLM] First token received after %.3fs",
                            first_token_time - request_start,
                        )

                    content += token
                    token_count += 1

                    print(token, end="", flush=True)

                    if tts_callback is not None and token.strip():
                        try:
                            tts_callback(token)
                        except Exception as exc:
                            logger.exception("[TTS] Token callback failed: %s", exc)

            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                logger.debug("[LLM] Skipping unparsable stream chunk: %s", decoded)
                continue

        print()

        self._try_flush_tts_callback(tts_callback)

        total_elapsed = time.perf_counter() - request_start
        stream_elapsed = time.perf_counter() - stream_start

        logger.info(
            "[LLM] Streaming finished | total_time=%.3fs | stream_time=%.3fs | token_chunks=%d | response_len=%d",
            total_elapsed,
            stream_elapsed,
            token_count,
            len(content),
        )

        if not content:
            logger.warning("[LLM] Empty content returned, using fallback")
            return self._empty_generation_fallback(language)

        logger.info("[LLM] Response received successfully.")
        return content

    def _try_flush_tts_callback(
        self,
        tts_callback: Optional[Callable[[str], None]],
    ) -> None:
        """
        Try to flush buffered TTS text if the callback belongs to an object
        that exposes a .flush() method, e.g. TTSService.feed_token.
        """
        if tts_callback is None:
            return

        try:
            callback_owner = getattr(tts_callback, "__self__", None)
            if callback_owner is None:
                return

            flush_method = getattr(callback_owner, "flush", None)
            if callable(flush_method):
                flush_method()

        except Exception as exc:
            logger.exception("[TTS] Flush callback failed: %s", exc)

    def _mock_opening_message(
        self,
        detected_emotion: Optional[str],
        language: str,
    ) -> str:
        emotion = (detected_emotion or "").lower().strip()

        if language == "vi":
            mapping = {
                "happy": "Có vẻ hôm nay bạn khá vui. Bạn đang thấy thế nào?",
                "sad": "Có vẻ hôm nay bạn hơi trầm xuống. Bạn muốn chia sẻ chút không?",
                "angry": "Có vẻ bạn đang hơi căng. Có chuyện gì đang làm bạn bận tâm sao?",
                "neutral": "Chào bạn. Hôm nay của bạn thế nào?",
                "surprise": "Có vẻ bạn vừa có điều gì đó khá bất ngờ. Bạn muốn kể mình nghe không?",
                "fear": "Có vẻ bạn đang hơi lo. Bạn muốn nói ra thử không?",
                "disgust": "Có vẻ có điều gì đó làm bạn không thoải mái. Chuyện gì vậy?",
            }
            return mapping.get(emotion, "Chào bạn. Hôm nay của bạn thế nào?")

        mapping = {
            "happy": "You seem to be in a pretty good mood today. How are you feeling?",
            "sad": "You seem a little down today. Want to share what’s on your mind?",
            "angry": "You seem a bit tense right now. What’s been bothering you?",
            "neutral": "Hi there. How’s your day going so far?",
            "surprise": "You seem a little surprised by something. Want to tell me about it?",
            "fear": "You seem a bit worried. What’s been on your mind?",
            "disgust": "You seem uncomfortable about something. Want to talk about it?",
        }
        return mapping.get(emotion, "Hi there. How’s your day going so far?")

    def _mock_response(
        self,
        user_text: str,
        detected_emotion: Optional[str],
        language: str,
    ) -> str:
        """
        Local fallback response so the whole pipeline can be tested
        without an external LLM.
        """
        emotion = (detected_emotion or "").lower().strip()
        text = user_text.strip()

        if language == "vi":
            emotion_prefix = {
                "happy": "Có vẻ bạn đang khá vui.",
                "sad": "Nghe như bạn đang hơi chùng xuống.",
                "angry": "Mình cảm nhận cuộc trò chuyện có chút căng thẳng.",
                "neutral": "Mình đang lắng nghe bạn đây.",
                "surprise": "Có vẻ bạn vừa có điều gì đó bất ngờ.",
                "fear": "Nghe như bạn đang hơi lo lắng.",
                "disgust": "Có vẻ bạn đang khá không thoải mái với chuyện này.",
            }.get(emotion, "Mình đang lắng nghe bạn đây.")

            return f"{emotion_prefix} Bạn có thể nói thêm về: “{text}” được không?"
        else:
            emotion_prefix = {
                "happy": "You sound quite upbeat.",
                "sad": "You seem a little down.",
                "angry": "This sounds a bit tense.",
                "neutral": "I'm here and listening.",
                "surprise": "That sounds a little surprising.",
                "fear": "You seem a bit worried.",
                "disgust": "It sounds like this made you uncomfortable.",
            }.get(emotion, "I'm here and listening.")

            return f"{emotion_prefix} Would you like to tell me a bit more about “{text}”?"

    @staticmethod
    def _empty_input_fallback(language: str) -> str:
        if language == "vi":
            return "Mình chưa nghe rõ lắm. Bạn có thể nói lại một lần nữa không?"
        return "I didn't catch that clearly. Could you say it again?"

    @staticmethod
    def _empty_generation_fallback(language: str) -> str:
        if language == "vi":
            return "Mình hiểu rồi. Bạn muốn nói thêm một chút nữa không?"
        return "I understand. Would you like to share a little more?"