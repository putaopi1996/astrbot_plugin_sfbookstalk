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
    lines = [
        _build_header(latest, chapter, title_prefix),
        f"预览：{preview}",
    ]
    if getattr(chapter, "detail_unavailable", False):
        lines.append(f"原文：{chapter.chapter_url}")
    lines.append(f"点评：{comment}")
    return "\n".join(lines)


def _build_header(latest: "NovelLatest", chapter: "ChapterDetail", title_prefix: str) -> str:
    if getattr(chapter, "detail_unavailable", False) or not chapter.update_time or chapter.word_count <= 0:
        return f"{title_prefix}（{latest.author}）更新了最新章节（{chapter.chapter_title}）"
    return f"{title_prefix}（{latest.author}）在{chapter.update_time}更新了字数为{chapter.word_count}的最新章节（{chapter.chapter_title}）"


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return "." * max_chars
    return text[: max_chars - 3].rstrip() + "..."
