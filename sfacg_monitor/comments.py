from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Mapping

try:
    from .compat import logger
except Exception:
    class _FallbackLogger:
        def info(self, message):
            print(message)

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
        fallback = getattr(self.config, "comment_fallback_text", "")
        if not getattr(self.config, "enable_llm_comment", True):
            return fallback
        if getattr(chapter, "detail_unavailable", False):
            return fallback

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
        except Exception as exc:
            logger.warning(f"点评生成失败，提示词格式化异常：{exc!r}")
            return fallback

        try:
            return await self._generate_with_providers(prompt)
        except Exception as exc:
            logger.warning(f"点评生成失败：{exc}")
            return fallback

    async def _generate_with_providers(self, prompt: str) -> str:
        candidates = await self.candidate_provider_ids()
        if not candidates:
            raise RuntimeError("未找到可用的聊天模型提供商，请先在 AstrBot 中配置 provider")

        errors: list[str] = []
        for provider_id in candidates:
            try:
                response = await self._call_provider(provider_id, prompt)
            except Exception as exc:
                logger.warning(f"点评调用 provider={provider_id} 失败：{exc!r}")
                errors.append(f"{provider_id}: {exc!r}")
                continue
            text = (getattr(response, "completion_text", "") or "").strip()
            if text:
                logger.info(f"点评已由 provider={provider_id} 生成")
                return text
            logger.warning(f"点评调用 provider={provider_id} 返回空内容")
            errors.append(f"{provider_id}: 返回空内容")
        raise RuntimeError("所有候选 provider 均失败：" + "；".join(errors))

    async def _call_provider(self, provider_id: str, prompt: str):
        llm_generate = getattr(self.context, "llm_generate", None)
        if callable(llm_generate):
            return await llm_generate(chat_provider_id=provider_id, prompt=prompt)

        # 旧版 AstrBot 没有 context.llm_generate，直接调用 provider 实例
        provider = _get_loaded_provider(self.context, provider_id)
        if provider is None:
            raise RuntimeError(f"Provider {provider_id} not found")
        return await provider.text_chat(prompt=prompt)

    async def candidate_provider_ids(self) -> list[str]:
        """按优先级返回点评要尝试的 provider id。

        1. 插件配置 llm_provider_id（手动指定）
        2. AstrBot 当前正在使用的聊天 provider（跟随 /provider 或 WebUI 的切换）
        3. 配置文件里的 provider_settings.default_provider_id
        4. 其余已加载的聊天 provider
        """
        loaded_ids = _loaded_provider_ids(self.context)
        raw_candidates: list[str] = [
            str(getattr(self.config, "llm_provider_id", "") or "").strip(),
            await _current_provider_id(self.context),
        ]

        global_config = _normalize_mapping(_safe_get_config(self.context))
        provider_settings = _normalize_mapping(global_config.get("provider_settings") or {})
        raw_candidates.append(str(provider_settings.get("default_provider_id") or "").strip())

        if loaded_ids is not None:
            raw_candidates.extend(loaded_ids)
        else:
            # 拿不到已加载列表时，退回读取配置文件中启用的 provider
            for provider in global_config.get("provider") or []:
                provider_data = _normalize_mapping(provider)
                if provider_data.get("enable", True):
                    raw_candidates.append(str(provider_data.get("id") or "").strip())

        candidates: list[str] = []
        for provider_id in raw_candidates:
            if not provider_id or provider_id in candidates:
                continue
            if loaded_ids is not None and provider_id not in loaded_ids:
                logger.warning(f"点评跳过未加载的 provider={provider_id}，可能已被删除或改名")
                continue
            candidates.append(provider_id)
        return candidates

    async def describe_providers(self) -> str:
        configured = str(getattr(self.config, "llm_provider_id", "") or "").strip()
        current = await _current_provider_id(self.context)
        loaded_ids = _loaded_provider_ids(self.context)
        candidates = await self.candidate_provider_ids()
        enabled = "已启用" if getattr(self.config, "enable_llm_comment", True) else "已关闭"
        lines = [
            f"大模型点评：{enabled}",
            f"插件指定 provider：{configured or '未指定（跟随 AstrBot 当前 provider）'}",
            f"AstrBot 当前 provider：{current or '未获取到'}",
            f"已加载的聊天 provider：{', '.join(loaded_ids) if loaded_ids else '无/无法获取'}",
            f"点评尝试顺序：{' -> '.join(candidates) if candidates else '无可用 provider'}",
        ]
        if configured and loaded_ids is not None and configured not in loaded_ids:
            lines.append(f"注意：指定的 provider {configured} 未加载，请在插件配置里重新选择")
        return "\n".join(lines)


async def _current_provider_id(context: Any) -> str:
    getter = getattr(context, "get_using_provider_async", None)
    if not callable(getter):
        getter = getattr(context, "get_using_provider", None)
    if not callable(getter):
        return ""
    try:
        provider = getter()
        if inspect.isawaitable(provider):
            provider = await provider
    except Exception as exc:
        logger.warning(f"获取 AstrBot 当前 provider 失败：{exc!r}")
        return ""
    return _provider_id(provider)


def _loaded_provider_ids(context: Any) -> list[str] | None:
    getter = getattr(context, "get_all_providers", None)
    if not callable(getter):
        return None
    try:
        providers = getter() or []
    except Exception as exc:
        logger.warning(f"获取已加载 provider 列表失败：{exc!r}")
        return None
    ids = [_provider_id(provider) for provider in providers]
    return [provider_id for provider_id in ids if provider_id]


def _get_loaded_provider(context: Any, provider_id: str) -> Any:
    getter = getattr(context, "get_all_providers", None)
    if not callable(getter):
        return None
    for provider in getter() or []:
        if _provider_id(provider) == provider_id:
            return provider
    return None


def _provider_id(provider: Any) -> str:
    if provider is None:
        return ""
    meta = getattr(provider, "meta", None)
    if callable(meta):
        try:
            return str(getattr(meta(), "id", "") or "").strip()
        except Exception:
            return ""
    return ""


def _safe_get_config(context: Any) -> Any:
    getter = getattr(context, "get_config", None)
    if not callable(getter):
        return {}
    try:
        return getter() or {}
    except Exception:
        return {}


def _normalize_mapping(data: Any) -> dict[str, Any]:
    if data is None:
        return {}
    model_dump = getattr(data, "model_dump", None)
    data_dict = getattr(data, "dict", None)
    if callable(model_dump):
        data = model_dump()
    elif callable(data_dict):
        data = data_dict()
    elif not isinstance(data, Mapping) and hasattr(data, "__dict__"):
        data = vars(data)

    if not isinstance(data, Mapping):
        return {}
    return dict(data)
