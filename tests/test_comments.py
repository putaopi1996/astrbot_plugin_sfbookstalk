import asyncio

from sfacg_monitor import comments
from sfacg_monitor.comments import CommentGenerator


class DummyConfig:
    def __init__(self, **kwargs):
        self.enable_llm_comment = kwargs.get("enable_llm_comment", True)
        self.comment_prompt = kwargs.get(
            "comment_prompt",
            "点评 {novel_title} {author} {chapter_title} {update_time} {word_count} {preview} {chapter_url}",
        )
        self.comment_fallback_text = kwargs.get("comment_fallback_text", "fallback")


class DummyContext:
    def __init__(self, response_text=None, exc=None):
        self.response_text = response_text
        self.exc = exc
        self.prompts = []

    async def llm_generate(self, *, prompt):
        self.prompts.append(prompt)
        if self.exc:
            raise self.exc
        return type("Resp", (), {"completion_text": self.response_text})()


class DummyLatest:
    novel_title = "小说名"
    author = "作者名"


class DummyChapter:
    chapter_title = "第十二章"
    update_time = "2026/04/24 01:00"
    word_count = 3456
    preview = "这里是一段很长很长的预览内容"
    chapter_url = "https://example.com/chapter"


class DummyLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)


def test_comment_generator_uses_prompt_and_strips_response():
    async def run():
        context = DummyContext("  很好的一章。  ")
        config = DummyConfig(comment_prompt="点评 {author} / {chapter_title} / {preview}")
        generator = CommentGenerator(context, config)

        result = await generator.generate(DummyLatest(), DummyChapter())

        assert result == "很好的一章。"
        assert context.prompts == ["点评 作者名 / 第十二章 / 这里是一段很长很长的预览内容"]

    asyncio.run(run())


def test_comment_generator_logs_and_falls_back_for_format_error_llm_error_and_empty_response(monkeypatch):
    dummy_logger = DummyLogger()
    monkeypatch.setattr(comments, "logger", dummy_logger)

    async def run():
        bad_prompt_context = DummyContext(response_text="不会被调用")
        bad_prompt_config = DummyConfig(comment_prompt="点评 {missing}", comment_fallback_text="格式兜底")
        bad_prompt_generator = CommentGenerator(bad_prompt_context, bad_prompt_config)

        assert await bad_prompt_generator.generate(DummyLatest(), DummyChapter()) == "格式兜底"
        assert bad_prompt_context.prompts == []

        failing_context = DummyContext(exc=RuntimeError("boom"))
        failing_config = DummyConfig(comment_fallback_text="异常兜底")
        failing_generator = CommentGenerator(failing_context, failing_config)

        assert await failing_generator.generate(DummyLatest(), DummyChapter()) == "异常兜底"

        empty_context = DummyContext(response_text="")
        empty_config = DummyConfig(comment_fallback_text="空内容兜底")
        empty_generator = CommentGenerator(empty_context, empty_config)

        assert await empty_generator.generate(DummyLatest(), DummyChapter()) == "空内容兜底"
        assert empty_context.prompts == [
            "点评 小说名 作者名 第十二章 2026/04/24 01:00 3456 这里是一段很长很长的预览内容 https://example.com/chapter"
        ]

    asyncio.run(run())

    assert len(dummy_logger.warnings) == 3
    assert "格式化或 llm 调用异常" in dummy_logger.warnings[0]
    assert "boom" in dummy_logger.warnings[1]
    assert "llm 返回空内容" in dummy_logger.warnings[2]
