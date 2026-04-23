from __future__ import annotations


class _FallbackLogger:
    def info(self, message: str) -> None:
        print(message)

    def warning(self, message: str) -> None:
        print(message)

    def exception(self, message: str) -> None:
        print(message)


try:
    from astrbot.api import logger
except Exception:
    logger = _FallbackLogger()


try:
    from astrbot.api.event import filter
except Exception:
    class _FallbackPlatformAdapterType:
        AIOCQHTTP = "AIOCQHTTP"

    class _FallbackFilter:
        PlatformAdapterType = _FallbackPlatformAdapterType

    filter = _FallbackFilter()
