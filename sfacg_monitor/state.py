from __future__ import annotations


class KvStateStore:
    def __init__(self, star, key: str = "last_chapter_url"):
        self.star = star
        self.key = key

    async def get_last_chapter_url(self) -> str | None:
        return await self.star.get_kv_data(self.key, None)

    async def set_last_chapter_url(self, chapter_url: str) -> None:
        await self.star.put_kv_data(self.key, chapter_url)


class MemoryStateStore:
    def __init__(self):
        self.value: str | None = None

    async def get_last_chapter_url(self) -> str | None:
        return self.value

    async def set_last_chapter_url(self, chapter_url: str) -> None:
        self.value = chapter_url
