from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

try:
    from .compat import logger
except Exception:
    class _FallbackLogger:
        def warning(self, message):
            print(message)

    logger = _FallbackLogger()

if TYPE_CHECKING:
    from .config import MonitorConfig
    from .models import ChapterDetail, NovelLatest


class CommentGenerator:
    def __init__(self, context: Any, config: "MonitorConfig"):
        self.context = context
        self.config = config

    async def generate(self, latest: "NovelLatest", chapter: "ChapterDetail") -> str:
        if not getattr(self.config, "enable_llm_comment", True):
            return getattr(self.config, "comment_fallback_text", "")
        if getattr(chapter, "detail_unavailable", False):
            return getattr(self.config, "comment_fallback_text", "")

        prompt_template = getattr(self.config, "comment_prompt", "")
        try:
            prompt = prompt_template.format(
                novel_title=latest.novel_title,
                author=latest.author,
                chapter_title=chapter.chapter_title,
                update_time=chapter.update_time,
                word_count=chapter.word_count,
                preview=chapter.preview,
                chapter_url=chapter.chapter_url,
            )
            response = await self._llm_generate(prompt)
        except Exception as exc:
            logger.warning(f"点评生成失败，提示词格式化或 llm 调用异常：{exc}")
            return getattr(self.config, "comment_fallback_text", "")

        text = getattr(response, "completion_text", "") or ""
        text = text.strip()
        if not text:
            logger.warning("点评生成失败，llm 返回空内容")
            return getattr(self.config, "comment_fallback_text", "")
        return text

    async def _llm_generate(self, prompt: str):
        llm_generate = self.context.llm_generate
        provider_id = self._maybe_resolve_chat_provider_id()

        if provider_id:
            try:
                return await llm_generate(
                    chat_provider_id=provider_id,
                    prompt=prompt,
                )
            except TypeError as exc:
                if not _looks_like_legacy_llm_signature_error(exc):
                    raise

        try:
            return await llm_generate(prompt=prompt)
        except TypeError as exc:
            if "chat_provider_id" not in str(exc):
                raise

        return await llm_generate(
            chat_provider_id=self._resolve_chat_provider_id(),
            prompt=prompt,
        )

    def _maybe_resolve_chat_provider_id(self) -> str | None:
        try:
            return self._resolve_chat_provider_id()
        except Exception:
            return None

    def _resolve_chat_provider_id(self) -> str:
        raw_config = {}
        if hasattr(self.context, "get_config"):
            try:
                raw_config = self.context.get_config() or {}
            except Exception:
                raw_config = {}

        normalized = _normalize_mapping(raw_config)
        provider_settings = _normalize_mapping(normalized.get("provider_settings") or {})
        provider_id = str(provider_settings.get("default_provider_id") or "").strip()
        if provider_id:
            return provider_id

        providers = normalized.get("provider") or []
        for provider in providers:
            provider_data = _normalize_mapping(provider)
            provider_id = str(provider_data.get("id") or "").strip()
            if provider_id and provider_data.get("enable", True):
                return provider_id

        raise RuntimeError("未找到可用的聊天模型提供商，请先在 AstrBot 中配置 provider")


def _normalize_mapping(data: Any) -> dict[str, Any]:
    if data is None:
        return {}
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    elif hasattr(data, "dict") and callable(data.dict):
        data = data.dict()
    elif not isinstance(data, Mapping) and hasattr(data, "__dict__"):
        data = vars(data)

    if not isinstance(data, Mapping):
        return {}
    return dict(data)


def _looks_like_legacy_llm_signature_error(exc: TypeError) -> bool:
    text = str(exc)
    return "unexpected keyword argument 'chat_provider_id'" in text or "got an unexpected keyword argument 'chat_provider_id'" in text
