from __future__ import annotations

from .compat import filter, logger
from .config import MonitorConfig


class OneBotSender:
    def __init__(self, context, config: MonitorConfig):
        self.context = context
        self.config = config

    def has_targets(self) -> bool:
        return bool(self.config.group_ids or self.config.private_user_ids)

    async def send_text(self, message: str) -> None:
        client = self._get_client()
        for group_id in self.config.group_ids:
            await self._safe_call(client, "send_group_msg", group_id=int(group_id), message=message)
        for user_id in self.config.private_user_ids:
            await self._safe_call(client, "send_private_msg", user_id=int(user_id), message=message)

    def _get_client(self):
        platform = self.context.get_platform(filter.PlatformAdapterType.AIOCQHTTP)
        if platform is None:
            raise RuntimeError("未找到 OneBot/aiocqhttp 平台")
        return platform.get_client()

    async def _safe_call(self, client, action: str, **payload) -> None:
        try:
            await client.api.call_action(action, **payload)
        except Exception as exc:
            logger.warning(f"OneBot 发送失败 action={action} payload={payload}: {exc}")
