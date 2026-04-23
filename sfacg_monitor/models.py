from __future__ import annotations

from dataclasses import dataclass


class SfParseError(RuntimeError):
    pass


@dataclass(frozen=True)
class NovelLatest:
    novel_title: str
    author: str
    latest_chapter_title: str
    latest_chapter_url: str


@dataclass(frozen=True)
class ChapterDetail:
    chapter_title: str
    update_time: str
    word_count: int
    preview: str
    chapter_url: str
