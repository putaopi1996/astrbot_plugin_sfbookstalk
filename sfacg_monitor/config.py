from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEFAULT_COMMENT_PROMPT = """请根据下面的 SF 轻小说更新信息写一段简短中文点评。
要求：
1. 点评字数，不超过 80 字。
2. 同时评价章节字数和预览内容。
3. 不要剧透，不要编造预览里没有的信息。

小说：{novel_title}
作者：{author}
章节：{chapter_title}
更新时间：{update_time}
字数：{word_count}
预览：{preview}
"""

DEFAULT_COMMENT_FALLBACK_TEXT = "点评暂时生成失败，但这章已经更新，可以先去看看正文。"


@dataclass(frozen=True)
class MonitorConfig:
    novel_url: str
    check_interval_minutes: int = 10
    group_ids: tuple[str, ...] = ()
    private_user_ids: tuple[str, ...] = ()
    notify_on_first_run: bool = False
    preview_max_chars: int = 180
    request_timeout_seconds: int = 15
    enable_llm_comment: bool = True
    comment_prompt: str = DEFAULT_COMMENT_PROMPT
    comment_fallback_text: str = DEFAULT_COMMENT_FALLBACK_TEXT

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "MonitorConfig":
        data = data or {}
        novel_url = str(data.get("novel_url", "")).strip()
        if not novel_url:
            raise ValueError("novel_url 不能为空")

        interval = int(data.get("check_interval_minutes", 10))
        if interval < 1:
            raise ValueError("check_interval_minutes 必须大于等于 1")

        preview_max_chars = int(data.get("preview_max_chars", 180))
        if preview_max_chars < 20:
            raise ValueError("preview_max_chars 必须大于等于 20")

        timeout = int(data.get("request_timeout_seconds", 15))
        if timeout < 3:
            raise ValueError("check_interval_minutes 或 request_timeout_seconds 配置无效")

        return cls(
            novel_url=novel_url,
            check_interval_minutes=interval,
            group_ids=tuple(_normalize_ids(data.get("group_ids", []))),
            private_user_ids=tuple(_normalize_ids(data.get("private_user_ids", []))),
            notify_on_first_run=bool(data.get("notify_on_first_run", False)),
            preview_max_chars=preview_max_chars,
            request_timeout_seconds=timeout,
            enable_llm_comment=bool(data.get("enable_llm_comment", True)),
            comment_prompt=str(data.get("comment_prompt") or DEFAULT_COMMENT_PROMPT),
            comment_fallback_text=str(data.get("comment_fallback_text") or DEFAULT_COMMENT_FALLBACK_TEXT),
        )

    @property
    def check_interval_seconds(self) -> int:
        return self.check_interval_minutes * 60


def _normalize_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.replace("\n", ",").split(",")
    else:
        raw_items = list(value)
    ids: list[str] = []
    for item in raw_items:
        text = str(item).strip()
        if text:
            ids.append(text)
    return ids
