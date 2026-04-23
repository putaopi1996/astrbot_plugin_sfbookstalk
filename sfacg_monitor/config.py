from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
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
    def from_sources(cls, plugin_config: Any, fallback_config: Any = None) -> "MonitorConfig":
        primary = _normalize_mapping(plugin_config)
        if _looks_like_plugin_config(primary):
            return cls.from_mapping(primary)
        return cls.from_mapping(fallback_config)

    @classmethod
    def from_mapping(cls, data: Any) -> "MonitorConfig":
        data = _normalize_mapping(data)
        novel_url = str(_unwrap_field_value(data.get("novel_url", ""))).strip()
        if not novel_url:
            raise ValueError("novel_url 不能为空")

        interval = int(_unwrap_field_value(data.get("check_interval_minutes", 10)))
        if interval < 1:
            raise ValueError("check_interval_minutes 必须大于等于 1")

        preview_max_chars = int(_unwrap_field_value(data.get("preview_max_chars", 180)))
        if preview_max_chars < 20:
            raise ValueError("preview_max_chars 必须大于等于 20")

        timeout = int(_unwrap_field_value(data.get("request_timeout_seconds", 15)))
        if timeout < 3:
            raise ValueError("check_interval_minutes 或 request_timeout_seconds 配置无效")

        return cls(
            novel_url=novel_url,
            check_interval_minutes=interval,
            group_ids=tuple(_normalize_ids(_unwrap_field_value(data.get("group_ids", [])))),
            private_user_ids=tuple(_normalize_ids(_unwrap_field_value(data.get("private_user_ids", [])))),
            notify_on_first_run=bool(_unwrap_field_value(data.get("notify_on_first_run", False))),
            preview_max_chars=preview_max_chars,
            request_timeout_seconds=timeout,
            enable_llm_comment=bool(_unwrap_field_value(data.get("enable_llm_comment", True))),
            comment_prompt=str(_unwrap_field_value(data.get("comment_prompt")) or DEFAULT_COMMENT_PROMPT),
            comment_fallback_text=str(
                _unwrap_field_value(data.get("comment_fallback_text")) or DEFAULT_COMMENT_FALLBACK_TEXT
            ),
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

    normalized = dict(data)
    for key in ("config", "settings", "data", "value"):
        nested = normalized.get(key)
        if "novel_url" in normalized:
            break
        if isinstance(nested, Mapping):
            return dict(nested)
    return normalized


def _unwrap_field_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        for key in ("value", "data", "current", "default"):
            if key in value:
                return value[key]
    return value


def _looks_like_plugin_config(data: Mapping[str, Any]) -> bool:
    return any(
        key in data
        for key in (
            "novel_url",
            "check_interval_minutes",
            "group_ids",
            "private_user_ids",
            "notify_on_first_run",
            "preview_max_chars",
            "request_timeout_seconds",
            "enable_llm_comment",
            "comment_prompt",
            "comment_fallback_text",
        )
    )
