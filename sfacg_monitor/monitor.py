from __future__ import annotations

import asyncio

from .config import MonitorConfig
from .compat import logger
from .messages import build_update_message


class MonitorRunner:
    def __init__(self, config: MonitorConfig, client, commenter, sender, state_store):
        self.config = config
        self.client = client
        self.commenter = commenter
        self.sender = sender
        self.state_store = state_store
        self._stopped = asyncio.Event()

    async def check_once(self) -> None:
        latest, chapter = await self.client.fetch_latest()
        last_url = await self.state_store.get_last_chapter_url()
        is_first_run = last_url is None
        if is_first_run and not self.config.notify_on_first_run:
            await self.state_store.set_last_chapter_url(chapter.chapter_url)
            return
        if last_url == chapter.chapter_url:
            return
        comment = await self.commenter.generate(latest, chapter)
        message = build_update_message(latest, chapter, comment, self.config.preview_max_chars)
        await self.sender.send_text(message)
        await self.state_store.set_last_chapter_url(chapter.chapter_url)

    async def run_forever(self) -> None:
        while not self._stopped.is_set():
            try:
                await self.check_once()
            except Exception as exc:
                logger.exception(f"SFACG 更新检查失败：{exc}")
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self.config.check_interval_seconds)
            except asyncio.TimeoutError:
                pass

    def stop(self) -> None:
        self._stopped.set()
