from sfacg_monitor.messages import build_update_message, build_update_messages
from sfacg_monitor.models import ChapterDetail, NovelLatest


def test_build_update_messages_splits_partial_chapter_detail_into_three_messages():
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

    messages = build_update_messages(
        latest,
        chapter,
        "先去看正文",
        180,
    )

    assert messages == [
        "（作者）更新了最新章节（第1章）",
        "预览：章节详情暂时获取失败，请直接打开原文链接查看。\n原文：https://book.sfacg.com/vip/c/1/",
        "点评：先去看正文",
    ]


def test_build_update_message_joins_three_messages_for_compat():
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

    message = build_update_message(
        latest,
        chapter,
        "点评完成",
        180,
        title_prefix="【测试】",
    )

    assert message == "\n".join(
        [
            "（作者）在2026-04-24 10:00:00更新了字数为1234的最新章节（第1章）",
            "预览：预览内容",
            "点评：点评完成",
        ]
    )
    assert "【测试】" not in message
