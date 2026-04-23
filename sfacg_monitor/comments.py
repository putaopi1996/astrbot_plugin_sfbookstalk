from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

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
        try:
            signature = inspect.signature(llm_generate)
        except (TypeError, ValueError):
            signature = None

        if signature and "chat_provider_id" in signature.parameters:
            return await llm_generate(
                chat_provider_id=self._resolve_chat_provider_id(),
                prompt=prompt,
            )
        try:
            return await llm_generate(prompt=prompt)
        except TypeError as exc:
            if "chat_provider_id" not in str(exc):
                raise
        return await llm_generate(
            chat_provider_id=self._resolve_chat_provider_id(),
            prompt=prompt,
        )

    def _resolve_chat_provider_id(self) -> str:
        raw_config = {}
        if hasattr(self.context, "get_config"):
            try:
                raw_config = self.context.get_config() or {}
            except Exception:
                raw_config = {}

        provider_settings = raw_config.get("provider_settings") or {}
        provider_id = str(provider_settings.get("default_provider_id") or "").strip()
        if provider_id:
            return provider_id

        providers = raw_config.get("provider") or []
        for provider in providers:
            provider_id = str(provider.get("id") or "").strip()
            if provider_id and provider.get("enable", True):
                return provider_id

        raise RuntimeError("未找到可用的聊天模型提供商，请先在 AstrBot 中配置 provider")
