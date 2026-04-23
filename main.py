import asyncio
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from astrbot.api import logger
from astrbot.api.star import Context, Star, register

from sfacg_monitor.client import SfNovelClient
from sfacg_monitor.comments import CommentGenerator
from sfacg_monitor.config import MonitorConfig
from sfacg_monitor.monitor import MonitorRunner
from sfacg_monitor.sender import OneBotSender
from sfacg_monitor.state import KvStateStore


@register("astrbot_plugin_sfbookstalk", "putaopi1996", "监控 SF 轻小说更新并推送到 QQ", "1.0.0")
class SFBooksTalkPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._task: asyncio.Task | None = None
        self._runner: MonitorRunner | None = None

    async def initialize(self):
        try:
            raw_config = self.context.get_config() or {}
            config = MonitorConfig.from_mapping(raw_config)
            client = SfNovelClient(config.novel_url, config.request_timeout_seconds)
            commenter = CommentGenerator(self.context, config)
            sender = OneBotSender(self.context, config)
            state = KvStateStore(self)
            self._runner = MonitorRunner(config, client, commenter, sender, state)
            self._task = asyncio.create_task(self._runner.run_forever())
            logger.info("SFBooksTalk 插件已启动")
        except Exception as exc:
            logger.exception(f"SFBooksTalk 插件初始化失败：{exc}")

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
