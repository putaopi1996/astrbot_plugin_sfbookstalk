from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ChapterDetail, NovelLatest


def build_update_messages(
    latest: "NovelLatest",
    chapter: "ChapterDetail",
    comment: str,
    preview_max_chars: int,
    title_prefix: str = "",
) -> list[str]:
    preview = _truncate(chapter.preview or "暂无预览内容", preview_max_chars)
    preview_message = f"预览：{preview}"
    if getattr(chapter, "detail_unavailable", False):
        preview_message = f"{preview_message}\n原文：{chapter.chapter_url}"

    return [
        _build_header(latest, chapter, title_prefix),
        preview_message,
        f"点评：{comment}",
    ]


def build_update_message(
    latest: "NovelLatest",
    chapter: "ChapterDetail",
    comment: str,
    preview_max_chars: int,
    title_prefix: str = "",
) -> str:
    return "\n".join(
        build_update_messages(
            latest,
            chapter,
            comment,
            preview_max_chars,
            title_prefix=title_prefix,
        )
    )


def _build_header(latest: "NovelLatest", chapter: "ChapterDetail", title_prefix: str) -> str:
    del title_prefix
    if getattr(chapter, "detail_unavailable", False) or not chapter.update_time or chapter.word_count <= 0:
        return f"（{latest.author}）更新了最新章节（{chapter.chapter_title}）"
    return (
        f"（{latest.author}）在{chapter.update_time}"
        f"更新了字数为{chapter.word_count}的最新章节（{chapter.chapter_title}）"
    )


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return "." * max_chars
    return text[: max_chars - 3].rstrip() + "..."
