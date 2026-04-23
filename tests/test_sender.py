import pytest

from sfacg_monitor.config import MonitorConfig
from sfacg_monitor.sender import OneBotSender


class FakeApi:
    def __init__(self):
        self.calls = []

    async def call_action(self, action, **payload):
        self.calls.append((action, payload))


class FakeClient:
    def __init__(self):
        self.api = FakeApi()


class FakePlatform:
    def __init__(self):
        self.client = FakeClient()

    def get_client(self):
        return self.client


class FakeContext:
    def __init__(self):
        self.platform = FakePlatform()

    def get_platform(self, _adapter_type):
        return self.platform


@pytest.mark.asyncio
async def test_onebot_sender_sends_to_groups_and_private_users():
    config = MonitorConfig.from_mapping(
        {
            "novel_url": "https://book.sfacg.com/Novel/747572/",
            "group_ids": ["1001"],
            "private_user_ids": ["2002"],
        }
    )
    context = FakeContext()
    sender = OneBotSender(context, config)

    await sender.send_text("hello")

    assert context.platform.client.api.calls == [
        ("send_group_msg", {"group_id": 1001, "message": "hello"}),
        ("send_private_msg", {"user_id": 2002, "message": "hello"}),
    ]
