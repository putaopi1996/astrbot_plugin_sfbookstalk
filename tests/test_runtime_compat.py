import asyncio
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sfacg_monitor.comments import CommentGenerator
from sfacg_monitor.config import MonitorConfig
from sfacg_monitor.messages import build_update_message, build_update_messages
from sfacg_monitor.models import ChapterDetail, NovelLatest


astrbot_mod = types.ModuleType("astrbot")
astrbot_api_mod = types.ModuleType("astrbot.api")
astrbot_event_mod = types.ModuleType("astrbot.api.event")
astrbot_star_mod = types.ModuleType("astrbot.api.star")


class _Logger:
    def info(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def exception(self, *_args, **_kwargs):
        pass


class _Filter:
    @staticmethod
    def command(_name):
        def decorator(func):
            return func

        return decorator


astrbot_api_mod.logger = _Logger()
astrbot_event_mod.AstrMessageEvent = object
astrbot_event_mod.filter = _Filter()
astrbot_star_mod.Context = object
astrbot_star_mod.Star = object
astrbot_star_mod.register = lambda *_args, **_kwargs: (lambda cls: cls)

sys.modules.setdefault("astrbot", astrbot_mod)
sys.modules.setdefault("astrbot.api", astrbot_api_mod)
sys.modules.setdefault("astrbot.api.event", astrbot_event_mod)
sys.modules.setdefault("astrbot.api.star", astrbot_star_mod)

import main as plugin_main
from main import _send_test_once
from sfacg_monitor import message_compat


class _LegacyRunner:
    def __init__(self):
        self.config = types.SimpleNamespace(
            preview_max_chars=180,
            group_ids=("123456",),
            private_user_ids=(),
        )
        self.client = types.SimpleNamespace(fetch_latest=self._fetch_latest)
        self.commenter = types.SimpleNamespace(generate=self._generate_comment)
        self.sender = types.SimpleNamespace(has_targets=lambda: True, send_text=self._send_text)
        self.state_store = types.SimpleNamespace()
        self.sent_messages = []

    async def _fetch_latest(self):
        latest = NovelLatest(
            novel_title="示例小说",
            author="作者",
            latest_chapter_title="第1章",
            latest_chapter_url="https://book.sfacg.com/vip/c/1/",
        )
        chapter = ChapterDetail(
            chapter_title="第1章",
            chapter_url="https://book.sfacg.com/vip/c/1/",
            update_time="2026-04-24 10:00:00",
            word_count=1234,
            preview="预览内容",
        )
        return latest, chapter

    async def _generate_comment(self, latest, chapter):
        return "点评完成"

    async def _send_text(self, message):
        self.sent_messages.append(message)


class _FakeResponse:
    def __init__(self, text: str):
        self.completion_text = text


class _ProviderContext:
    def __init__(self):
        self.calls = []

    async def llm_generate(self, *, chat_provider_id, prompt):
        self.calls.append((chat_provider_id, prompt))
        return _FakeResponse("点评完成")

    def get_config(self):
        return {
            "provider_settings": {"default_provider_id": "default"},
            "provider": [{"id": "default", "enable": True}],
        }


class _OpaqueProviderContext(_ProviderContext):
    async def _llm_generate_impl(self, *, chat_provider_id, prompt):
        self.calls.append((chat_provider_id, prompt))
        return _FakeResponse("点评完成")

    async def llm_generate(self, **kwargs):
        return await self._llm_generate_impl(**kwargs)


class _ObjectConfigProviderContext(_ProviderContext):
    def get_config(self):
        return types.SimpleNamespace(
            provider_settings=types.SimpleNamespace(default_provider_id="default"),
            provider=[types.SimpleNamespace(id="default", enable=True)],
        )


def test_send_test_once_supports_legacy_runner():
    runner = _LegacyRunner()
    result = asyncio.run(_send_test_once(runner))

    expected = build_update_messages(
        NovelLatest(
            novel_title="示例小说",
            author="作者",
            latest_chapter_title="第1章",
            latest_chapter_url="https://book.sfacg.com/vip/c/1/",
        ),
        ChapterDetail(
            chapter_title="第1章",
            chapter_url="https://book.sfacg.com/vip/c/1/",
            update_time="2026-04-24 10:00:00",
            word_count=1234,
            preview="预览内容",
        ),
        "点评完成",
        180,
    )

    assert result == expected
    assert runner.sent_messages == expected


def test_test_send_command_yields_three_reply_messages(monkeypatch):
    plugin = object.__new__(plugin_main.SFBooksTalkPlugin)
    plugin._runner = object()

    async def _fake_send_test_once(_runner):
        return [
            "（作者）更新了最新章节（第1章）",
            "预览：预览内容",
            "点评：点评完成",
        ]

    class _Event:
        @staticmethod
        def plain_result(message):
            return message

    async def _collect():
        replies = []
        async for item in plugin.sfbookstalk_test_send(_Event()):
            replies.append(item)
        return replies

    monkeypatch.setattr(plugin_main, "_send_test_once", _fake_send_test_once)

    replies = asyncio.run(_collect())

    assert replies == [
        "测试发送完成，已按正式流程发送通知。\n\n（作者）更新了最新章节（第1章）",
        "预览：预览内容",
        "点评：点评完成",
    ]


def test_comment_generator_supplies_default_provider_id():
    config = MonitorConfig.from_mapping(
        {
            "novel_url": "https://book.sfacg.com/Novel/747572/",
            "enable_llm_comment": True,
        }
    )
    context = _ProviderContext()
    generator = CommentGenerator(context, config)
    latest = NovelLatest(
        novel_title="示例小说",
        author="作者",
        latest_chapter_title="第1章",
        latest_chapter_url="https://book.sfacg.com/vip/c/1/",
    )
    chapter = ChapterDetail(
        chapter_title="第1章",
        chapter_url="https://book.sfacg.com/vip/c/1/",
        update_time="2026-04-24 10:00:00",
        word_count=1234,
        preview="预览内容",
    )

    result = asyncio.run(generator.generate(latest, chapter))

    assert result == "点评完成"
    assert context.calls
    assert context.calls[0][0] == "default"


def test_comment_generator_retries_with_provider_id_for_opaque_signature():
    config = MonitorConfig.from_mapping(
        {
            "novel_url": "https://book.sfacg.com/Novel/747572/",
            "enable_llm_comment": True,
        }
    )
    context = _OpaqueProviderContext()
    generator = CommentGenerator(context, config)
    latest = NovelLatest(
        novel_title="示例小说",
        author="作者",
        latest_chapter_title="第1章",
        latest_chapter_url="https://book.sfacg.com/vip/c/1/",
    )
    chapter = ChapterDetail(
        chapter_title="第1章",
        chapter_url="https://book.sfacg.com/vip/c/1/",
        update_time="2026-04-24 10:00:00",
        word_count=1234,
        preview="预览内容",
    )

    result = asyncio.run(generator.generate(latest, chapter))

    assert result == "点评完成"
    assert context.calls
    assert context.calls[0][0] == "default"


def test_comment_generator_supports_object_config_provider_settings():
    config = MonitorConfig.from_mapping(
        {
            "novel_url": "https://book.sfacg.com/Novel/747572/",
            "enable_llm_comment": True,
        }
    )
    context = _ObjectConfigProviderContext()
    generator = CommentGenerator(context, config)
    latest = NovelLatest(
        novel_title="示例小说",
        author="作者",
        latest_chapter_title="第1章",
        latest_chapter_url="https://book.sfacg.com/vip/c/1/",
    )
    chapter = ChapterDetail(
        chapter_title="第1章",
        chapter_url="https://book.sfacg.com/vip/c/1/",
        update_time="2026-04-24 10:00:00",
        word_count=1234,
        preview="预览内容",
    )

    result = asyncio.run(generator.generate(latest, chapter))

    assert result == "点评完成"
    assert context.calls
    assert context.calls[0][0] == "default"


def test_comment_generator_uses_fallback_for_partial_chapter():
    config = MonitorConfig.from_mapping(
        {
            "novel_url": "https://book.sfacg.com/Novel/747572/",
            "enable_llm_comment": True,
            "comment_fallback_text": "先去看正文",
        }
    )
    context = _ProviderContext()
    generator = CommentGenerator(context, config)
    latest = NovelLatest(
        novel_title="示例小说",
        author="作者",
        latest_chapter_title="第1章",
        latest_chapter_url="https://book.sfacg.com/vip/c/1/",
    )
    chapter = ChapterDetail(
        chapter_title="第1章",
        chapter_url="https://book.sfacg.com/vip/c/1/",
        update_time="",
        word_count=0,
        preview="章节详情暂时获取失败，请直接打开原文链接查看。",
        detail_unavailable=True,
    )

    result = asyncio.run(generator.generate(latest, chapter))

    assert result == "先去看正文"
    assert context.calls == []


def test_send_test_once_handles_stale_message_builder(monkeypatch):
    runner = _LegacyRunner()

    def old_build_update_message(latest, chapter, comment, preview_max_chars):
        return build_update_message(latest, chapter, comment, preview_max_chars)

    stale_messages = types.SimpleNamespace(build_update_message=old_build_update_message)
    monkeypatch.setattr(message_compat, "messages_module", stale_messages)

    result = asyncio.run(plugin_main._send_test_once(runner))

    assert result == [
        "（作者）在2026-04-24 10:00:00更新了字数为1234的最新章节（第1章）",
        "预览：预览内容",
        "点评：点评完成",
    ]
    assert runner.sent_messages == result


def test_initialize_uses_fresh_runtime_components_on_hot_reload(monkeypatch):
    created = {}

    class _FreshClient:
        def __init__(self, novel_url, timeout_seconds):
            created["client"] = (novel_url, timeout_seconds)

    class _FreshCommenter:
        def __init__(self, context, config):
            created["commenter"] = (context, config)

    class _FreshSender:
        def __init__(self, context, config):
            created["sender"] = (context, config)

    class _FreshRunner:
        def __init__(self, config, client, commenter, sender, state_store):
            created["runner"] = (config, client, commenter, sender, state_store)

        async def run_forever(self):
            return None

    class _StaleClient:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("stale client should not be used")

    class _StaleCommenter:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("stale commenter should not be used")

    def _fake_create_task(coro):
        coro.close()
        return types.SimpleNamespace(cancel=lambda: None)

    monkeypatch.setattr(plugin_main, "SfNovelClient", _StaleClient, raising=False)
    monkeypatch.setattr(plugin_main, "CommentGenerator", _StaleCommenter, raising=False)
    monkeypatch.setattr(asyncio, "create_task", _fake_create_task)
    monkeypatch.setattr(plugin_main.importlib, "reload", lambda module: module)

    monkeypatch.setattr(sys.modules["sfacg_monitor.client"], "SfNovelClient", _FreshClient)
    monkeypatch.setattr(sys.modules["sfacg_monitor.comments"], "CommentGenerator", _FreshCommenter)
    monkeypatch.setattr(sys.modules["sfacg_monitor.sender"], "OneBotSender", _FreshSender)
    monkeypatch.setattr(sys.modules["sfacg_monitor.monitor"], "MonitorRunner", _FreshRunner)

    context = types.SimpleNamespace(
        get_config=lambda: {
            "provider_settings": {"default_provider_id": "default"},
            "provider": [{"id": "default", "enable": True}],
        }
    )
    plugin = object.__new__(plugin_main.SFBooksTalkPlugin)
    plugin.context = context
    plugin._plugin_config = {
        "novel_url": "https://book.sfacg.com/Novel/747572/",
        "group_ids": ["123456"],
    }
    plugin._task = None
    plugin._runner = None

    asyncio.run(plugin.initialize())

    assert "client" in created
    assert "commenter" in created
    assert "sender" in created
    assert "runner" in created


def test_load_runtime_components_reloads_messages_before_message_compat(monkeypatch):
    stale_messages = types.ModuleType("sfacg_monitor.messages")
    stale_messages.build_update_message = lambda *_args, **_kwargs: "header\npreview\ncomment"
    stale_message_compat = types.ModuleType("sfacg_monitor.message_compat")
    stale_message_compat.render_update_message = lambda *_args, **_kwargs: "unused"
    stale_message_compat.render_update_messages = lambda *_args, **_kwargs: ["unused"]

    monkeypatch.setitem(sys.modules, "sfacg_monitor.messages", stale_messages)
    monkeypatch.setitem(sys.modules, "sfacg_monitor.message_compat", stale_message_compat)

    reload_order = []

    def fake_reload(module):
        reload_order.append(module.__name__)
        if module.__name__ == "sfacg_monitor.messages":
            module.build_update_messages = lambda *_args, **_kwargs: ["header", "preview", "comment"]
            return module
        if module.__name__ == "sfacg_monitor.message_compat":
            if not hasattr(sys.modules["sfacg_monitor.messages"], "build_update_messages"):
                raise ImportError("cannot import name 'build_update_messages' from 'sfacg_monitor.messages'")
            module.render_update_message = lambda *_args, **_kwargs: "header\npreview\ncomment"
            module.render_update_messages = lambda *_args, **_kwargs: ["header", "preview", "comment"]
            return module
        return module

    monkeypatch.setattr(plugin_main.importlib, "reload", fake_reload)

    runtime = plugin_main._load_runtime_components()

    assert runtime.render_update_messages(None, None, "", 0) == ["header", "preview", "comment"]
    assert reload_order.index("sfacg_monitor.messages") < reload_order.index("sfacg_monitor.message_compat")
