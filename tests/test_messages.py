from sfacg_monitor.messages import build_update_message


class DummyLatest:
    novel_title = "小说名"
    author = "作者名"


class DummyChapter:
    chapter_title = "第十二章"
    update_time = "2026/04/24 01:00"
    word_count = 3456
    preview = "这是一段超过长度限制的预览内容，用来检查截断是否生效。"
    chapter_url = "https://example.com/chapter"


def test_build_update_message_uses_expected_line_structure():
    message = build_update_message(
        DummyLatest(),
        DummyChapter(),
        comment="点评内容",
        preview_max_chars=12,
    )

    assert message.splitlines() == [
        "（作者名）在2026/04/24 01:00更新了字数为3456的最新章节（第十二章）",
        "小说：小说名",
        "链接：https://example.com/chapter",
        "预览：这是一段超过长度限...",
        "点评：点评内容",
    ]
