import asyncio
import sys
from pathlib import Path
from typing import Any
from typing import Mapping

PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from sfacg_monitor.client import SfNovelClient
from sfacg_monitor.comments import CommentGenerator
from sfacg_monitor.config import MonitorConfig
from sfacg_monitor.messages import build_update_message
from sfacg_monitor.monitor import MonitorRunner
from sfacg_monitor.sender import OneBotSender
from sfacg_monitor.state import KvStateStore


@register("astrbot_plugin_sfbookstalk", "putaopi1996", "监控 SF 轻小说更新并推送到 QQ", "1.0.0")
class SFBooksTalkPlugin(Star):
    def __init__(self, context: Context, config: Any = None):
        super().__init__(context)
        self._plugin_config = config
        self._task: asyncio.Task | None = None
        self._runner: MonitorRunner | None = None

    async def initialize(self):
        raw_global_config = None
        try:
            raw_global_config = self.context.get_config()
            logger.info(
                "SFBooksTalk 读取到配置结构："
                f"plugin={_describe_config_shape(self._plugin_config)}; "
                f"global={_describe_config_shape(raw_global_config)}"
            )
            source_config = self._plugin_config
            if not _looks_like_plugin_config(source_config):
                source_config = raw_global_config
            config = MonitorConfig.from_mapping(source_config)
            client = SfNovelClient(config.novel_url, config.request_timeout_seconds)
            commenter = CommentGenerator(self.context, config)
            sender = OneBotSender(self.context, config)
            state = KvStateStore(self)
            self._runner = MonitorRunner(config, client, commenter, sender, state)
            self._task = asyncio.create_task(self._runner.run_forever())
            logger.info("SFBooksTalk 插件已启动")
        except Exception as exc:
            logger.exception(
                "SFBooksTalk 插件初始化失败："
                f"{exc}；plugin={_describe_config_shape(self._plugin_config)}；"
                f"global={_describe_config_shape(raw_global_config)}"
            )

    @filter.command("sfbookstalk_test_send")
    async def sfbookstalk_test_send(self, event: AstrMessageEvent):
        """立即抓取当前最新章节并强制发送一条【测试】通知。"""
        if self._runner is None:
            yield event.plain_result("SFBooksTalk 还没有完成初始化，请先检查 novel_url 和插件日志。")
            return
        try:
            message = await _send_test_once(self._runner)
        except Exception as exc:
            logger.exception(f"SFBooksTalk 测试发送失败：{exc}")
            yield event.plain_result(f"测试发送失败：{exc}")
            return
        logger.info("SFBooksTalk 已完成一次手动测试发送")
        yield event.plain_result(f"测试发送完成，已按正式流程发送通知。\n\n{message}")

    async def terminate(self):
        if self._runner:
            self._runner.stop()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SFBooksTalk 插件已停止")


def _describe_config_shape(raw_config: Any) -> str:
    if raw_config is None:
        return "None"
    if isinstance(raw_config, Mapping):
        return f"{type(raw_config).__name__}(keys={list(raw_config.keys())})"
    keys = list(getattr(raw_config, "__dict__", {}).keys())
    if keys:
        return f"{type(raw_config).__name__}(attrs={keys})"
    return type(raw_config).__name__


def _looks_like_plugin_config(raw_config: Any) -> bool:
    if isinstance(raw_config, Mapping):
        keys = raw_config.keys()
    else:
        keys = getattr(raw_config, "__dict__", {}).keys()
    return any(
        key in keys
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


async def _send_test_once(runner: Any) -> str:
    if hasattr(runner, "send_test_once"):
        return await runner.send_test_once()
    if hasattr(runner, "_process_once"):
        return await runner._process_once(force_send=True, title_prefix="【测试】")

    required_attrs = ("client", "commenter", "sender", "config")
    if not all(hasattr(runner, attr) for attr in required_attrs):
        raise AttributeError("MonitorRunner 缺少测试发送入口")

    latest, chapter = await runner.client.fetch_latest()
    sender = runner.sender
    if hasattr(sender, "has_targets") and not sender.has_targets():
        raise RuntimeError("没有可发送的 QQ 群或 QQ 目标，请先配置 group_ids 或 private_user_ids")
    comment = await runner.commenter.generate(latest, chapter)
    message = build_update_message(
        latest,
        chapter,
        comment,
        getattr(runner.config, "preview_max_chars", 180),
        title_prefix="【测试】",
    )
    await sender.send_text(message)
    return message
