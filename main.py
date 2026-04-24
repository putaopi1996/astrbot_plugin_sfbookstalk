import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register


@register("astrbot_plugin_sfbookstalk", "putaopi1996", "监控 SF 轻小说更新并推送到 QQ", "1.0.0")
class SFBooksTalkPlugin(Star):
    def __init__(self, context: Context, config: Any = None):
        super().__init__(context)
        self._plugin_config = config
        self._task: asyncio.Task | None = None
        self._runner = None

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

            runtime = _load_runtime_components()
            config = runtime.MonitorConfig.from_mapping(source_config)
            client = runtime.SfNovelClient(config.novel_url, config.request_timeout_seconds)
            commenter = runtime.CommentGenerator(self.context, config)
            sender = runtime.OneBotSender(self.context, config)
            state = runtime.KvStateStore(self)
            self._runner = runtime.MonitorRunner(config, client, commenter, sender, state)
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
        """立即抓取当前最新章节并强制发送一次通知。"""
        if self._runner is None:
            yield event.plain_result("SFBooksTalk 还没有完成初始化，请先检查 novel_url 和插件日志。")
            return
        try:
            # Only trigger the actual notification flow here.
            await _send_test_once(self._runner)
        except Exception as exc:
            logger.exception(f"SFBooksTalk 测试发送失败：{exc}")
            yield event.plain_result(f"测试发送失败：{exc}")
            return
        logger.info("SFBooksTalk 已完成一次手动测试发送")
        return

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


async def _send_test_once(runner: Any) -> list[str]:
    runtime = _load_runtime_components()

    if hasattr(runner, "send_test_once"):
        return await runner.send_test_once()
    if hasattr(runner, "_process_once"):
        return await runner._process_once(force_send=True, title_prefix="")

    required_attrs = ("client", "commenter", "sender", "config")
    if not all(hasattr(runner, attr) for attr in required_attrs):
        raise AttributeError("MonitorRunner 缺少测试发送入口")

    latest, chapter = await runner.client.fetch_latest()
    sender = runner.sender
    if hasattr(sender, "has_targets") and not sender.has_targets():
        raise RuntimeError("没有可发送的 QQ 群或 QQ 目标，请先配置 group_ids 或 private_user_ids")
    comment = await runner.commenter.generate(latest, chapter)
    messages = runtime.render_update_messages(
        latest,
        chapter,
        comment,
        getattr(runner.config, "preview_max_chars", 180),
        title_prefix="",
    )
    if hasattr(sender, "send_texts"):
        await sender.send_texts(messages)
    else:
        for message in messages:
            await sender.send_text(message)
    return messages


def _load_runtime_components():
    module_names = (
        "sfacg_monitor.client",
        "sfacg_monitor.comments",
        "sfacg_monitor.config",
        "sfacg_monitor.messages",
        "sfacg_monitor.message_compat",
        "sfacg_monitor.monitor",
        "sfacg_monitor.sender",
        "sfacg_monitor.state",
    )
    modules: dict[str, Any] = {}
    for module_name in module_names:
        module = sys.modules.get(module_name)
        if module is None:
            module = importlib.import_module(module_name)
        else:
            module = importlib.reload(module)
        modules[module_name] = module

    return SimpleNamespace(
        SfNovelClient=modules["sfacg_monitor.client"].SfNovelClient,
        CommentGenerator=modules["sfacg_monitor.comments"].CommentGenerator,
        MonitorConfig=modules["sfacg_monitor.config"].MonitorConfig,
        render_update_message=modules["sfacg_monitor.message_compat"].render_update_message,
        render_update_messages=modules["sfacg_monitor.message_compat"].render_update_messages,
        MonitorRunner=modules["sfacg_monitor.monitor"].MonitorRunner,
        OneBotSender=modules["sfacg_monitor.sender"].OneBotSender,
        KvStateStore=modules["sfacg_monitor.state"].KvStateStore,
    )
