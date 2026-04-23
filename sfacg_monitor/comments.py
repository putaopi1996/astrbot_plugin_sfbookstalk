from __future__ import annotations

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
            response = await self.context.llm_generate(prompt=prompt)
        except Exception as exc:
            logger.warning(f"点评生成失败，提示词格式化或 llm 调用异常：{exc}")
            return getattr(self.config, "comment_fallback_text", "")

        text = getattr(response, "completion_text", "") or ""
        text = text.strip()
        if not text:
            logger.warning("点评生成失败，llm 返回空内容")
            return getattr(self.config, "comment_fallback_text", "")
        return text
