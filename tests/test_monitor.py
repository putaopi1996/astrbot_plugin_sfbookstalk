import pytest

from sfacg_monitor.config import MonitorConfig
from sfacg_monitor.models import ChapterDetail, NovelLatest
from sfacg_monitor.monitor import MonitorRunner
from sfacg_monitor.state import MemoryStateStore


class FakeClient:
    async def fetch_latest(self):
        return (
            NovelLatest("测试小说", "葡萄皮", "第十二章", "https://example.com/chapter"),
            ChapterDetail("第十二章", "2026/04/24 01:00", 3456, "预览", "https://example.com/chapter"),
        )


class FakeCommenter:
    async def generate(self, latest, chapter):
        return "点评"


class FakeSender:
    def __init__(self):
        self.messages = []

    async def send_text(self, message):
        self.messages.append(message)


@pytest.mark.asyncio
async def test_first_run_records_without_sending_by_default():
    sender = FakeSender()
    state = MemoryStateStore()
    config = MonitorConfig.from_mapping({"novel_url": "https://book.sfacg.com/Novel/747572/"})
    runner = MonitorRunner(config, FakeClient(), FakeCommenter(), sender, state)

    await runner.check_once()

    assert sender.messages == []
    assert await state.get_last_chapter_url() == "https://example.com/chapter"


@pytest.mark.asyncio
async def test_new_chapter_sends_message():
    sender = FakeSender()
    state = MemoryStateStore()
    await state.set_last_chapter_url("https://example.com/old")
    config = MonitorConfig.from_mapping({"novel_url": "https://book.sfacg.com/Novel/747572/"})
    runner = MonitorRunner(config, FakeClient(), FakeCommenter(), sender, state)

    await runner.check_once()

    assert len(sender.messages) == 1
    assert "（葡萄皮）在2026/04/24 01:00更新了字数为3456的最新章节（第十二章）" in sender.messages[0]
    assert await state.get_last_chapter_url() == "https://example.com/chapter"
