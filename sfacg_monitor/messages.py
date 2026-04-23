from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ChapterDetail, NovelLatest


def build_update_message(
    latest: "NovelLatest",
    chapter: "ChapterDetail",
    comment: str,
    preview_max_chars: int,
    title_prefix: str = "",
) -> str:
    preview = _truncate(chapter.preview or "暂无预览内容", preview_max_chars)
    return "\n".join(
        [
            f"{title_prefix}（{latest.author}）在{chapter.update_time}更新了字数为{chapter.word_count}的最新章节（{chapter.chapter_title}）",
            f"预览：{preview}",
            f"点评：{comment}",
        ]
    )


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return "." * max_chars
    return text[: max_chars - 3].rstrip() + "..."
